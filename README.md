# ManimCE Fast Development Workflow

A highly optimized development workflow for ManimCE that approximates 3b1b's ManimGL interactive experience — tailored for illustration-heavy content production.

## The Problem

ManimCE's default workflow is: edit → render entire scene → wait 30-120s → watch → repeat. For a channel producing complex, illustration-heavy content, this loop kills iteration speed and creative flow.

ManimGL solves this with live interactive reloading and `checkpoint_paste()`.

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
        "key": "cmd+shift+d",
        "command": "workbench.action.tasks.runTask",
        "args": "MCE: Run Scene at Cursor (Centered)",
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
| `Cmd+Shift+R` | **Run scene at cursor** — renders 2-3 animations forward from cursor `[idx, idx+2]` | mpv loops the rendered video clip |
| `Cmd+Shift+D` | **Run scene at cursor (centered)** — renders 3 animations centered on cursor `[idx-1, idx+1]` | mpv loops the rendered video clip |
| `Cmd+Shift+S` | **Snapshot at cursor** — renders exact scene state at cursor line as PNG (auto-checkpoint) | mpv shows the still image |
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
   - Auto-checkpoint ensures you see exactly the state at your cursor line

3. **Animation phase** — use `Cmd+Shift+R` (run at cursor):
   - Place cursor on or near the `self.play()` call you're tuning
   - It detects the animation index and renders 2-3 animations forward `[idx, idx+2]`
   - The video appears in mpv and loops so you can watch it repeatedly
   - Tweak timing, easing, transforms — press the shortcut again to see changes

4. **Polish phase** — use `Cmd+Shift+D` (centered run) to check transitions:
   - Renders 3 animations centered on cursor `[idx-1, idx+1]`
   - See how your animation connects with the one before and after it
   - Useful for fine-tuning timing and visual continuity between animations

5. **Review phase** — cursor on the class definition line, press `Cmd+Shift+R`:
   - When cursor is on the `class MyScene(Scene):` line, it renders the full scene
   - Watch the whole beat play through in mpv (looping)

6. **Polish + voiceover** — `Cmd+Shift+F` for high quality render.

### The mpv window in practice

Tile your screen: **VSCode on the left, mpv on the right.** Your eyes stay on the mpv window while your hands stay in the editor. The loop becomes:

```
edit code → Cmd+Shift+R → eyes shift to mpv (2-3s wait) → watch loop
→ "that easing is wrong" → edit code → Cmd+Shift+R → watch again
→ "does this connect well?" → Cmd+Shift+D → watch centered transition
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
"Does this look right spatially?"          → Ctrl+Shift+S  (snapshot at cursor → mpv shows image)
"Does this animation feel right?"          → Ctrl+Shift+R  (render at cursor → mpv loops video)
"How does this connect with neighbors?"    → Ctrl+Shift+D  (centered range → mpv loops video)
"Let me try something experimental"        → Paste in Dev scene → Ctrl+Shift+R
"How does the whole beat flow?"            → Cursor on class line → Ctrl+Shift+R
"Scene has no animations?"                 → Ctrl+Shift+R  (auto-detects → shows snapshot or skips)
"Ship it"                                  → python concat_render.py ... --quality qh
```

---

## Shortcut Behavior Reference

Detailed behavior of each shortcut depending on cursor position and scene content.

### `Ctrl+Shift+R` — Run Scene at Cursor

Renders the scene as **video** and sends it to the mpv preview window (looping). Uses a **forward-looking** animation range `[idx, idx+2]`.

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** as video | Looping video of entire scene |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **targeted video** of animations `[idx, idx+2]` | Looping video of ~3 animations starting at cursor |
| Inside scene, any line | No animations, has `self.add()` | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **Note:** Animation index is determined by the `self.play()` / `self.wait()` call at or just before the cursor line. `self.add()` calls are not animations and do not affect the index.

---

### `Ctrl+Shift+D` — Run Scene at Cursor (Centered)

Same as `Ctrl+Shift+R`, but uses a **centered** animation range `[idx-1, idx+1]` instead of forward-looking.

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** as video | Looping video of entire scene |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, on/near animation | Has animations | Renders **targeted video** of animations `[idx-1, idx+1]` | Looping video of ~3 animations centered on cursor |
| Inside scene, any line | No animations, has `self.add()` | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at cursor |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **Tip:** Use `Ctrl+Shift+R` when building new animations (forward context is more useful). Use `Ctrl+Shift+D` when polishing (see how your edit connects with surrounding animations).

---

### `Ctrl+Shift+S` — Snapshot at Cursor

Renders the scene as a **still image** (last frame as PNG) and sends it to mpv. Uses **auto-checkpoint** to stop execution at exactly the cursor line — no code leaking past the cursor.

| Cursor Position | Scene Content | Behavior | mpv Shows |
|---|---|---|---|
| On `class MyScene(Scene):` line | Has animations | Renders **full scene** last frame (`-s`) | Still image after all animations complete |
| On `class MyScene(Scene):` line | No animations, has `self.add()` | Renders **full scene** last frame (`-s`) | Still image of all added content |
| On `class MyScene(Scene):` line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |
| Inside scene, any line | Has animations | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at exactly that line |
| Inside scene, any line | No animations, has `self.add()` | **Auto-checkpoint snapshot** at cursor line | Still image of scene state at exactly that line |
| Inside scene, any line | No animations, no `self.add()` | Prints "nothing to preview" | Nothing sent to mpv |

> **How auto-checkpoint works:** Creates a temp copy of the scene file with `self.wait(0.01)` + `return` injected after the cursor line, then renders that copy with `-s`. This ensures execution stops at exactly the cursor position. The temp file is cleaned up automatically after rendering.

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
