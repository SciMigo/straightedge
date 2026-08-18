from __future__ import annotations

import re

from .calculus import (
    ConceptCalculus,
    is_derivative_request,
    is_ftc_request,
    is_integral_request,
    is_taylor_request,
)
from .conics import ConceptConic
from .expr import parse_function, pretty_expr
from .linalg import VIEWS, ConceptLinAlg
from .models import AnimationPlan, Topic
from .topics import detect, plan_builder, plan_for
from .solids3d import (
    Concept3D,
    SolidSpec,
    is_three_views_request,
    parse_section_points,
    parse_solid_spec,
    solid_title_zh,
)
from .trig import Concept as ConceptTrig, TrigSpec, parse_trig_spec, trig_func_zh


def plan_from_template(template: str,
                       parameters: dict | None = None) -> AnimationPlan:
    """Build a plan for a named animation template, bypassing the request router.

    The keyword router in :func:`build_plan` is Chinese-first, so the obvious
    English prompt for ``calculus/derivative_tangent`` does not reach it. Naming
    the template does — every shipped animation is reachable this way, in any
    language, with no LLM. It is the counterpart to :func:`~straightedge.catalog.
    list_templates`: that says what exists, this takes one of those ids back.

    ``template`` is an animation id from the catalog — either a topic
    (``geometry``) or a concept (``conic/ellipse_foci``). Figure templates are a
    different lane and are drawn with :func:`straightedge.diagrams.render_diagram`
    instead; naming one here is refused rather than silently mis-rendered.

    Scene builders default anything ``parameters`` leaves out — the frame above
    is ``conic/ellipse_foci`` with no parameters at all — so a bare template id
    renders a complete scene, and ``parameters`` only refines it.
    """
    from .catalog import list_templates
    from .errors import StraightedgeError

    animation_ids = {t.id for t in list_templates() if t.lane == "animation"}
    if template not in animation_ids:
        raise StraightedgeError(
            f"No animation template named {template!r}.",
            remedy="Run `straightedge list-templates` to see the ids; note "
                   "figure templates are drawn with render_diagram, not this.",
            details={"template": template})

    topic, _, concept = template.partition("/")
    return AnimationPlan(
        topic=topic,
        title_zh="",
        objective_zh="",
        english_prompt=f"template:{template}",
        concept=template if concept else None,
        parameters=dict(parameters or {}),
    )


def build_plan(chinese_request: str) -> AnimationPlan:
    request = _normalize(chinese_request)

    # Order matters here: these specific conic/trig concepts share vocabulary
    # with the calculus keywords (焦点/面积/积分), so they must claim the request
    # before _calculus_plan_for_request runs below. Keep the most specific
    # detectors first.
    if _is_unit_circle_to_sine(request):
        return _unit_circle_to_sine_plan(request)
    if _is_parabola_focus_directrix(request):
        return _parabola_focus_directrix_plan(request)
    if _is_ellipse_foci(request):
        return _ellipse_foci_plan(request)

    # An explicit y=/f(x)= formula is plotted directly, regardless of topic.
    # Trig transformations ``A·f(ωx+φ)+k`` go to the annotated trig scene;
    # anything else falls through to the generic function grapher.
    expression = parse_function(request)
    if expression is not None:
        calculus_plan = _calculus_plan_for_request(request, expression)
        if calculus_plan is not None:
            return calculus_plan
        trig_spec = parse_trig_spec(expression)
        if trig_spec is not None:
            return _trig_transform_plan(request, expression, trig_spec)
        return _function_plan(request, expression)

    calculus_plan = _calculus_plan_for_request(request, None)
    if calculus_plan is not None:
        return calculus_plan

    topic = _detect_topic(request)
    return (plan_builder(topic) or _geometry_plan)(request)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _detect_topic(text: str) -> str:
    """Which topic a request is about, or geometry when nothing matches.

    Keywords and tie-break priority now live on each topic's own declaration
    rather than in two tuples here that a new topic had to be added to. Geometry
    stays the default: the planner never refuses, and ``AnimationPlan.match``
    is what tells a caller the result was a fallback.
    """
    return detect(text, default=Topic.GEOMETRY)


def _is_unit_circle_to_sine(text: str) -> bool:
    lowered = text.lower()
    circle_signal = "单位圆" in lowered
    sine_signal = any(keyword in lowered for keyword in ("正弦", "sin", "sine"))
    trace_signal = any(
        keyword in lowered
        for keyword in ("生成", "轨迹", "对应", "展开", "同步", "波形", "图像")
    )
    return circle_signal and sine_signal and trace_signal


