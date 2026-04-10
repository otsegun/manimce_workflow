#!/usr/bin/env python3
"""
concat_render.py — Render all scenes in order and concatenate into final video.

Usage:
    python concat_render.py scenes.py --quality qh --output episode_01.mp4

This is your "production render" command. During development you render
individual micro-scenes; for the final video, this stitches them all together.
"""

import subprocess
import os
import argparse

# import importlib.util
from pathlib import Path

# Must match the MEDIA_DIR setting in mce_dev.py and your manim.cfg
MEDIA_DIR = "exports"


def load_scene_order(filepath: str) -> list[str]:
    """Load the EPISODE_ONE_SCENE_ORDER (or similar) from the scene file."""
    # spec = importlib.util.spec_from_file_location("scenes", filepath)
    # module = importlib.util.module_from_spec(spec)

    # Look for scene order constants
    with open(filepath) as f:
        content = f.read()

    # Simple extraction: find lists assigned to variables ending in _SCENE_ORDER
    import ast

    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "SCENE_ORDER" in target.id:
                    # Evaluate the list literal
                    try:
                        return ast.literal_eval(node.value)
                    except Exception:
                        pass

    print("WARNING: No *_SCENE_ORDER list found. Rendering all scenes in file order.")
    from mce_dev import find_scenes

    scenes = find_scenes(filepath)
    return [s["name"] for s in scenes]


def render_all(filepath: str, scene_order: list[str], quality: str = "qh"):
    """Render each scene individually and return paths to output files."""
    quality_flags = {"ql": "-ql", "qm": "-qm", "qh": "-qh", "qp": "-qp", "qk": "-qk"}
    q_flag = quality_flags.get(quality, "-qh")
    output_files = []

    for i, scene_name in enumerate(scene_order):
        print(f"\n{'─' * 60}")
        print(f"  Rendering {i + 1}/{len(scene_order)}: {scene_name}")
        print(f"{'─' * 60}")

        cmd = ["manim", "render", q_flag, filepath, scene_name]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ERROR rendering {scene_name}:")
            print(result.stderr)
            continue

        # Find the output file in manim's export directory
        # ManimCE outputs to exports/videos/<filename>/<quality>/
        base = Path(filepath).stem
        quality_dir_map = {
            "ql": "480p15",
            "qm": "720p30",
            "qh": "1080p60",
            "qp": "1440p60",
            "qk": "2160p60",
        }
        q_dir = quality_dir_map.get(quality, "1080p60")
        output_path = Path(MEDIA_DIR) / "videos" / base / q_dir / f"{scene_name}.mp4"

        if output_path.exists():
            output_files.append(str(output_path))
            print(f"  ✓ {output_path}")
        else:
            print(f"  WARNING: Expected output not found at {output_path}")
            # Try to find it
            search_dir = Path(MEDIA_DIR) / "videos" / base / q_dir
            if search_dir.exists():
                mp4s = list(search_dir.glob(f"*{scene_name}*.mp4"))
                if mp4s:
                    output_files.append(str(mp4s[0]))
                    print(f"  ✓ Found at {mp4s[0]}")

    return output_files


def concatenate(video_files: list[str], output: str):
    """Concatenate video files using ffmpeg."""
    if not video_files:
        print("ERROR: No video files to concatenate.")
        return

    # Write ffmpeg concat file
    concat_file = "concat_list.txt"
    with open(concat_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{os.path.abspath(vf)}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        output,
    ]

    print(f"\n{'=' * 60}")
    print(f"  Concatenating {len(video_files)} scenes → {output}")
    print(f"{'=' * 60}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(concat_file)

    if result.returncode == 0:
        print(f"\n  ✓ Final video: {output}")
        print(f"  Size: {os.path.getsize(output) / 1024 / 1024:.1f} MB")
    else:
        print(f"  ERROR: {result.stderr}")


def main():
    parser = argparse.ArgumentParser(
        description="Render and concatenate ManimCE scenes"
    )
    parser.add_argument("file", help="Scene file")
    parser.add_argument(
        "--quality", default="qh", choices=["ql", "qm", "qh", "qp", "qk"]
    )
    parser.add_argument("--output", default="final_output.mp4", help="Output filename")
    parser.add_argument(
        "--scenes", nargs="*", help="Override scene order (list of names)"
    )
    args = parser.parse_args()

    if args.scenes:
        scene_order = args.scenes
    else:
        scene_order = load_scene_order(args.file)

    print(f"\n  Scene order: {' → '.join(scene_order)}")

    video_files = render_all(args.file, scene_order, args.quality)
    concatenate(video_files, args.output)


if __name__ == "__main__":
    main()
