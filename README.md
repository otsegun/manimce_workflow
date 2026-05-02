# ManimCE Fast Development Workflow

A highly optimized development workflow for ManimCE that approximates 3b1b's ManimGL interactive experience — tailored for illustration-heavy content production.

## The Problem

ManimCE's default workflow is: edit → render entire scene → wait 30-120s → watch → repeat. For a someone producing complex, illustration-heavy content, this loop kills iteration speed and creative flow.

ManimGL solves this with live interactive reloading and `checkpoint_paste()`. This project is an attempt to replicate that interactive experiences as much as possible using ManimCE. 

## The Solution

We engineer away the slow iteration loop using **four reinforcing strategies** plus a **persistent mpv preview window**:

| Strategy | What it does | ManimGL equivalent |
|---|---|---|
| Micro-scene decomposition | Each beat = one Scene class (3-5 animations) | Working on small code blocks |
| State reconstruction | `setup_state()` rebuilds prior state instantly | `checkpoint_paste()` state restore |
| Targeted rendering | `-n START,END` renders only specific animations | Running code from a checkpoint |
| Snapshot mode | `-s` renders only the last frame as PNG | Visual inspection without animation |
| **Checkpoint video** | Injects a `return` at cursor, renders video up to that exact line | Scrubbing to a point in the scene |
| **Persistent mpv window** | Single preview window that updates in-place | Interactive scene window |

Combined iteration loop: **edit → keyboard shortcut → 2-5 seconds → mpv updates in-place**.

---

## How the Preview Works

On your first `Cmd+Shift+R` or `Cmd+Shift+S`, the script:
1. Runs `manim render` (no `--preview` flag — we handle preview ourselves)
2. Checks if mpv is already running on the IPC socket at `/tmp/mpv-manim`
3. If not, spawns `mpv --idle --force-window --loop-file --input-ipc-server=/tmp/mpv-manim`
4. Waits for the socket to become ready (~0.5s, first time only)
5. Sends the rendered file to mpv via the IPC socket

On every subsequent shortcut press:
1. Runs `manim render`
2. mpv is already running — sends the new file immediately
3. mpv replaces whatever it's currently showing (video or image) with the new content

The mpv window stays open for your entire session. Videos loop automatically. Images display as stills. You can freely alternate between `Cmd+Shift+R` (video) and `Cmd+Shift+S` (image snapshot) — the same window handles both.

If you close mpv (or it crashes), the next shortcut press detects this, cleans up the stale socket, and spawns a fresh instance automatically.

---

## Setup

### 1. Install dependencies

```bash
pip install manim watchdog
```

mpv must be installed:
```bash
# macOS
brew install mpv

# Ubuntu/Debian
sudo apt install mpv

# Arch
sudo pacman -S mpv
```

### 2. Copy workflow files into your project

```
your-project/
├── mce_dev.py           # CLI tool (this repo)
├── concat_render.py     # Production render + concatenation
├── scene_patterns.py    # Reference patterns (copy what you need)
├── .vscode/
│   └── tasks.json       # VSCode task definitions
├── scenes/              # Your actual scene files
│   ├── ep01_beat01.py
│   └── ...
└── assets/              # SVGs, images
    └── ...
```

### 3. Configure VSCode keybindings

Open **Preferences → Keyboard Shortcuts → Open Keyboard Shortcuts (JSON)** and add:

```json
[
    {
        "key": "cmd+shift+r",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Run Scene at Cursor",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "ctrl+shift+d",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Run Scene at Cursor (Centered)",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "ctrl+shift+v",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Video to Cursor",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "cmd+shift+s",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Snapshot at Cursor",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "cmd+shift+l",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: List Scenes",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "cmd+shift+w",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Dev Watch Mode",
        "when": "editorTextFocus && editorLangId == python"
    },
    {
        "key": "cmd+shift+f",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Render Full Scene (High Quality)",
        "when": "editorTextFocus && editorLangId == python"
    }
]
```

**On Windows/Linux**, replace `cmd` with `ctrl`. Note that `Ctrl+Shift+D` and `Ctrl+Shift+V` use `ctrl` on all platforms (macOS included) to avoid conflicting with system shortcuts.