def _is_parabola_focus_directrix(text: str) -> bool:
    return "抛物线" in text and any(keyword in text for keyword in ("焦点", "准线"))


def _is_ellipse_foci(text: str) -> bool:
    if "椭圆" not in text:
        return False
    return any(keyword in text for keyword in ("焦点", "距离和", "距离的和", "pf1", "pf2"))


@plan_for(Topic.GEOMETRY)
def _geometry_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.GEOMETRY,
        title_zh="几何关系演示",
        objective_zh="用动态标注解释基本几何关系。",
        elements=["triangle", "angle labels", "side highlights", "explanation text"],
        narration_zh=[
            "先画出一个三角形，并标出关键顶点。",
            "再突出显示边和角，观察它们之间的关系。",
            "最后把结论固定在画面上，方便学生记录。",
        ],
        parameters={"source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene for a Chinese math lesson. "
            "Show a clean triangle geometry diagram with labeled vertices A, B, C, "
            "highlight one angle and one side relation, then display a concise Chinese "
            "teaching conclusion. Use stable Manim primitives and avoid external assets."
        ),
    )


@plan_for(Topic.TRIG)
def _trig_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.TRIG,
        title_zh="正弦函数的周期与振幅",
        objective_zh="展示正弦函数图像，并解释周期和振幅。",
        elements=["axes", "sine curve", "amplitude marker", "period marker"],
        narration_zh=[
            "先建立坐标系并画出正弦函数。",
            "竖直方向的最大高度表示振幅。",
            "水平方向重复一次所需的长度表示周期。",
        ],
        parameters={"function": "sin(x)", "source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene for y = sin(x). Draw axes, animate "
            "the sine curve, mark amplitude 1 with a vertical brace, mark period 2*pi "
            "with a horizontal brace, and show Chinese labels for 振幅 and 周期."
        ),
    )


def _unit_circle_to_sine_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.TRIG,
        concept=ConceptTrig.UNIT_CIRCLE_TO_SINE,
        title_zh="单位圆生成正弦函数",
        objective_zh="用单位圆上动点的纵坐标同步生成 y=sin(x) 的图像。",
        elements=[
            "unit circle",
            "rotating radius",
            "moving point",
            "sine graph",
            "projection guide",
            "period marker",
        ],
        narration_zh=[
            "先在单位圆上取一个随角度转动的点。",
            "这个点的纵坐标就是 sin θ。",
            "把每个角度对应的纵坐标搬到右侧坐标系，就得到正弦函数图像。",
            "转过一整圈后，曲线完成一个周期 2π。",
        ],
        parameters={"source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene for a Chinese lesson. Show a unit "
            "circle on the left and a sine graph on the right. Animate a point moving "
            "around the unit circle while its y-coordinate is projected to a moving "
            "point on y = sin(theta). Trace the sine curve, mark theta, sin(theta), "
            "and the period 2*pi with Chinese labels."
        ),
    )


@plan_for(Topic.CONIC)
def _conic_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.CONIC,
        title_zh="椭圆的焦点与长轴",
        objective_zh="展示椭圆、两个焦点和长轴。",
        elements=["ellipse", "foci", "major axis", "distance relation"],
        narration_zh=[
            "先画出椭圆和长轴。",
            "再标出两个焦点，说明它们决定椭圆的形状。",
            "椭圆上一点到两个焦点的距离和保持不变。",
        ],
        parameters={"conic": "ellipse", "source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene explaining an ellipse. Draw an "
            "ellipse, its major axis, two foci F1 and F2, a moving point P on the "
            "ellipse, and Chinese labels explaining that PF1 + PF2 is constant."
        ),
    )


def _ellipse_foci_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.CONIC,
        concept=ConceptConic.ELLIPSE_FOCI,
        title_zh="椭圆的焦点距离和",
        objective_zh="动态展示椭圆上一点到两个焦点的距离和保持不变。",
        elements=[
            "ellipse",
            "major axis",
            "foci F1 F2",
            "moving point P",
            "segments PF1 PF2",
            "constant sum label",
        ],
        narration_zh=[
            "先画出椭圆和它的两个焦点。",
            "取椭圆上的动点 P，连接 P 到两个焦点。",
            "点 P 移动时，两段距离会变化。",
            "但 PF1 与 PF2 的和始终等于长轴长度 2a。",
        ],
        parameters={"conic": "ellipse", "source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene explaining the foci definition "
            "of an ellipse for a Chinese lesson. Draw an ellipse, foci F1 and F2, "
            "a moving point P on the ellipse, segments PF1 and PF2, and show the "
            "constant relation PF1 + PF2 = 2a with concise Chinese labels."
        ),
    )


