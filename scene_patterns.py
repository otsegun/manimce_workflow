"""
ManimCE Fast Iteration Patterns
================================
This file demonstrates the coding patterns that make the optimized
workflow actually work. The tooling (mce_dev.py) is only half the
story — the other half is how you structure your scene code.


THE KEY INSIGHT:
    3b1b's checkpoint_paste() works because it can save and restore
    scene state at arbitrary points. ManimCE can't do this directly.
    But we can achieve the same effect through CODE STRUCTURE:

    1. Micro-scenes: One conceptual beat = one Scene class
    2. State reconstruction: A setup() method that rebuilds state instantly
    3. Section markers: self.next_section() for partial movie files
    4. Animation indices: -n flag to skip to specific animations

    Combined, these let you iterate on any 3-5 second chunk of your
    video in under 5 seconds of render time.
"""

from manim import *


# ══════════════════════════════════════════════════════════════════════
# PATTERN 1: MICRO-SCENE DECOMPOSITION
# ══════════════════════════════════════════════════════════════════════
#
# Instead of one giant scene, decompose into small scenes that each
# handle one conceptual beat. Each scene renders in seconds.
#
# Map this directly to your animation spec:
#   Beat 1.1 → PersonalSavingsScene
#   Beat 1.2 → DebtFinancingScene
#   Beat 2.1 → EquityIntroScene
#   etc.
#
# When you need the "final" video, you render them all and concatenate.
# During development, you only render the one you're working on.


class PersonalSavingsScene(Scene):
    """Beat 1.1: Yufei starts FeiCoffee with personal savings."""

    def construct(self):
        self.next_section("savings_intro")

        # -- Setup (instant, no animations) --
        title = Text("Personal Savings", font_size=36).to_edge(UP)
        yufei = SVGMobject("assets/yufei_silhouette.svg").scale(0.8).shift(LEFT * 3)
        piggy = SVGMobject("assets/piggybank.svg").scale(0.5).shift(RIGHT * 2)

        # -- Animate --
        self.play(FadeIn(title))                          # anim 0
        self.play(FadeIn(yufei))                          # anim 1
        self.play(yufei.animate.shift(RIGHT), FadeIn(piggy))  # anim 2

        self.next_section("savings_pie")

        # Pie chart showing savings breakdown
        savings = 50000
        pie_data = [
            ("Equipment", 15000, BLUE),
            ("Rent", 20000, GREEN),
            ("Inventory", 10000, ORANGE),
            ("Reserve", 5000, GRAY),
        ]
        # ... pie chart animation ...
        self.wait(1)                                      # anim 3


class DebtFinancingScene(Scene):
    """Beat 1.2: Yufei borrows from Uncle Lee."""

    def construct(self):
        # This scene picks up where PersonalSavingsScene left off.
        # We rebuild the ending state of the previous scene WITHOUT
        # animation, then animate the new content.

        # -- State reconstruction (instant) --
        yufei = SVGMobject("assets/yufei_silhouette.svg").scale(0.8).shift(LEFT * 1)
        shop = SVGMobject("assets/coffee_shop.svg").scale(0.6).shift(RIGHT * 2)
        self.add(yufei, shop)  # add without animation = instant

        self.next_section("uncle_lee_intro")

        # -- New content for this beat --
        uncle = SVGMobject("assets/uncle_lee.svg").scale(0.7).shift(LEFT * 4)
        self.play(FadeIn(uncle))                          # anim 0
        # ... debt financing animations ...


# ══════════════════════════════════════════════════════════════════════
# PATTERN 2: STATE RECONSTRUCTION WITH setup_state()
# ══════════════════════════════════════════════════════════════════════
#
# This is the closest equivalent to checkpoint_paste()'s state saving.
# A setup_state() method reconstructs the scene to a known point
# WITHOUT any animations (using self.add, .set, .move_to, etc.)
#
# This means rendering starts from the animations you care about,
# not from the beginning of the scene.


class EquityIntroScene(Scene):
    """Demonstrates state reconstruction pattern."""

    def setup_state(self):
        """
        Reconstruct scene to the state at the START of this beat.
        Everything here is instant (no self.play calls).

        This is your "checkpoint" — equivalent to the state that
        checkpoint_paste() would save.
        """
        # Characters
        self.yufei = SVGMobject("assets/yufei_silhouette.svg").scale(0.8).shift(LEFT * 3)
        self.shop = SVGMobject("assets/coffee_shop.svg").scale(0.6)

        # Previously established info
        self.debt_label = Text("Debt: $30,000", font_size=24).to_corner(UR)

        # Add everything to scene (instant, no animation)
        self.add(self.yufei, self.shop, self.debt_label)

    def construct(self):
        self.setup_state()  # Instant state reconstruction

        self.next_section("equity_explain")

        # Now the only thing that renders is the NEW content:
        auntie = SVGMobject("assets/auntie_wang.svg").scale(0.7).shift(RIGHT * 3)
        self.play(FadeIn(auntie))                         # anim 0

        # Show equity concept
        pie = Circle(radius=1.5, color=WHITE).shift(DOWN)
        yufei_share = Sector(arc_center=pie.get_center(), outer_radius=1.5,
                             angle=270 * DEGREES, start_angle=90 * DEGREES,
                             color=BLUE, fill_opacity=0.7)
        auntie_share = Sector(arc_center=pie.get_center(), outer_radius=1.5,
                              angle=90 * DEGREES, start_angle=0 * DEGREES,
                              color=ORANGE, fill_opacity=0.7)

        self.play(Create(pie))                            # anim 1
        self.play(FadeIn(yufei_share), FadeIn(auntie_share))  # anim 2
        self.wait(1)                                      # anim 3

        self.next_section("equity_labels")

        y_label = Text("Yufei: 75%", font_size=20, color=BLUE).next_to(yufei_share, LEFT)
        a_label = Text("Auntie: 25%", font_size=20, color=ORANGE).next_to(auntie_share, RIGHT)
        self.play(Write(y_label), Write(a_label))         # anim 4

        # ITERATION TIP:
        # If you're only working on the labels (anim 4), run:
        #   python mce_dev.py render_range scenes.py EquityIntroScene 4 4
        # This skips anims 0-3 entirely. Sub-second render.


