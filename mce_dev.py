#!/usr/bin/env python3
"""
mce_dev.py — ManimCE Fast Development Workflow CLI

Approximates 3b1b's ManimGL interactive workflow within ManimCE by
leveraging: targeted animation rendering (-n), snapshot mode (-s),
section-based partial movie files, micro-scene decomposition, and
a persistent mpv preview window via IPC.

Usage:
    python mce_dev.py run_scene <file> <line_number> [--quality ql]
    python mce_dev.py snapshot <file> <line_number>
    python mce_dev.py render_range <file> <scene_name> <start> <end> [--quality ql]
    python mce_dev.py render_section <file> <scene_name> <section_name>
    python mce_dev.py render_full <file> <scene_name> [--quality qh]
    python mce_dev.py list_scenes <file>
    python mce_dev.py dev <file> [--scene <scene_name>]

Requirements:
    pip install manim watchdog
    mpv must be installed and on PATH
"""

import ast
import sys
import os
import subprocess
import argparse
import json
import time
import socket
from pathlib import Path
from contextlib import contextmanager


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

MPV_SOCKET = "/tmp/mpv-manim"

# Where manim writes output. Set via manim.cfg's media_dir option.
# Default manim uses "media", but change this to match your setup.
MEDIA_DIR = "exports"

QUALITY_FLAGS = {
    "ql": "-ql",       # 480p, 15fps — fastest for iteration
    "qm": "-qm",       # 720p, 30fps — decent preview
    "qh": "-qh",       # 1080p, 60fps — high quality
    "qp": "-qp",       # 1440p, 60fps — production
    "qk": "-qk",       # 4K, 60fps — final render
}

QUALITY_DIR_MAP = {
    "ql": "480p15",
    "qm": "720p30",
    "qh": "1080p60",
    "qp": "1440p60",
    "qk": "2160p60",
}


# ──────────────────────────────────────────────────────────────────────
# Persistent mpv Preview Window (IPC)
# ──────────────────────────────────────────────────────────────────────

def mpv_is_alive() -> bool:
    """Check if mpv is listening on the IPC socket."""
    if not os.path.exists(MPV_SOCKET):
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(MPV_SOCKET)
        # Send a harmless command to verify it's responsive
        msg = json.dumps({"command": ["get_property", "pid"]}) + "\n"
        sock.sendall(msg.encode())
        response = sock.recv(4096)
        sock.close()
        return len(response) > 0
    except (ConnectionRefusedError, FileNotFoundError, OSError, socket.timeout):
        # Stale socket — clean it up
        try:
            os.remove(MPV_SOCKET)
        except OSError:
            pass
        return False


def mpv_spawn():
    """
    Spawn mpv in idle mode with IPC socket.
    Blocks until the socket is ready to accept commands.
    """
    print("  Starting mpv preview window...")

    # Clean up stale socket if present
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except OSError:
            pass

    # Spawn mpv in background
    #   --idle          start without a file, wait for IPC commands
    #   --force-window  show window immediately even with no file
    #   --keep-open=yes don't close when playback ends
    #   --loop-file     loop videos continuously (no effect on images)
    #   --title         identify the window in taskbar / alt-tab
    #   --geometry      reasonable default size
    #   --osd-level=0   suppress on-screen display clutter
    cmd = [
        "mpv",
        "--idle",
        "--force-window",
        "--keep-open=yes",
        "--loop-file",
        f"--input-ipc-server={MPV_SOCKET}",
        "--title=ManimCE Preview",
        "--geometry=960x540",
        "--osd-level=0",
    ]

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Detach from our process group
    )

    # Wait for socket to become available (up to 2 seconds)
    for _ in range(20):
        time.sleep(0.1)
        if os.path.exists(MPV_SOCKET):
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect(MPV_SOCKET)
                sock.close()
                print("  mpv preview window ready.")
                return True
            except (ConnectionRefusedError, OSError):
                continue

    print("  WARNING: mpv started but socket not ready. Preview may not work.")
    return False