def _parabola_focus_directrix_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.CONIC,
        concept=ConceptConic.PARABOLA_FOCUS_DIRECTRIX,
        title_zh="抛物线的焦点与准线",
        objective_zh="动态展示抛物线上一点到焦点和准线的距离相等。",
        elements=[
            "parabola",
            "focus",
            "directrix",
            "moving point P",
            "focus distance",
            "directrix distance",
            "equality label",
        ],
        narration_zh=[
            "先画出抛物线、焦点和准线。",
            "取抛物线上的动点 P，连接 P 和焦点 F。",
            "再从 P 向准线作垂线。",
            "两段距离始终相等，这就是抛物线的定义。",
        ],
        parameters={"conic": "parabola", "source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition scene explaining the focus-directrix "
            "definition of a parabola for a Chinese lesson. Draw a parabola, focus F, "
            "directrix, a moving point P on the parabola, the segment PF, the "
            "perpendicular distance from P to the directrix, and the equality "
            "PF = d(P, directrix) with concise Chinese labels."
        ),
    )


@plan_for(Topic.THREE_D)
def _three_d_plan(request: str) -> AnimationPlan:
    spec = parse_solid_spec(request)
    if spec is not None:
        # 三视图 is solid-agnostic — check it before the cube-section branch.
        if is_three_views_request(request):
            return _three_views_plan(request, spec)
        if spec.kind == "cube":
            points = parse_section_points(request)
            if points is not None:
                return _cube_section_plan(request, spec, points)
        return _solid_overview_plan(request, spec)
    return _sphere_section_plan(request)


def _sphere_section_plan(request: str) -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.SPHERE_SECTION,
        title_zh="三维几何关系",
        objective_zh="用三维坐标系展示空间图形与截面。",
        elements=["3D axes", "sphere", "plane slice", "camera rotation"],
        narration_zh=[
            "先建立三维坐标系，帮助学生定位空间方向。",
            "再展示一个球体和一个截面平面。",
            "旋转视角后，可以更清楚地看到截面与立体图形的关系。",
        ],
        parameters={"solid": "sphere", "source_request_zh": request},
        english_prompt=(
            "Create a Manim Community Edition ThreeDScene for a Chinese lesson. Show "
            "3D axes, a translucent sphere, a slicing plane, rotate the camera, and add "
            "Chinese labels explaining the spatial relationship."
        ),
    )


def _solid_overview_plan(request: str, spec: SolidSpec) -> AnimationPlan:
    zh = solid_title_zh(spec)
    return AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.SOLID_OVERVIEW,
        title_zh=f"{zh} {spec.name} 的体积",
        objective_zh=f"展示{zh}的顶点结构与体积公式。",
        elements=["3D axes", "labeled solid", "vertex labels", "volume formula"],
        narration_zh=[
            "先建立三维坐标系，标出立体的八个顶点。",
            f"画出{zh}并依次标注 A、B、C、D 和上层顶点。",
            "最后给出体积公式，帮助学生记住推导过程。",
        ],
        parameters={
            "solid_spec": {"kind": spec.kind, "params": dict(spec.params), "name": spec.name},
            "source_request_zh": request,
        },
        english_prompt=(
            f"Create a Manim Community Edition ThreeDScene for a Chinese lesson. "
            f"Show a labeled {spec.kind} with named vertices ({spec.name}), 3D axes, "
            "billboard MathTex labels at each vertex, and a MathTex volume formula. "
            "Use a slight ambient camera rotation."
        ),
    )


