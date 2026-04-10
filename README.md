# ManimCE Fast Development Workflow

A highly optimized development workflow for ManimCE that approximates 3b1b's ManimGL interactive experience — tailored for illustration-heavy finance content production.

## The Problem

ManimCE's default workflow is: edit → render entire scene → wait 30-120s → watch → repeat. For a channel producing complex, illustration-heavy content, this loop kills iteration speed and creative flow.

ManimGL solves this with live interactive reloading and `checkpoint_paste()`, but has poor SVG support and no manim-voiceover integration — dealbreakers for illustration-driven content.

## The Solution

We keep ManimCE (stable SVGs, voiceover, math support, Cairo renderer) and engineer away the slow iteration loop using **four reinforcing strategies** plus a **persistent mpv preview window**:

| Strategy | What it does | ManimGL equivalent |
|---|---|---|
| Micro-scene decomposition | Each beat = one Scene class (3-5 animations) | Working on small code blocks |
| State reconstruction | `setup_state()` rebuilds prior state instantly | `checkpoint_paste()` state restore |
| Targeted rendering | `-n START,END` renders only specific animations | Running code from a checkpoint |
| Snapshot mode | `-s` renders only the last frame as PNG | Visual inspection without animation |
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

**On Windows/Linux**, replace `cmd` with `ctrl`.

> **Note on Cmd+Shift+S:** This overrides the default "Save As" shortcut in VSCode. If you use Save As frequently, pick a different binding (e.g., `cmd+shift+p` for "preview snapshot"). The `when` clause limits the override to Python files only, so it won't affect other file types.

---

## Keyboard Shortcuts Reference

| Shortcut | Action | Preview behavior |
|---|---|---|
| `Cmd+Shift+R` | **Run scene at cursor** — renders 2-3 animations around cursor position | mpv loops the rendered video clip |
| `Cmd+Shift+S` | **Snapshot at cursor** — renders final frame as PNG | mpv shows the still image |
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

3. **Animation phase** — use `Cmd+Shift+R` (run at cursor):
   - Place cursor on or near the `self.play()` call you're tuning
   - It detects the animation index and renders just 2-3 animations
   - The video appears in mpv and loops so you can watch it repeatedly
   - Tweak timing, easing, transforms — press the shortcut again to see changes

4. **Review phase** — cursor on the class definition line, press `Cmd+Shift+R`:
   - When cursor is on the `class MyScene(Scene):` line, it renders the full scene
   - Watch the whole beat play through in mpv (looping)

5. **Polish + voiceover** — `Cmd+Shift+F` for high quality render.

### The mpv window in practice

Tile your screen: **VSCode on the left, mpv on the right.** Your eyes stay on the mpv window while your hands stay in the editor. The loop becomes:

```
edit code → Cmd+Shift+R → eyes shift to mpv (2-3s wait) → watch loop
→ "that easing is wrong" → edit code → Cmd+Shift+R → watch again
→ "positioning is off" → edit code → Cmd+Shift+S → see snapshot
→ "that's right" → Cmd+Shift+R → confirm with animation
```

You never switch windows, never open a file browser, never close a video player. The preview just *updates*.

---

## Scene Organization for Episodes

### Recommended structure

```python
# ep01_corporate_finance.py

class PersonalSavingsScene(Scene):
    """Beat 1.1"""
    def construct(self):
        self.next_section("savings_intro")
        # ...

class DebtFinancingScene(Scene):
    """Beat 1.2 — picks up from savings scene"""
    def setup_state(self):
        # Reconstruct end state of previous scene (instant, no animation)
        self.yufei = SVGMobject("assets/yufei.svg").scale(0.8).shift(LEFT*3)
        self.add(self.yufei)

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
    "PersonalSavingsScene",
    "DebtFinancingScene",
    # ...
]
```

### Production render

```bash
python concat_render.py ep01_corporate_finance.py --quality qh --output ep01_final.mp4
```

---

## Tips

- **Always develop at `-ql`** (480p, 15fps). Only go higher for review/production.
- **Use `self.add()` not `self.play(FadeIn())`** for things that should already be on screen.
- **Keep a Dev scene** at the bottom of every file for quick experiments.
- **Pre-build SVG assets at the right scale.** Rescaling complex SVGs at render time is slow.
- **Snapshot (`-s`) renders the LAST frame.** If your scene ends blank, the snapshot is blank.
- **Animation indices are 0-based** and count every `self.play()` and `self.wait()`.
- **If output looks stale**, delete the `media/` directory — cached partial movie files can become outdated when you change early animations.
- **The mpv window size** defaults to 960x540. Edit the `--geometry` flag in `mce_dev.py` to change it, or just resize the window manually (mpv remembers).

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
"Does this look right spatially?"          → Cmd+Shift+S  (snapshot at cursor → mpv shows image)
"Does this animation feel right?"          → Cmd+Shift+R  (render at cursor → mpv loops video)
"Let me try something experimental"        → Paste in Dev scene → Cmd+Shift+R
"How does the whole beat flow?"            → Cursor on class line → Cmd+Shift+R
"Scene has no animations?"                 → Cmd+Shift+R  (auto-detects → shows snapshot or skips)
"Ship it"                                  → python concat_render.py ... --quality qh
```
