"""原创导数图解：连续几何变化、局部放大与公式变换。"""

import json
import os
from pathlib import Path
from manim import *

BG = "#101010"
SOFT = "#EEEEEE"
MUTED = "#888888"
CURVE = "#58C4DD"
GOLD = "#FFFF00"
RISE = "#83C167"
SECOND = "#FC6255"
FONT = os.environ.get("EXPLAINER_FONT", "Microsoft YaHei")


def words(text, size=25, color=SOFT):
    return Text(text, font=FONT, font_size=size, color=color, disable_ligatures=True)


class ExplainerScene(MovingCameraScene):
    def construct(self):
        self.timeline = json.loads(Path(os.environ["EXPLAINER_TIMELINE"]).read_text(encoding="utf-8"))
        self.camera.background_color = BG
        self.camera.frame.save_state()
        self.h = ValueTracker(1)
        self.caption = None
        for beat in self.timeline["beats"]:
            self.say(beat, getattr(self, "show_" + beat["id"]))

    def say(self, beat, action):
        if self.caption is not None:
            self.caption.clear_updaters()
            self.remove(self.caption)
        text = words(beat["caption"], 23)
        if text.width > 12.6:
            text.scale_to_fit_width(12.6)
        backdrop = Rectangle(width=14.3, height=0.68, stroke_width=0, fill_color=BG, fill_opacity=1)
        self.caption = VGroup(backdrop, text).set_z_index(100)
        self.caption.add_updater(lambda m: m.scale_to_fit_width(self.camera.frame.width + 0.02).move_to(
            self.camera.frame.get_bottom() + UP * (0.42 * self.camera.frame.width / 14.2222)))
        self.add(self.caption)
        action()
        remaining = round(beat["end"] - self.time, 8)
        if remaining < -1 / config.frame_rate:
            raise RuntimeError(f"分镜 {beat['id']} 超过旁白时长，请增大 min_seconds 或缩短动作。")
        if remaining > 0:
            self.wait(remaining)

    def show_intro(self):
        self.question = words("一个点，\n怎么谈变化？", 49).move_to(ORIGIN + UP * 0.55)
        self.intro_label = words("导数的几何直觉", 23, MUTED).move_to(UP * 2.7)
        self.intro_arrow = words("两个点  →  一个点", 31, CURVE).move_to(DOWN * 1.5)
        self.play(FadeIn(self.intro_label), Write(self.question), run_time=1.2)
        self.play(Write(self.intro_arrow), run_time=1.0)

    def show_curve(self):
        self.play(FadeOut(VGroup(self.question, self.intro_label, self.intro_arrow)), run_time=0.55)
        self.axes = Axes(x_range=[0, 2.6, 0.5], y_range=[0, 6, 1], x_length=7.0, y_length=4.75,
                         tips=False, axis_config={"color": MUTED, "stroke_width": 1.3}).move_to([-2.7, -0.1, 0])
        self.graph = self.axes.plot(lambda x: x*x, x_range=[0, 2.42], color=CURVE, stroke_width=4)
        self.graph_label = MathTex("f(x)=x^2", color=CURVE, font_size=32).move_to(self.axes.c2p(1.45, 5.45))
        self.p = Dot(self.axes.c2p(1, 1), color=GOLD, radius=0.075)
        self.p_label = MathTex("P", color=GOLD, font_size=29).next_to(self.p, UL, buff=0.15)
        self.p_coordinates = MathTex("(1,1)", color=GOLD, font_size=31).move_to([3.65, 0.5, 0])
        self.side_heading = words("先固定一个点", 25, MUTED).move_to([3.65, 1.8, 0])
        labels = [MathTex("x", color=MUTED, font_size=24).next_to(self.axes.x_axis, RIGHT, buff=0.1),
                  MathTex("y", color=MUTED, font_size=24).next_to(self.axes.y_axis, UP, buff=0.1)]
        for x in (1, 2):
            labels.append(MathTex(str(x), color=MUTED, font_size=24).next_to(self.axes.c2p(x, 0), DOWN, buff=0.12))
        for y in (1, 4):
            labels.append(MathTex(str(y), color=MUTED, font_size=24).next_to(self.axes.c2p(0, y), LEFT, buff=0.12))
        self.axis_labels = VGroup(*labels)
        self.play(Create(self.axes), Create(self.graph), FadeIn(self.axis_labels), run_time=1.5)
        self.play(FadeIn(self.graph_label), FadeIn(self.p), Write(self.p_label), FadeIn(self.side_heading), Write(self.p_coordinates), run_time=1.0)

    def show_second(self):
        self.q = always_redraw(lambda: Dot(self.axes.c2p(1+self.h.get_value(), (1+self.h.get_value())**2), color=SECOND, radius=0.075))
        self.q_label = always_redraw(lambda: MathTex("Q", font_size=29, color=SECOND).next_to(self.q, UR, buff=0.15).set_opacity(min(1, abs(self.h.get_value())/0.1)))
        self.secant = always_redraw(lambda: Line(self.axes.c2p(0.3, 1+(2+self.h.get_value())*(0.3-1)),
                                                self.axes.c2p(2.35, 1+(2+self.h.get_value())*(2.35-1)), color=SECOND, stroke_width=3))
        self.dx_line = always_redraw(lambda: DashedLine(self.axes.c2p(1, 1), self.axes.c2p(1+self.h.get_value(), 1), color=GOLD, stroke_width=2))
        self.dy_line = always_redraw(lambda: DashedLine(self.axes.c2p(1+self.h.get_value(), 1), self.axes.c2p(1+self.h.get_value(), (1+self.h.get_value())**2), color=RISE, stroke_width=2))
        self.dx_label = always_redraw(lambda: MathTex("h", font_size=29, color=GOLD).move_to(self.dx_line.get_center()+DOWN*0.22).set_opacity(min(1, abs(self.h.get_value())/0.15)))
        self.dy_label = always_redraw(lambda: MathTex(r"\Delta y", font_size=27, color=RISE).move_to(self.dy_line.get_center()+RIGHT*0.40).set_opacity(min(1, abs(self.h.get_value())/0.15)))
        self.play(FadeOut(self.p_coordinates), FadeIn(self.q), FadeIn(self.q_label), Create(self.secant), run_time=1.2)
        self.play(FadeIn(self.dx_line), FadeIn(self.dy_line), FadeIn(self.dx_label), FadeIn(self.dy_label), run_time=0.8)

    def show_average(self):
        new_heading = words("平均变化率", 25, MUTED).move_to(self.side_heading)
        colored_tex = TexTemplate()
        colored_tex.add_to_preamble(r"\usepackage{xcolor}")
        self.ratio = MathTex(r"\frac{\color[HTML]{83C167}\Delta y}{\color[HTML]{FFFF00}h}", "=", "3", font_size=52, tex_template=colored_tex).move_to([3.65, 0.5, 0])
        self.ratio[2].set_color(SECOND)
        self.average_note = MathTex(r"\frac{3}{1}=3", font_size=34, color=MUTED).move_to([3.65, -1.0, 0])
        self.play(Transform(self.side_heading, new_heading), Write(self.ratio), run_time=1.1)
        self.play(Write(self.average_note), Indicate(self.dy_line, color=RISE), Indicate(self.dx_line, color=GOLD), run_time=1.4)

    def show_near(self):
        self.play(FadeOut(self.ratio), FadeOut(self.average_note), FadeOut(self.side_heading), run_time=0.5)
        slope_label = MathTex("m=", font_size=32, color=MUTED)
        slope_number = DecimalNumber(3, num_decimal_places=2, font_size=32, color=SECOND)
        slope_number.add_updater(lambda m: m.set_value(2+self.h.get_value()))
        self.live_slope = VGroup(slope_label, slope_number)
        def place_counter(group):
            scale = self.camera.frame.width / 14.2222
            group.arrange(RIGHT, buff=0.12).scale_to_fit_height(0.40*scale)
            group.move_to(self.camera.frame.get_corner(UL)+RIGHT*0.55*scale+DOWN*0.6*scale, aligned_edge=UL)
        self.live_slope.add_updater(place_counter)
        self.add(self.live_slope)
        focus = self.p.get_center() + RIGHT*0.65 + UP*0.5
        self.play(self.camera.frame.animate.set(width=6.0).move_to(focus), self.h.animate.set_value(0.5), run_time=2.2)
        self.play(self.h.animate.set_value(0.1), run_time=2.2)

    def show_delta(self):
        self.live_slope.clear_updaters()
        self.play(FadeOut(self.live_slope), run_time=0.25)
        self.play(self.camera.frame.animate.restore(), self.h.animate.set_value(0.5), run_time=1.6)
        heading = words("让间隔逐渐缩小", 25, MUTED).move_to([3.65, 1.8, 0])
        self.side_heading = heading
        self.fraction = MathTex(r"\frac{f(1+h)-f(1)}{h}", font_size=42).move_to([3.65, 0.4, 0])
        self.nonzero = MathTex(r"h\ne0", font_size=30, color=GOLD).move_to([3.65, -1.3, 0])
        self.play(FadeIn(heading), Write(self.fraction), FadeIn(self.nonzero), run_time=1.2)

    def show_formula(self):
        steps = [r"\frac{(1+h)^2-1}{h}", r"\frac{2h+h^2}{h}", "2+h"]
        for expression in steps:
            new = MathTex(expression, font_size=44).move_to(self.fraction)
            self.play(TransformMatchingTex(self.fraction, new), run_time=1.1)
            self.fraction = new
        self.fraction.set_color(GOLD)

    def show_limit(self):
        self.limit_text = MathTex(r"h\to0\quad\Longrightarrow\quad2+h\to2", font_size=31, color=GOLD).move_to([3.6, -0.65, 0])
        self.play(Write(self.limit_text), run_time=0.7)
        self.play(self.h.animate.set_value(0.02), run_time=1.9)
        self.play(FadeOut(self.q), FadeOut(self.q_label), FadeOut(self.secant), FadeOut(self.dx_line), FadeOut(self.dy_line), FadeOut(self.dx_label), FadeOut(self.dy_label), run_time=0.4)
        self.h.set_value(-0.4)
        self.play(FadeIn(self.q), FadeIn(self.q_label), FadeIn(self.secant), FadeIn(self.dx_line), FadeIn(self.dy_line), FadeIn(self.dx_label), FadeIn(self.dy_label), run_time=0.4)
        self.play(self.h.animate.set_value(-0.02), run_time=1.9)

    def show_tangent(self):
        self.tangent = Line(self.axes.c2p(0.25, 1+2*(0.25-1)), self.axes.c2p(2.35, 1+2*(2.35-1)), color=GOLD, stroke_width=4)
        self.play(FadeOut(self.secant), FadeOut(self.q), FadeOut(self.q_label), FadeOut(self.dx_line), FadeOut(self.dy_line), FadeOut(self.dx_label), FadeOut(self.dy_label), run_time=0.5)
        self.play(Create(self.tangent), run_time=1.0)
        result = MathTex("f'(1)", "=", "2", font_size=58, color=GOLD).move_to([3.65, 0.45, 0])
        self.play(FadeOut(self.fraction), FadeOut(self.limit_text), FadeOut(self.nonzero),
                  Transform(self.side_heading, words("切线的斜率", 25, MUTED).move_to(self.side_heading)), Write(result), run_time=1.0)
        self.result = result

    def show_application(self):
        predicted = MathTex(r"\Delta y\approx f'(1)\,\Delta x", font_size=35).move_to([3.65, -0.65, 0])
        numbers = MathTex(r"0.02\approx2\times0.01", font_size=35, color=RISE).move_to([3.65, -1.6, 0])
        exact = words("实际变化：0.0201", 20, MUTED).move_to([3.65, -2.35, 0])
        self.play(Write(predicted), run_time=0.9)
        self.play(Write(numbers), FadeIn(exact), run_time=1.0)

    def show_close(self):
        contents = Group(*[m for m in self.mobjects if m is not self.caption])
        self.play(FadeOut(contents), run_time=0.7)
        heading = words("从两点的变化，走向一点的斜率", 31).move_to(UP*2.0)
        definition = MathTex(r"f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}", font_size=49).move_to(ORIGIN)
        condition = words("极限存在时", 23, MUTED).move_to(DOWN*1.55)
        self.play(Write(heading), Write(definition), run_time=1.3)
        self.play(FadeIn(condition), run_time=0.6)