def mpv_send_file(filepath: str):
    """
    Send a file to the persistent mpv window.
    Spawns mpv automatically if not already running.
    Handles both video (.mp4) and image (.png) files seamlessly —
    mpv switches between looping video and displaying a still image
    in the same window.
    """
    abs_path = os.path.abspath(filepath)

    if not os.path.exists(abs_path):
        print(f"  WARNING: Output file not found: {abs_path}")
        return False

    # Ensure mpv is running
    if not mpv_is_alive():
        if not mpv_spawn():
            print("  ERROR: Could not start mpv. No preview available.")
            return False

    # Send the file via IPC
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(MPV_SOCKET)

        # "replace" mode replaces the current playlist entry
        msg = json.dumps({"command": ["loadfile", abs_path, "replace"]}) + "\n"
        sock.sendall(msg.encode())

        response = sock.recv(4096).decode()
        sock.close()

        try:
            resp_data = json.loads(response)
            if resp_data.get("error") == "success":
                file_type = "image" if abs_path.endswith(".png") else "video"
                print(f"  -> Sent {file_type} to mpv: {os.path.basename(abs_path)}")
                return True
            else:
                print(f"  WARNING: mpv returned: {response.strip()}")
                return False
        except json.JSONDecodeError:
            # mpv sometimes sends multiple JSON lines; data received = probably fine
            print(f"  -> Sent to mpv: {os.path.basename(abs_path)}")
            return True

    except (ConnectionRefusedError, FileNotFoundError, OSError, socket.timeout) as e:
        print(f"  WARNING: mpv connection lost ({e}). Restarting...")
        # mpv may have been closed by user — restart and retry once
        if mpv_spawn():
            return mpv_send_file(filepath)
        return False


# ──────────────────────────────────────────────────────────────────────
# Output File Detection
# ──────────────────────────────────────────────────────────────────────

def find_output_file(filepath: str, scene_name: str, quality: str = "ql",
                     is_snapshot: bool = False) -> str | None:
    """
    Locate the output file that manim just rendered.

    Output structure (under MEDIA_DIR, default "exports"):
      Videos:  exports/videos/{file_stem}/{quality_dir}/{SceneName}.mp4
      Images:  exports/images/{file_stem}/{SceneName}_ManimCE_v*.png

    Falls back to the most recently modified matching file if the
    predicted path doesn't exist (handles version suffixes, partial
    movie files, etc.)
    """
    # Resolve MEDIA_DIR relative to the scene file's directory
    # so it matches manim's cwd (where manim.cfg is read from)
    scene_dir = Path(filepath).resolve().parent
    base = scene_dir / MEDIA_DIR
    file_stem = Path(filepath).stem
    quality_dir = QUALITY_DIR_MAP.get(quality, "480p15")

    if is_snapshot:
        image_dir = base / "images" / file_stem
        if image_dir.exists():
            candidates = list(image_dir.glob(f"{scene_name}*.png"))
            if candidates:
                return str(max(candidates, key=lambda p: p.stat().st_mtime))
    else:
        video_dir = base / "videos" / file_stem / quality_dir

        # Try exact match first
        exact = video_dir / f"{scene_name}.mp4"
        if exact.exists():
            return str(exact)

        # Try any matching .mp4 in the quality directory
        if video_dir.exists():
            candidates = list(video_dir.glob(f"*{scene_name}*.mp4"))
            if candidates:
                return str(max(candidates, key=lambda p: p.stat().st_mtime))

        # Check partial_movie_files directory
        partial_dir = video_dir / "partial_movie_files" / scene_name
        if partial_dir.exists():
            candidates = list(partial_dir.glob("*.mp4"))
            if candidates:
                return str(max(candidates, key=lambda p: p.stat().st_mtime))

    # Last resort: most recently modified file anywhere in MEDIA_DIR (within 30s)
    if base.exists():
        ext = "*.png" if is_snapshot else "*.mp4"
        all_files = list(base.rglob(ext))
        recent = [f for f in all_files
                  if time.time() - f.stat().st_mtime < 30]
        if recent:
            return str(max(recent, key=lambda p: p.stat().st_mtime))

    return None