# ══════════════════════════════════════════════════════════════════════
# PATTERN 3: DEV SCENE (SCRATCH PAD)
# ══════════════════════════════════════════════════════════════════════
#
# A throwaway scene for testing visual ideas quickly.
# This is the closest analogue to "copy code + checkpoint_paste()":
# you paste whatever you're experimenting with into construct(),
# and it renders in isolation.


class Dev(Scene):
    """
    Scratch scene for rapid experimentation.
    Paste whatever you're iterating on into construct().
    Render with: manim -ql -s scenes.py Dev   (snapshot)
                 manim -ql scenes.py Dev       (animated)

    Keyboard shortcut: Place cursor here, press Cmd+Shift+R
    """

    def construct(self):
        # ---- PASTE YOUR EXPERIMENTAL CODE BELOW ----

        # Testing pie chart component
        pie = Circle(radius=1.5, color=WHITE)
        wedge = Sector(
            arc_center=ORIGIN, outer_radius=1.5,
            angle=120 * DEGREES, start_angle=90 * DEGREES,
            color=BLUE, fill_opacity=0.7
        )
        self.play(Create(pie))
        self.play(FadeIn(wedge))
        self.wait(0.5)

        # ---- END EXPERIMENTAL CODE ----


# ══════════════════════════════════════════════════════════════════════
# PATTERN 4: REUSABLE COMPONENTS AS FUNCTIONS
# ══════════════════════════════════════════════════════════════════════
#
# Build your reusable visual components (pie charts, flow diagrams,
# character rigs) as standalone functions or classes. Test them in
# the Dev scene. Import into production scenes once stable.
#
# This is in a separate file in practice (e.g., components.py),
# shown inline here for illustration.


def create_pie_chart(data: list[tuple[str, float, str]], radius=1.5,
                     center=ORIGIN, show_labels=True) -> VGroup:
    """
    Reusable pie chart component.

    Args:
        data: List of (label, value, color) tuples
        radius: Chart radius
        center: Center position
        show_labels: Whether to include labels

    Returns:
        VGroup containing all pie chart mobjects
    """
    total = sum(v for _, v, _ in data)
    group = VGroup()
    start_angle = 90 * DEGREES

    for label, value, color in data:
        angle = (value / total) * TAU
        sector = Sector(
            arc_center=center, outer_radius=radius,
            angle=angle, start_angle=start_angle,
            color=color, fill_opacity=0.7,
            stroke_width=2, stroke_color=WHITE,
        )
        group.add(sector)

        if show_labels:
            mid_angle = start_angle + angle / 2
            label_pos = center + (radius + 0.5) * np.array([
                np.cos(mid_angle), np.sin(mid_angle), 0
            ])
            pct = f"{value/total*100:.0f}%"
            text = Text(f"{label}\n{pct}", font_size=16, color=color)
            text.move_to(label_pos)
            group.add(text)

        start_angle += angle

    return group


def create_flow_arrow(start_mob, end_mob, label_text="", color=WHITE) -> VGroup:
    """Reusable labeled arrow between two mobjects."""
    arrow = Arrow(start_mob.get_right(), end_mob.get_left(), color=color, buff=0.2)
    group = VGroup(arrow)
    if label_text:
        label = Text(label_text, font_size=18, color=color)
        label.next_to(arrow, UP, buff=0.1)
        group.add(label)
    return group


# ══════════════════════════════════════════════════════════════════════
# PATTERN 5: CONCATENATION SCENE ORDER
# ══════════════════════════════════════════════════════════════════════
#
# For final rendering, define the scene order in a config-like manner.
# A simple script (concat_scenes.py) renders them all and concatenates
# using ffmpeg.

EPISODE_ONE_SCENE_ORDER = [
    "PersonalSavingsScene",
    "DebtFinancingScene",
    "EquityIntroScene",
    # "BankLoanScene",
    # "InvestmentBankScene",
    # "IPOScene",
    # "EpilogueScene",
]


# ══════════════════════════════════════════════════════════════════════
# PATTERN 6: SECTION MARKERS FOR NAVIGATION
# ══════════════════════════════════════════════════════════════════════
#
# Even within micro-scenes, use self.next_section() to create
# independently addressable chunks. ManimCE writes separate partial
# movie files for each section, which means:
#
# 1. You can preview individual sections without the others
# 2. The file watcher can target sections
# 3. You build a "table of contents" into your scene code
#
# Pro tip: Name sections descriptively. They appear in the media/
# output directory and serve as your visual storyboard.
