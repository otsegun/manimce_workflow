# test_workflow.py
from manim import *


class TestA(Scene):
    def construct(self):
        c = Circle(color=GREEN)
        self.play(Create(c))  # anim 0
        self.play(c.animate.shift(UP))  # anim 1
        self.wait(0.5)  # anim 2


class TestB(Scene):
    def construct(self):
        s = Square(color=RED)
        self.add(s)  # instant, no animation
        self.play(s.animate.rotate(PI / 4))  # anim 0


class TestTargeted(Scene):
    def construct(self):
        a = Circle(color=BLUE)
        b = Square(color=RED)
        c = Triangle(color=GREEN)

        self.play(Create(a))  # anim 0
        self.play(a.animate.shift(LEFT * 2))  # anim 1
        self.play(Create(b))  # anim 2
        self.play(b.animate.shift(RIGHT * 2))  # anim 3
        self.play(Create(c))  # anim 4
        self.play(c.animate.shift(UP * 2))  # anim 5
        self.wait(1)  # anim 6


class TestStaticContent(Scene):
    """Has self.add() but no animations — should render as snapshot."""

    def construct(self):
        a = Circle(color=BLUE)
        b = Square(color=RED).shift(RIGHT * 2)
        self.add(a)
        # self.wait(1)
        # self.wait(1)
        self.add(b)


class TestEmpty(Scene):
    """No animations, no self.add() — truly empty, skip mpv."""

    def construct(self):
        a = Circle(color=BLUE)  # created but never added