def _three_views_plan(request: str, spec: SolidSpec) -> AnimationPlan:
    zh = solid_title_zh(spec)
    return AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.THREE_VIEWS,
        title_zh=f"{zh} {spec.name} 的三视图",
        objective_zh=f"展示{zh}的正视图、侧视图与俯视图，并用辅助线说明长对正、高平齐、宽相等。",
        elements=["front view", "side view", "top view", "alignment guides", "Chinese labels"],
        narration_zh=[
            "正视图：从正前方观察立体得到的轮廓。",
            "侧视图：从左侧观察立体，反映宽度与高度。",
            "俯视图：从正上方观察立体，反映长度与宽度。",
            "三视图之间满足长对正、高平齐、宽相等。",
        ],
        parameters={
            "solid_spec": {"kind": spec.kind, "params": dict(spec.params), "name": spec.name},
            "source_request_zh": request,
        },
        english_prompt=(
            f"Create a Manim Community Edition scene laying out the three standard "
            f"orthographic views (front / side / top) of a {spec.kind}. Arrange the "
            "front view upper-left, side upper-right, top lower-left, and add dashed "
            "alignment guides showing 长对正 and 高平齐 with concise Chinese labels."
        ),
    )


def _calculus_plan_for_request(request: str, expression: str | None) -> AnimationPlan | None:
    if is_taylor_request(request):
        return _taylor_series_plan(request)
    if is_ftc_request(request):
        return _ftc_accumulation_plan(request, expression)
    if is_integral_request(request):
        return _riemann_integral_plan(request, expression)
    if is_derivative_request(request):
        return _derivative_tangent_plan(request, expression)
    return None


@plan_for(Topic.CALCULUS)
def _calculus_plan(request: str) -> AnimationPlan:
    return _derivative_tangent_plan(request, None)


def _taylor_series_plan(request: str) -> AnimationPlan:
    # Default to sin; switch to cos when the request asks for it explicitly and
    # does not also mention sin. Other functions fall back to the sin demo (use
    # the LLM agent path for arbitrary Taylor targets).
    lowered = request.lower()
    wants_cos = any(k in lowered for k in ("cos", "余弦")) and not any(
        k in lowered for k in ("sin", "正弦")
    )
    func = "cos" if wants_cos else "sin"
    if func == "cos":
        title = "cos(x) 的泰勒展开"
        objective = "逐项加入泰勒多项式，展示多项式如何逼近 cos(x)。"
        first_step = "从零阶多项式 1 开始，它只在原点附近贴合曲线。"
        prompt = (
            "Create a Manim Community Edition calculus scene for the Taylor series of cos(x). "
            "Plot y=cos(x), then successively replace polynomial approximations 1, "
            "1 - x^2/2!, 1 - x^2/2! + x^4/4!, and 1 - x^2/2! + x^4/4! - x^6/6!. "
            "Show each formula with concise Chinese annotations explaining that more "
            "terms improve the approximation near 0."
        )
    else:
        title = "sin(x) 的泰勒展开"
        objective = "逐项加入泰勒多项式，展示多项式如何逼近 sin(x)。"
        first_step = "从一阶多项式 x 开始，它只在原点附近贴合曲线。"
        prompt = (
            "Create a Manim Community Edition calculus scene for the Taylor series of sin(x). "
            "Plot y=sin(x), then successively replace polynomial approximations x, "
            "x - x^3/3!, x - x^3/3! + x^5/5!, and x - x^3/3! + x^5/5! - x^7/7!. "
            "Show each formula with concise Chinese annotations explaining that more "
            "terms improve the approximation near 0."
        )
    return AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.TAYLOR_SERIES,
        title_zh=title,
        objective_zh=objective,
        elements=["axes", "target curve", "Taylor polynomial curves", "formula ladder", "error band"],
        narration_zh=[
            f"先画出目标函数 {func}(x)。",
            first_step,
            "继续加入更高阶项，逼近范围逐渐扩大。",
            "泰勒展开用原点附近的导数信息，拼出越来越准确的函数近似。",
        ],
        parameters={"function": func, "source_request_zh": request},
        english_prompt=prompt,
    )


def _derivative_tangent_plan(request: str, expression: str | None) -> AnimationPlan:
    pretty = pretty_expr(expression) if expression else "x^2"
    return AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.DERIVATIVE_TANGENT,
        title_zh=f"导数：y = {pretty} 的切线斜率",
        objective_zh="用割线逼近切线，解释导数表示瞬时变化率。",
        elements=["axes", "function curve", "secant line", "tangent line", "slope label"],
        narration_zh=[
            "先画出函数图像，并选定一个点。",
            "再取附近第二个点，画出两点之间的割线。",
            "当两点距离趋近于 0，割线就逼近切线。",
            "切线斜率就是该点处的导数，也就是瞬时变化率。",
        ],
        parameters={"expression": expression or "x ** 2", "source_request_zh": request},
        english_prompt=(
            f"Create a Manim Community Edition calculus scene for y = {expression or 'x ** 2'}. "
            "Plot the function, show a secant line through x0 and x0+h, animate h shrinking, "
            "then highlight the tangent line and label dy/dx as instantaneous rate of change "
            "with concise Chinese annotations."
        ),
    )