> **Note on Cmd+Shift+S:** This overrides the default "Save As" shortcut in VSCode. If you use Save As frequently, pick a different binding (e.g., `cmd+shift+p` for "preview snapshot"). The `when` clause limits the override to Python files only, so it won't affect other file types.

---

## Keyboard Shortcuts Reference

| Shortcut | Action | Preview behavior |
|---|---|---|
| `Cmd+Shift+R` | **Run scene at cursor** — renders animations `[idx, idx+2]` around cursor | mpv loops the rendered video clip |
| `Ctrl+Shift+D` | **Run scene at cursor (centered)** — renders `[idx-1, idx+1]`, centering on cursor animation | mpv loops the rendered video clip |
| `Ctrl+Shift+V` | **Video to cursor** — auto-checkpoint at exact cursor line, renders video up to that point | mpv loops video of scene up to cursor |
| `Cmd+Shift+S` | **Snapshot at cursor** — auto-checkpoint at exact cursor line, renders as PNG | mpv shows the still image |
| `Cmd+Shift+L` | **List scenes** — shows scenes, animation counts, sections in terminal | No mpv interaction |
| `Cmd+Shift+W` | **Watch mode** — auto-renders active scene on every file save | mpv updates on every save |
| `Cmd+Shift+F` | **Full render** — high quality render of a named scene | mpv shows the full render |

---

## Workflow In Practice

### Typical development session

1. **Open your scene file.** Place cursor inside the scene you're working on.

2. **Layout phase** — use `Cmd+Shift+S` (snapshot) repeatedly:
   - Position mobjects using `.shift()`, `.move_to()`, `.next_to()`
   - Adjust scales, colors, fonts
   - Each snapshot renders in <1s and the image appears in mpv instantly
   - You're only checking spatial relationships, not animation

3. **Animation phase** — use `Cmd+Shift+R` or `Ctrl+Shift+D` (run at cursor):
   - Place cursor on or near the `self.play()` call you're tuning
   - It detects the animation index and renders just 2-3 animations
   - The video appears in mpv and loops so you can watch it repeatedly
   - Tweak timing, easing, transforms — press the shortcut again to see changes

4. **Sequence check phase** — use `Ctrl+Shift+V` (video to cursor):
   - Place cursor anywhere in the scene — the rendered video covers everything from the start up to that exact line
   - Use this when you want to verify that a run of animations flows correctly, not just the 2-3 around the cursor
   - Equivalent to asking "does everything up to here look right?" rather than "does this one animation look right?"

5. **Review phase** — cursor on the class definition line, press `Cmd+Shift+R`:
   - When cursor is on the `class MyScene(Scene):` line, it renders the full scene
   - Watch the whole beat play through in mpv (looping)

6. **Polish + voiceover** — `Cmd+Shift+F` for high quality render.

### The mpv window in practice

Tile your screen: **VSCode on the left, mpv on the right.** Your eyes stay on the mpv window while your hands stay in the editor. The loop becomes:

```
edit code → Cmd+Shift+R → eyes shift to mpv (2-3s wait) → watch loop
→ "that easing is wrong" → edit code → Cmd+Shift+R → watch again
→ "positioning is off" → edit code → Cmd+Shift+S → see snapshot
→ "that's right" → Cmd+Shift+R → confirm with animation
→ "does the whole sequence flow?" → Ctrl+Shift+V → watch video up to cursor
```

You never switch windows, never open a file browser, never close a video player. The preview just *updates*.

---

## Scene Organization for Episodes

### Recommended structure

```python
# ep01_intro.py

class OpeningScene(Scene):
    """Beat 1.1"""
    def construct(self):
        self.next_section("opening")
        # ...

class FollowUpScene(Scene):
    """Beat 1.2 — picks up from opening scene"""
    def setup_state(self):
        # Reconstruct end state of previous scene (instant, no animation)
        self.character = SVGMobject("assets/character.svg").scale(0.8).shift(LEFT*3)
        self.add(self.character)

    def construct(self):
        self.setup_state()
        # Only the NEW animations below get rendered
        # ...

class Dev(Scene):
    """Scratch pad — paste experimental code here"""
    def construct(self):
        # Experiment freely, Cmd+Shift+R to see results
        pass

EPISODE_SCENE_ORDER = [
    "OpeningScene",
    "FollowUpScene",
    # ...
]
```

### Production render

```bash
python concat_render.py ep01_intro.py --quality qh --output ep01_final.mp4
```