# ──────────────────────────────────────────────────────────────────────
# Scene Detection: Parse .py to find Scene classes and line ranges
# ──────────────────────────────────────────────────────────────────────

def find_scenes(filepath: str) -> list[dict]:
    """Parse a Python file and return all Scene subclasses."""
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    scenes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            scene_bases = {
                "Scene", "MovingCameraScene", "ThreeDScene",
                "ZoomedScene", "VectorScene"
            }
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name in scene_bases:
                    scenes.append({
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno or node.lineno,
                    })
                    break

    return scenes


def scene_at_line(filepath: str, line_number: int) -> str | None:
    """Find which Scene class the cursor (line number) is inside."""
    scenes = find_scenes(filepath)
    for scene in scenes:
        if scene["start_line"] <= line_number <= scene["end_line"]:
            return scene["name"]
    for scene in scenes:
        if line_number == scene["start_line"]:
            return scene["name"]
    return None


# ──────────────────────────────────────────────────────────────────────
# Animation Index Detection
# ──────────────────────────────────────────────────────────────────────

def find_animation_calls(filepath: str, scene_name: str) -> list[dict]:
    """
    Find all animation calls (self.play, self.wait, etc.) in a scene's
    construct() method, with their line numbers and animation indices.
    """
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    anim_calls = []
    anim_methods = {"play", "wait", "play_all", "add_sound"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == scene_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "construct":
                    idx = 0
                    for stmt in ast.walk(item):
                        if isinstance(stmt, ast.Call):
                            func = stmt.func
                            if (isinstance(func, ast.Attribute) and
                                func.attr in anim_methods and
                                isinstance(func.value, ast.Name) and
                                func.value.id == "self"):
                                anim_calls.append({
                                    "index": idx,
                                    "line": stmt.lineno,
                                    "method": func.attr,
                                })
                                idx += 1
    return anim_calls


def animation_index_at_line(filepath: str, scene_name: str, line_number: int) -> int:
    """Find the animation index at or just before the given line number."""
    calls = find_animation_calls(filepath, scene_name)
    if not calls:
        return 0

    best_idx = 0
    for call in calls:
        if call["line"] <= line_number:
            best_idx = call["index"]
        else:
            break
    return best_idx


def has_visual_content(filepath: str, scene_name: str) -> bool:
    """
    Check if a scene has self.add() calls — i.e., visual content added
    to the scene without animation. Used to distinguish "truly empty"
    scenes from ones that display static content.
    """
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == scene_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "construct":
                    for stmt in ast.walk(item):
                        if (isinstance(stmt, ast.Call) and
                            isinstance(stmt.func, ast.Attribute) and
                            stmt.func.attr == "add" and
                            isinstance(stmt.func.value, ast.Name) and
                            stmt.func.value.id == "self"):
                            return True
    return False


# ──────────────────────────────────────────────────────────────────────
# Auto-Checkpoint: Exact-Line Snapshot Rendering
# ──────────────────────────────────────────────────────────────────────

def _find_statement_end_line(construct_node: ast.FunctionDef,
                             line_number: int) -> int | None:
    """
    Find the end line of the innermost statement containing line_number
    within the construct() method. Returns None if no statement found.
    """
    best = None
    best_span = float("inf")

    for node in ast.walk(construct_node):
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            continue
        if node is construct_node:
            continue
        end = node.end_lineno or node.lineno
        if node.lineno <= line_number <= end:
            span = end - node.lineno
            # Prefer the outermost statement-level node that still
            # contains the cursor, not sub-expressions
            if isinstance(node, ast.stmt) and span < best_span:
                best = node
                best_span = span

    if best:
        return best.end_lineno or best.lineno
    return None


def create_checkpoint_file(filepath: str, line_number: int,
                           scene_name: str) -> str | None:
    """
    Create a temp copy of the scene file with a checkpoint injected
    after the cursor line. Injects:
        self.wait(0.01)  # mce_auto_checkpoint
        return  # mce_auto_checkpoint

    This causes construct() to exit immediately after the cursor line,
    so a snapshot (-s) captures the exact scene state at that point.

    Returns the temp file path, or None if injection failed.
    """
    with open(filepath, "r") as f:
        lines = f.readlines()

    source = "".join(lines)
    tree = ast.parse(source)

    # Find the construct() method of the target scene
    construct_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == scene_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "construct":
                    construct_node = item
                    break
            break

    if not construct_node:
        return None

    # Find the end line of the statement at the cursor
    inject_after = _find_statement_end_line(construct_node, line_number)

    if inject_after is None:
        # Cursor might be on a blank/comment line — find the nearest
        # statement above the cursor within construct()
        for check_line in range(line_number, construct_node.lineno, -1):
            result = _find_statement_end_line(construct_node, check_line)
            if result is not None:
                inject_after = result
                break

    if inject_after is None:
        # Cursor is before any statements in construct — inject right
        # after the def line
        inject_after = construct_node.lineno

    # Determine indentation from the construct body
    # (first statement in construct, or default 8 spaces)
    if construct_node.body:
        first_stmt = construct_node.body[0]
        indent = len(lines[first_stmt.lineno - 1]) - len(
            lines[first_stmt.lineno - 1].lstrip()
        )
    else:
        indent = 8

    indent_str = " " * indent
    checkpoint_lines = (
        f"{indent_str}self.wait(0.01)  # mce_auto_checkpoint\n"
        f"{indent_str}return  # mce_auto_checkpoint\n"
    )

    # Inject after the target line
    new_lines = lines[:inject_after] + [checkpoint_lines] + lines[inject_after:]

    # Write temp file in the same directory (picks up same manim.cfg)
    scene_dir = Path(filepath).parent
    temp_name = f"._{Path(filepath).stem}_mce_checkpoint.py"
    temp_path = scene_dir / temp_name
    with open(temp_path, "w") as f:
        f.writelines(new_lines)

    return str(temp_path)


@contextmanager
def checkpoint_render(filepath: str, line_number: int, scene_name: str):
    """
    Context manager that creates a checkpoint temp file, yields it,
    and cleans up after rendering (even on error).
    """
    tmp = create_checkpoint_file(filepath, line_number, scene_name)
    try:
        yield tmp
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# ──────────────────────────────────────────────────────────────────────
# Section Detection
# ──────────────────────────────────────────────────────────────────────

def find_sections(filepath: str, scene_name: str) -> list[dict]:
    """Find all self.next_section() calls and their names."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    import re
    sections = []
    in_scene = False
    scene_indent = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if f"class {scene_name}" in stripped:
            in_scene = True
            scene_indent = len(line) - len(line.lstrip())
            continue
        if in_scene:
            current_indent = len(line) - len(line.lstrip())
            if stripped and current_indent <= scene_indent and not stripped.startswith("#"):
                in_scene = False
                continue
            match = re.search(r'self\.next_section\(["\'](.+?)["\']\)', stripped)
            if match:
                sections.append({"name": match.group(1), "line": i})

    return sections


# ──────────────────────────────────────────────────────────────────────
# Core Render Function
# ──────────────────────────────────────────────────────────────────────

def run_manim(filepath: str, scene_name: str, extra_args: list[str] = None,
              quality: str = "ql", send_to_preview: bool = True,
              dry_run: bool = False) -> str | None:
    """
    Build and execute a manim render command.
    After rendering, automatically sends the output to the persistent
    mpv window (spawning it if necessary).

    Returns the path to the output file, or None on failure.
    """
    cmd = [sys.executable, "-m", "manim", "render"]

    q_flag = QUALITY_FLAGS.get(quality, "-ql")
    cmd.append(q_flag)

    # We do NOT pass --preview. Preview is handled entirely through
    # the persistent mpv window via IPC, so manim just renders to file.
    is_snapshot = False
    if extra_args:
        cmd.extend(extra_args)
        is_snapshot = "-s" in extra_args

    # Use the scene file's directory as cwd so manim picks up
    # the local manim.cfg (which defines media_dir, quality, etc.)
    scene_dir = str(Path(filepath).resolve().parent)
    scene_filename = Path(filepath).name
    cmd.extend([scene_filename, scene_name])

    cmd_str = " ".join(cmd)
    print(f"\n{'='*60}")
    print(f"  MCE DEV | {cmd_str}")
    print(f"  CWD: {scene_dir}")
    print(f"{'='*60}\n")

    if dry_run:
        return None

    start = time.time()
    result = subprocess.run(cmd, capture_output=False, cwd=scene_dir)
    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"\n  Render FAILED ({elapsed:.1f}s)")
        return None

    print(f"\n  Rendered in {elapsed:.1f}s")

    # Find the output file and send to mpv
    output = find_output_file(filepath, scene_name, quality, is_snapshot)

    if output and send_to_preview:
        mpv_send_file(output)
    elif not output:
        print("  WARNING: Could not locate output file for preview.")

    return output


# ──────────────────────────────────────────────────────────────────────
# CLI Command Handlers
# ──────────────────────────────────────────────────────────────────────

def cmd_run_scene(args):
    """
    Detect scene at cursor and render it.
    - Cursor on class definition line -> render full scene (video if has
      animations, snapshot if static content only, skip if truly empty)
    - Cursor inside construct() -> render 2-3 animations around cursor
    Result appears in the mpv preview window.
    """
    scene_name = scene_at_line(args.file, args.line_number)
    if not scene_name:
        print(f"ERROR: No Scene class found at line {args.line_number}")
        sys.exit(1)

    print(f"  Detected scene: {scene_name} (cursor at line {args.line_number})")

    total_anims = len(find_animation_calls(args.file, scene_name))

    # Zero-animation scene: snapshot fallback or skip
    if total_anims == 0:
        if has_visual_content(args.file, scene_name):
            print("  No animations found, but scene has visual content -> auto-checkpoint snapshot")
            with checkpoint_render(args.file, args.line_number, scene_name) as tmp:
                if tmp:
                    run_manim(tmp, scene_name, extra_args=["-s"], quality="ql")
                else:
                    print("  WARNING: Checkpoint failed, falling back to full scene snapshot")
                    run_manim(args.file, scene_name, extra_args=["-s"], quality="ql")
        else:
            print("  No animations and no visual content (no self.add()). Nothing to preview.")
        return

    # Cursor on class definition -> full scene video
    scenes = find_scenes(args.file)
    for s in scenes:
        if s["start_line"] == args.line_number:
            print("  Cursor on class definition -> rendering full scene")
            run_manim(args.file, scene_name, quality=args.quality)
            return

    # Cursor inside scene -> targeted animation range
    anim_idx = animation_index_at_line(args.file, scene_name, args.line_number)
    centered = getattr(args, "centered", False)
    if centered:
        start_idx = max(anim_idx - 1, 0)
        end_idx = min(anim_idx + 1, total_anims - 1)
        print(f"  Animation index at cursor: {anim_idx} (of {total_anims - 1}) [centered range]")
    else:
        start_idx = anim_idx
        end_idx = min(anim_idx + 2, total_anims - 1)
        print(f"  Animation index at cursor: {anim_idx} (of {total_anims - 1})")
    run_manim(
        args.file, scene_name,
        extra_args=["-n", f"{start_idx},{end_idx}"],
        quality=args.quality
    )


def cmd_snapshot(args):
    """
    Render a snapshot (last frame as PNG) of the scene at cursor.
    - Cursor on class definition line -> snapshot of full scene
    - Cursor inside scene -> snapshot up to the animation at cursor
    - Zero-animation scene with self.add() -> snapshot of full scene
    - Truly empty scene -> skip mpv
    Image appears in the mpv preview window (replacing any video).
    """
    scene_name = scene_at_line(args.file, args.line_number)
    if not scene_name:
        print(f"ERROR: No Scene class found at line {args.line_number}")
        sys.exit(1)

    print(f"  Snapshot of: {scene_name}")

    total_anims = len(find_animation_calls(args.file, scene_name))

    # Zero-animation scene
    if total_anims == 0:
        if has_visual_content(args.file, scene_name):
            print("  No animations, has visual content -> auto-checkpoint snapshot")
            with checkpoint_render(args.file, args.line_number, scene_name) as tmp:
                if tmp:
                    run_manim(tmp, scene_name, extra_args=["-s"], quality="ql")
                else:
                    print("  WARNING: Checkpoint failed, falling back to full scene snapshot")
                    run_manim(args.file, scene_name, extra_args=["-s"], quality="ql")
        else:
            print("  No animations and no visual content (no self.add()). Nothing to preview.")
        return

    # Cursor on class definition -> full scene snapshot
    scenes = find_scenes(args.file)
    for s in scenes:
        if s["start_line"] == args.line_number:
            print("  Cursor on class definition -> full scene snapshot")
            run_manim(args.file, scene_name, extra_args=["-s"], quality="ql")
            return

    # Cursor inside scene -> auto-checkpoint snapshot at exact cursor line
    print(f"  Auto-checkpoint snapshot at line {args.line_number}")
    with checkpoint_render(args.file, args.line_number, scene_name) as tmp:
        if tmp:
            run_manim(tmp, scene_name, extra_args=["-s"], quality="ql")
        else:
            # Fallback to the old -n approach if checkpoint creation fails
            anim_idx = animation_index_at_line(args.file, scene_name, args.line_number)
            print(f"  WARNING: Checkpoint failed, falling back to -n 0,{anim_idx} -s")
            run_manim(
                args.file, scene_name,
                extra_args=["-n", f"0,{anim_idx}", "-s"],
                quality="ql"
            )


def cmd_render_range(args):
    """Render a specific animation range. Result appears in mpv."""
    run_manim(
        args.file, args.scene_name,
        extra_args=["-n", f"{args.start},{args.end}"],
        quality=args.quality
    )


def cmd_render_section(args):
    """Render scene with sections saved. Result appears in mpv."""
    run_manim(
        args.file, args.scene_name,
        extra_args=["--save_sections"],
        quality=args.quality
    )
    print(f"\n  Section files saved. Look for '{args.section_name}' "
          f"in the sections/ output directory.")


def cmd_render_full(args):
    """Full quality render of a scene. Result appears in mpv."""
    run_manim(args.file, args.scene_name, quality=args.quality)


def cmd_list_scenes(args):
    """List all scenes, their animation counts, and sections."""
    scenes = find_scenes(args.file)
    if not scenes:
        print("No Scene classes found.")
        return

    print(f"\n  Scenes in {args.file}:")
    print(f"  {'─'*50}")
    for s in scenes:
        anims = find_animation_calls(args.file, s["name"])
        sections = find_sections(args.file, s["name"])
        print(f"  {s['name']}")
        print(f"    Lines {s['start_line']}–{s['end_line']} | "
              f"{len(anims)} animations | {len(sections)} sections")
        if sections:
            for sec in sections:
                print(f"      § {sec['name']} (line {sec['line']})")
    print()


def cmd_dev(args):
    """
    Watch mode: auto-render the active scene on every file save.
    Results are pushed to the persistent mpv window automatically.
    Control which scene renders by editing .mce_dev_state.json.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("ERROR: watchdog not installed. Run: pip install watchdog")
        sys.exit(1)

    filepath = os.path.abspath(args.file)
    active_scene = args.scene

    if not active_scene:
        scenes = find_scenes(filepath)
        if scenes:
            active_scene = scenes[0]["name"]
        else:
            print("ERROR: No scenes found in file")
            sys.exit(1)

    state_file = Path(filepath).parent / ".mce_dev_state.json"
    state_file.write_text(json.dumps({
        "active_scene": active_scene,
        "quality": "ql",
        "mode": "full",      # "full", "snapshot", or "range"
        "range_start": 0,
        "range_end": -1,
    }, indent=2))

    print(f"\n{'='*60}")
    print(f"  MCE DEV WATCH MODE")
    print(f"  Watching: {filepath}")
    print(f"  Active scene: {active_scene}")
    print(f"  State file: {state_file}")
    print(f"{'='*60}")
    print(f"  Edit .mce_dev_state.json to change scene or mode.")
    print(f"  Preview updates in the mpv window on every save.")
    print(f"  Press Ctrl+C to stop.\n")

    class RenderOnChange(FileSystemEventHandler):
        def __init__(self):
            self.last_render = 0
            self.debounce_sec = 1.5

        def on_modified(self, event):
            if event.src_path != filepath:
                return
            now = time.time()
            if now - self.last_render < self.debounce_sec:
                return
            self.last_render = now

            try:
                state = json.loads(state_file.read_text())
            except Exception:
                state = {"active_scene": active_scene, "quality": "ql", "mode": "full"}

            scene = state.get("active_scene", active_scene)
            quality = state.get("quality", "ql")
            mode = state.get("mode", "full")

            print(f"\n  File changed -> rendering {scene} ({mode})...")

            extra = []
            if mode == "snapshot":
                extra = ["-s"]
            elif mode == "range":
                s = state.get("range_start", 0)
                e = state.get("range_end", -1)
                if e >= 0:
                    extra = ["-n", f"{s},{e}"]
                else:
                    extra = ["-n", f"{s}"]

            try:
                run_manim(filepath, scene,
                          extra_args=extra if extra else None,
                          quality=quality, send_to_preview=True)
            except Exception as e:
                print(f"  Render error: {e}")

    handler = RenderOnChange()
    observer = Observer()
    observer.schedule(handler, path=os.path.dirname(filepath), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n  Dev watch mode stopped.")
    observer.join()


# ──────────────────────────────────────────────────────────────────────
# CLI Argument Parsing
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ManimCE Fast Development Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run_scene scenes.py 42              Render scene at line 42
  %(prog)s snapshot scenes.py 42               Snapshot scene at line 42
  %(prog)s render_range scenes.py MyScene 3 5  Render animations 3-5
  %(prog)s list_scenes scenes.py               List all scenes
  %(prog)s dev scenes.py --scene MyScene       Watch mode, auto-render on save

All render commands automatically send output to a persistent mpv
preview window. mpv is spawned on the first render and reused for
all subsequent renders (video and images, same window).
        """
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # run_scene
    p = subparsers.add_parser("run_scene", help="Render scene at cursor position")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("line_number", type=int, help="Current cursor line number")
    p.add_argument("--quality", default="ql", choices=QUALITY_FLAGS.keys())
    p.add_argument("--centered", action="store_true",
                   help="Center animation range around cursor (1 before + 1 after)")
    p.set_defaults(func=cmd_run_scene)

    # snapshot
    p = subparsers.add_parser("snapshot", help="Render last frame of scene at cursor")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("line_number", type=int, help="Current cursor line number")
    p.set_defaults(func=cmd_snapshot)

    # render_range
    p = subparsers.add_parser("render_range", help="Render specific animation range")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("scene_name", help="Scene class name")
    p.add_argument("start", type=int, help="Start animation index")
    p.add_argument("end", type=int, help="End animation index")
    p.add_argument("--quality", default="ql", choices=QUALITY_FLAGS.keys())
    p.set_defaults(func=cmd_render_range)

    # render_section
    p = subparsers.add_parser("render_section", help="Render scene with sections saved")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("scene_name", help="Scene class name")
    p.add_argument("section_name", help="Section name to find")
    p.add_argument("--quality", default="ql", choices=QUALITY_FLAGS.keys())
    p.set_defaults(func=cmd_render_section)

    # render_full
    p = subparsers.add_parser("render_full", help="Full quality render")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("scene_name", help="Scene class name")
    p.add_argument("--quality", default="qh", choices=QUALITY_FLAGS.keys())
    p.set_defaults(func=cmd_render_full)

    # list_scenes
    p = subparsers.add_parser("list_scenes", help="List all scenes in file")
    p.add_argument("file", help="Path to .py file")
    p.set_defaults(func=cmd_list_scenes)

    # dev (watch mode)
    p = subparsers.add_parser("dev", help="Watch file and auto-render on save")
    p.add_argument("file", help="Path to .py file")
    p.add_argument("--scene", help="Active scene name (default: first scene)")
    p.set_defaults(func=cmd_dev)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