def _riemann_integral_plan(request: str, expression: str | None) -> AnimationPlan:
    pretty = pretty_expr(expression) if expression else "0.25x^2 + 0.5"
    return AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.RIEMANN_INTEGRAL,
        title_zh=f"定积分：y = {pretty} 下的面积",
        objective_zh="用黎曼矩形逼近曲线下方面积，解释定积分的含义。",
        elements=["axes", "function curve", "coarse rectangles", "fine rectangles", "integral label"],
        narration_zh=[
            "把区间切成若干小段，每一段宽度记作 Δx。",
            "用函数值作为矩形高度，矩形面积近似为 f(xᵢ)Δx。",
            "切分越细，矩形总面积越接近曲线下方的真实面积。",
            "这个极限就是定积分。",
        ],
        parameters={"expression": expression or "0.25 * x ** 2 + 0.5", "source_request_zh": request},
        english_prompt=(
            f"Create a Manim Community Edition calculus scene for y = {expression or '0.25 * x ** 2 + 0.5'}. "
            "Plot the function on an interval, fill the area with coarse Riemann rectangles, "
            "refine to more rectangles, and label the limit as an integral with Chinese annotations."
        ),
    )


def _ftc_accumulation_plan(request: str, expression: str | None) -> AnimationPlan:
    pretty = pretty_expr(expression) if expression else "0.3x^2 + 0.4"
    return AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.FTC_ACCUMULATION,
        title_zh=f"微积分基本定理：由面积得到函数",
        objective_zh="展示变上限面积函数 F(x) 的变化率等于原函数 f(x)。",
        elements=["source curve", "moving shaded area", "accumulation graph", "FTC equation"],
        narration_zh=[
            "左侧用移动的上限 x 形成从 a 到 x 的面积。",
            "右侧把这个面积值记录成新的函数 F(x)。",
            "当 x 向右移动一点，新增面积约等于 f(x)Δx。",
            "因此面积函数的导数回到原函数：F'(x)=f(x)。",
        ],
        parameters={"expression": expression or "0.3 * x ** 2 + 0.4", "source_request_zh": request},
        english_prompt=(
            f"Create a Manim Community Edition scene illustrating the Fundamental Theorem "
            f"of Calculus for f(x) = {expression or '0.3 * x ** 2 + 0.4'}. Show a moving "
            "shaded area from a to x, trace the accumulated area function F(x), and label "
            "F'(x)=f(x) with concise Chinese annotations."
        ),
    )


def _cube_section_plan(request: str, spec: SolidSpec, points: list[str]) -> AnimationPlan:
    zh_points = "、".join(points)
    return AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.CUBE_SECTION,
        title_zh=f"正方体 {spec.name} 过 {zh_points} 的截面",
        objective_zh=f"画出过 {zh_points} 三点的平面与正方体相交的截面。",
        elements=["3D axes", "labeled cube", "highlighted points", "section polygon"],
        narration_zh=[
            "先画出正方体并标注八个顶点。",
            f"接着标出确定截面的三个点：{zh_points}。",
            "求出截面与每条棱的交点，连接成多边形即为所求截面。",
        ],
        parameters={
            "solid_spec": {"kind": spec.kind, "params": dict(spec.params), "name": spec.name},
            "section_points": list(points),
            "source_request_zh": request,
        },
        english_prompt=(
            f"Create a Manim Community Edition ThreeDScene for a Chinese lesson. "
            f"Show the cube {spec.name}, highlight the points {', '.join(points)}, "
            "draw the polygonal section where the plane through them cuts the cube, "
            "and add a Chinese caption. Use a slight ambient camera rotation."
        ),
    )