---

## Tips

- **Always develop at `-ql`** (480p, 15fps). Only go higher for review/production.
- **Use `self.add()` not `self.play(FadeIn())`** for things that should already be on screen.
- **Keep a Dev scene** at the bottom of every file for quick experiments.
- **Pre-build SVG assets at the right scale.** Rescaling complex SVGs at render time is slow.
- **Snapshot (`-s`) renders the LAST frame.** If your scene ends blank, the snapshot is blank.
- **Animation indices are 0-based** and count every `self.play()` and `self.wait()`. Indices inside `for` loops are expanded automatically — a loop of 3 iterations with 1 `self.play()` inside counts as 3 animations.
- **`VoiceoverScene` is auto-detected.** Scenes subclassing `VoiceoverScene` are recognised alongside `Scene`, `MovingCameraScene`, `ThreeDScene`, `ZoomedScene`, and `VectorScene`.
- **If output looks stale**, delete the `media/` directory — cached partial movie files can become outdated when you change early animations.
- **The mpv window size** defaults to 960x540. Edit the `--geometry` flag in `mce_dev.py` to change it, or just resize the window manually (mpv remembers).
- **Add `._*_mce_checkpoint.py` to your `.gitignore`.** The snapshot command creates temporary checkpoint files in your scene directory. They are cleaned up automatically, but may linger if a render is killed hard.

### Checkpoint pattern for setup snapshots

Manim's targeted rendering (`-n`) works at the animation level. `self.add()` is instant
and doesn't create an animation index, so you can't snapshot at a specific `self.add()` line.

**Workaround:** Insert a near-instant `self.wait(0.01)` as a checkpoint. This creates a
targetable animation index with negligible render cost:

```python
def construct(self):
    a = Circle()
    self.add(a)
    self.wait(0.01)          # checkpoint — Cmd+Shift+S here shows just 'a'
    b = Square()
    self.add(b)
    self.wait(0.01)          # checkpoint — Cmd+Shift+S here shows 'a' + 'b'
    self.play(Create(c))     # anim 2 — Cmd+Shift+R here renders the animation
```

---

## Quick reference

```
"Does this look right spatially?"          → Cmd+Shift+S  (auto-checkpoint snapshot at cursor → mpv shows image)
"Does this animation feel right?"          → Cmd+Shift+R  (render [idx, idx+2] at cursor → mpv loops video)
"I want to see this animation in context"  → Ctrl+Shift+D (centered render [idx-1, idx+1] → mpv loops video)
"Does everything up to here flow right?"   → Ctrl+Shift+V (checkpoint video up to cursor → mpv loops video)
"Let me try something experimental"        → Paste in Dev scene → Cmd+Shift+R
"How does the whole beat flow?"            → Cursor on class line → Cmd+Shift+R
"Scene has no animations?"                 → Cmd+Shift+R  (auto-detects → auto-checkpoint snapshot or skips)
"Ship it"                                  → python concat_render.py ... --quality qh
```

---

## Shortcut Behavior Reference

Detailed behavior of each shortcut depending on cursor position and scene content.

### `Ctrl+Shift+R` — Run Scene at Cursor

Renders the scene as **video** and sends it to the mpv preview window (looping).

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** as video | Looping video of entire scene |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | Renders **full scene snapshot** | Still image of complete scene |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **targeted video** of animations `[idx, idx+2]` | Looping video of 2-3 animations around cursor |
| Inside scene, any line | No animations, has `self.add()` | Renders **auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **Note:** Animation index is determined by the `self.play()` / `self.wait()` call at or just before the cursor line. `self.add()` calls are not animations and do not affect the index. For scenes with `for` loops, iteration counts are inferred automatically so the index matches manim's runtime `-n` flag.

---

### `Ctrl+Shift+D` — Run Scene at Cursor (Centered)

Renders the scene as **video**, but centers the animation range on the cursor rather than starting at it. Sends result to the mpv preview window (looping).

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** as video | Looping video of entire scene |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | Renders **full scene snapshot** | Still image of complete scene |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **centered video** of animations `[idx-1, idx+1]` | Looping video of the animation at cursor + its neighbors |
| Inside scene, any line | No animations, has `self.add()` | Renders **auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **When to use `Ctrl+Shift+D` vs `Ctrl+Shift+R`:** Use `Ctrl+Shift+R` (`[idx, idx+2]`) when you're building forward and want to see what comes *after* the cursor. Use `Ctrl+Shift+D` (`[idx-1, idx+1]`) when you're tuning a specific animation and want to see it in context — one before and one after.