def _trig_transform_plan(request: str, expression: str, spec: TrigSpec) -> AnimationPlan:
    zh = trig_func_zh(spec)
    return AnimationPlan(
        topic=Topic.TRIG,
        concept=ConceptTrig.GRAPH_TRANSFORM,
        title_zh=f"{zh}函数 y = A·{spec.func}(ωx + φ) + k 的图像变换",
        objective_zh="展示振幅、周期、相位和中线对函数图像的影响。",
        elements=["axes", "base curve", "transformed curve", "amplitude brace", "period brace", "midline"],
        narration_zh=[
            f"先建立坐标系并画出基础{zh}函数 y = {spec.func}(x)。",
            "然后变换到目标函数，观察振幅、周期、相位和中线的变化。",
            "标出关键量：A 表示振幅，T 表示周期，y = k 表示中线。",
        ],
        parameters={
            "expression": expression,
            "trig_spec": {
                "func": spec.func, "A": spec.A, "omega": spec.omega,
                "phi": spec.phi, "k": spec.k,
            },
            "source_request_zh": request,
        },
        english_prompt=(
            f"Create a Manim Community Edition scene plotting y = A {spec.func}(ω x + φ) + k "
            f"with the parsed values A={spec.A}, ω={spec.omega}, φ={spec.phi}, k={spec.k}. "
            "Draw axes, animate the base curve y = {spec.func}(x), morph into the target, "
            "and label amplitude (brace), period (brace), and midline (dashed line) with "
            "concise Chinese annotations."
        ),
    )


def _function_plan(request: str, expression: str) -> AnimationPlan:
    pretty = pretty_expr(expression)
    return AnimationPlan(
        topic=Topic.FUNCTION,
        title_zh=f"函数 y = {pretty} 的图像",
        objective_zh="绘制函数图像，并标出零点和 y 轴截距。",
        elements=["axes", "function curve", "x-intercepts", "y-intercept"],
        narration_zh=[
            "先建立坐标系。",
            f"画出函数 y = {pretty} 的图像。",
            "标出图像与坐标轴的交点，帮助学生观察函数性质。",
        ],
        parameters={"expression": expression, "source_request_zh": request},
        english_prompt=(
            f"Create a Manim Community Edition scene plotting y = {expression}. "
            "Draw labeled axes with coordinates, the curve, mark x-intercepts and "
            "the y-intercept, and add concise Chinese labels."
        ),
    )



#: Words that pick a *reading* of a matrix product, for a request that already
#: asked for one. Absent from ``TOPIC_KEYWORDS`` on purpose: "行"/"row" alone is
#: not a linear-algebra request, it is a word.
_VIEW_KEYWORDS = {
    "outer": ("外积", "秩一", "rank-1", "rank one", "outer product"),
    "column": ("列向量", "按列", "column of b", "by column", "columns of"),
    "row": ("行向量", "按行", "row of a", "by row", "rows of"),
    "entry": ("逐元素", "内积视角", "entry by entry", "dot product"),
}

_MATMUL_KEYWORDS = (
    "矩阵乘法", "矩阵相乘", "矩阵乘积", "外积", "秩一",
    "matmul", "matrix multiplication", "matrix product", "outer product",
    "rank-1", "rank one",
)


@plan_for(Topic.LINEAR_ALGEBRA)
def _linear_algebra_plan(request: str) -> AnimationPlan:
    """Two concepts: one matrix acting, or two matrices meeting.

    Which one a prompt gets is decided here; *which reading* of a product it
    gets is decided by the parameters, and a text request carries none — so a
    prompt that names a view in words is honoured, and everything else takes the
    default and leaves refinement to callers that pass ``parameters`` (which is
    what :func:`plan_from_template` is for).
    """
    if any(word in request for word in _MATMUL_KEYWORDS):
        view = next((name for name, words in _VIEW_KEYWORDS.items()
                     if any(word in request for word in words)), "entry")
        assert view in VIEWS
        return AnimationPlan(
            topic=Topic.LINEAR_ALGEBRA,
            title_zh="矩阵乘法的四种读法",
            objective_zh="同一个乘积，四种理解方式",
            english_prompt=request,
            concept=ConceptLinAlg.MATMUL_VIEWS,
            parameters={"view": view},
            elements=["matrix", "matrix", "product"],
        )

    return AnimationPlan(
        topic=Topic.LINEAR_ALGEBRA,
        title_zh="线性变换",
        objective_zh="看矩阵如何作用于平面",
        english_prompt=request,
        concept=ConceptLinAlg.LINEAR_MAP,
        elements=["plane", "vectors", "matrix"],
    )