---

### `Ctrl+Shift+V` — Video to Cursor

Renders the scene as **video up to the cursor line** using the same checkpoint mechanism as `Ctrl+Shift+S`, but outputs video instead of an image. Sends result to the mpv preview window (looping).

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** as video | Looping video of entire scene |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | Renders **full scene snapshot** | Still image of complete scene |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **checkpoint video** from start of scene up to cursor line | Looping video of everything up to cursor |
| Inside scene, any line | No animations, has `self.add()` | Renders **auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **How it differs from `Ctrl+Shift+R`:** `Ctrl+Shift+R` renders a small window of 2-3 animations starting at the cursor — useful for fast iteration on a specific animation. `Ctrl+Shift+V` renders the full sequence from the beginning up to the cursor — useful for checking that a run of animations flows correctly as a whole. Both produce a video; only the scope differs.
>
> **How it differs from `Ctrl+Shift+S`:** Both use the same checkpoint injection (injecting `self.wait(0.01)` + `return` at the cursor line into a temp copy of the file). `Ctrl+Shift+S` adds `-s` for a still image of the last frame; `Ctrl+Shift+V` omits `-s` and keeps the video. Use `Ctrl+Shift+V` when timing and motion matter; use `Ctrl+Shift+S` when you only care about spatial layout.
>
> **Fallback:** If checkpoint injection fails, the tool falls back to `-n 0,{idx}` with a warning, rendering animations 0 through the index at the cursor.

---

### `Ctrl+Shift+S` — Snapshot at Cursor

Renders the scene as a **still image** (last frame as PNG) and sends it to mpv.

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** last frame (`-s`) | Still image after all animations complete |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | Renders **full scene snapshot** | Still image of complete scene |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **auto-checkpoint snapshot** at exact cursor line | Still image of scene state at cursor line |
| Inside scene, any line | No animations, has `self.add()` | Renders **auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **How auto-checkpoint works:** Instead of using `-n 0,{idx} -s`, the tool injects `self.wait(0.01)` and `return` into a temporary copy of your file immediately after the cursor line, then renders that copy with `-s`. This captures the **exact scene state at the cursor** — including any `self.add()` calls up to that line — with no trailing code running. The temp file (`._<filename>_mce_checkpoint.py`) is created in your scene directory and automatically deleted after the render completes.
>
> **Fallback:** If checkpoint injection fails (e.g., cursor is outside a `construct()` body), the tool falls back to the `-n 0,{idx} -s` approach with a warning.

---

### `Ctrl+Alt+L` — List Scenes

Lists all Scene classes in the current file with metadata. **Cursor position does not matter** — it always scans the entire file.

| Output | Description |
|---|---|
| Scene name | Each `Scene` subclass found in the file |
| Line range | Start and end lines of the class definition |
| Animation count | Number of `self.play()`, `self.wait()` calls in `construct()` |
| Section count | Number of `self.next_section()` calls |
| Section names | Names and line numbers of each section |

No rendering occurs. Nothing is sent to mpv.

---

### `Ctrl+Alt+W` — Dev Watch Mode

Watches the current file for changes and **auto-renders on every save**. Runs as a background process.

| Aspect | Behavior |
|---|---|
| Trigger | Every file save (debounced at 1.5s) |
| Active scene | First scene in file by default, or specified via `--scene` flag |
| Configuration | Edit `.mce_dev_state.json` in the scene directory to change scene, quality, or mode |
| Modes | `"full"` (render full scene), `"snapshot"` (last frame), `"range"` (animation range) |
| Preview | Automatically sent to mpv on each render |
| Stop | `Ctrl+C` in the terminal |

---

### `Ctrl+Alt+F` — Render Full Scene (High Quality)

Prompts for a scene name and renders it at **high quality** (`-qh`, 1080p 60fps by default).

| Aspect | Behavior |
|---|---|
| Scene selection | Prompted via input dialog (not cursor-based) |
| Quality | High quality (`-qh`) by default, configurable |
| Preview | Full render sent to mpv |
| Use case | Final review before production render |
