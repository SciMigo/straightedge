"""On-screen label language: what the viewer reads inside the frame.

Distinct from narration, which the caller already supplies in whatever language
it likes (``AnimationPlan.narration_zh`` is filled from the job payload). The
scene builders, by contrast, carry their labels as Chinese literals, so an
English-narrated render used to ship English audio over Chinese titles.

**Translation happens after generation, on the emitted source.** The builders
stay single-language and untouched, and — more usefully — this is the only point
where *everything* that reached the frame is visible at once. Labels arrive from
several places: literals in ``templates``, solid names from ``solids3d``,
function names from ``trig``, all substituted into placeholders. Translating at
the source boundary catches them regardless of origin, and
:func:`untranslated` can then report anything still unrendered in the target
language rather than letting it ship silently.

Lookup is per **whole quoted literal**, never per fragment. That matters twice:
a phrase that contains a shorter phrase (``"PF = d(P, 准线)"`` contains
``"准线"``) can never be half-replaced, and comments cannot be rewritten because
they are not quoted.
"""

from __future__ import annotations

import re

LANGUAGES = ("zh", "en")

#: The language the scene builders are written in, and therefore the key
#: language of the catalog below. A **fact about the source**, not a product
#: choice: translation is a no-op in this direction, which is why it is the one
#: value :func:`translate` can short-circuit on.
AUTHORED_LANGUAGE = "zh"

#: What a caller gets for asking for nothing. A **product choice** — the launch
#: market is US YouTube and TikTok, so a render with no stated language should
#: be English, not the language the library happens to be written in.
#:
#: Deliberately not the same constant as :data:`AUTHORED_LANGUAGE`. Conflating
#: them is what made "no opinion" mean "Chinese", and it would quietly do so
#: again the moment either one moved.
DEFAULT_LANGUAGE = "en"

#: Chinese on-screen literal -> English.
#:
#: Several titles are Chinese *circumfixes* — ``函数`` + formula + ``的图像`` —
#: where English needs a prefix only. Those map the suffix to ``""``; an empty
#: ``Text`` is a zero-width mobject that leaves ``VGroup.arrange`` unchanged
#: (verified against Manim CE 0.20). Where one prefix serves two different
#: titles it cannot carry the framing, so ``正方体`` stays a plain noun and the
#: suffix supplies the rest.
TRANSLATIONS: dict[str, str] = {
    # --- conics: the launch series' path, so these are the load-bearing ones
    "椭圆的焦点距离和": "Sum of Distances to the Foci",
    "椭圆：到两个焦点的距离和为常数的点的轨迹":
        "Constant sum of distances to two foci",
    "椭圆的焦点与长轴": "Foci and Major Axis of an Ellipse",
    "椭圆上任意点到两个焦点的距离和不变":
        "The two focal distances always sum to 2a",
    "长轴": "major axis",
    "抛物线的焦点与准线": "Focus and Directrix of a Parabola",
    "抛物线：到焦点和到准线距离相等的点的轨迹":
        "Equidistant from the focus and the directrix",
    "准线": "directrix",
    "焦点 F": "focus F",
    "PF = d(P, 准线)": "PF = d(P, directrix)",
    "d(P, 准线)": "d(P, directrix)",
    "圆锥曲线的由来": "Where the Conics Come From",
    "垂直于轴：截面是圆": "Perpendicular to the axis: a circle",
    "略微倾斜：截面是椭圆": "Tilt it slightly: an ellipse",
    "与母线平行：截面是抛物线": "Parallel to a slant line: a parabola",
    "更陡：同时截到两个锥面，是双曲线": "Steeper: it cuts both nappes — a hyperbola",
    "平面过顶点：截面缩成一个点": "Through the apex: the section shrinks to a point",
    "继续倾斜：先是一条线，再变成两条相交直线":
        "Tilt further: one line, then two crossed lines",
    "同一个圆锥，切的角度不同，就得到四条曲线":
        "One cone. The cutting angle is the whole story.",

    # --- trigonometry
    "单位圆": "unit circle",
    "单位圆生成正弦函数": "The Unit Circle Generates the Sine Function",
    "单位圆上一点的纵坐标，沿角度展开就是正弦曲线":
        "Unroll that height by angle and you get the sine curve",
    "正弦函数的周期与振幅": "Period and Amplitude of the Sine Function",
    "周期 = 2π": "period = 2π",
    "振幅 = 1": "amplitude = 1",
    "正弦": "sine",
    "余弦": "cosine",
    "正切": "tangent",

    # --- calculus (circumfix titles: prefix carries the sense, suffix empties)
    "导数：": "Derivative: tangent slope of",
    " 的切线斜率": "",
    "两点靠近时，割线斜率逼近切线斜率":
        "The secant slope approaches the tangent slope",
    "定积分：": "Definite integral: area under",
    " 下的面积": "",
    "矩形越细，总面积越接近曲线下方的面积":
        "Narrower rectangles, closer to the true area",
    "微积分基本定理": "The Fundamental Theorem of Calculus",
    "面积函数的瞬时变化率，等于当前高度 f(x)":
        "The area's rate of change equals the height f(x)",

    # --- Taylor series
    "sin(x) 的泰勒展开": "Taylor expansion of sin(x)",
    "cos(x) 的泰勒展开": "Taylor expansion of cos(x)",
    "只保留常数项：在 0 附近是一条水平线":
        "Constant term only: a horizontal line near 0",
    "只保留一阶项：在 0 附近像一条切线":
        "Through the linear term: a tangent line near 0",
    "加入二次项：开口方向开始匹配":
        "Add the quadratic term: the concavity begins to match",
    "加入三次项：弯曲方向开始匹配":
        "Add the cubic term: the bending begins to match",
    "加入四次项：贴合范围继续扩大":
        "Add the fourth-order term: the fit reaches further out",
    "加入五次项：贴合范围继续扩大":
        "Add the fifth-order term: the fit reaches further out",
    "加入六次项：多项式逐步逼近 cos(x)":
        "Add the sixth-order term: the polynomial closes in on cos(x)",
    "加入七次项：多项式逐步逼近 sin(x)":
        "Add the seventh-order term: the polynomial closes in on sin(x)",
    "先在 0 附近最准确": "Most accurate near 0 first",
    "更多项会把逼近范围继续向外推开":
        "More terms widen the range of good fit",

    # --- solid geometry. 正方体 prefixes both the cross-section title and the
    # three-view title, so the suffix carries the framing rather than the noun.
    "三维几何中的截面": "Cross-Sections in Solid Geometry",
    "平面截球得到圆形截面": "A plane cutting a sphere gives a circular cross-section",
    "的截面": "— cross-section",
    "的三视图": "— three views",
    "过": "through",
    "正方体": "cube",
    "长方体": "rectangular box",
    "正四面体": "regular tetrahedron",
    "圆柱": "cylinder",
    "圆锥": "cone",
    "正三棱柱": "regular triangular prism",
    "正四棱柱": "regular quadrilateral prism",
    "正五棱柱": "regular pentagonal prism",
    "正六棱柱": "regular hexagonal prism",
    "正三棱锥": "regular triangular pyramid",
    "正四棱锥": "regular quadrilateral pyramid",
    "正五棱锥": "regular pentagonal pyramid",
    "正六棱锥": "regular hexagonal pyramid",
    "正视图": "front view",
    "侧视图": "side view",
    "俯视图": "top view",
    "长对正": "widths aligned",
    "高平齐": "heights level",

    # --- plane geometry
    "几何关系演示": "Geometric Relationships",
    "通过标注边和角，观察几何关系":
        "Label the sides and angles to see the relationships",

    # --- function grapher
    "函数": "Graph of",
    "的图像": "",
    "红点：零点    黄点：y 轴截距": "red: zeros    yellow: y-intercept",
}

#: A double-quoted literal containing at least one CJK character. Anchored to
#: the quotes so a comment mentioning a label is never rewritten, and bounded to
#: one line so a stray quote cannot swallow the rest of the file.
_QUOTED_CJK = re.compile(r'"([^"\n]*[一-鿿][^"\n]*)"')


def normalize(language: str | None) -> str:
    """An unknown or absent language is the authored one, never an error."""
    value = (language or "").strip().lower()
    if value in LANGUAGES:
        return value
    # Accept the BCP-47-ish forms the job API speaks ("zh-CN", "en-US").
    base = value.split("-")[0]
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


def needs_cjk_font(language: str | None) -> bool:
    """Whether a render will actually draw CJK glyphs.

    An English scene has no Chinese left in it, so failing its render for a
    missing CJK font would block a host that can serve it perfectly well.
    """
    return normalize(language) == AUTHORED_LANGUAGE


def translate(code: str, language: str | None = DEFAULT_LANGUAGE) -> str:
    """Rewrite on-screen labels in ``code`` into ``language``.

    Unknown literals are left as they are rather than blanked: a Chinese label
    is a visible, reportable defect, where a silently empty one looks like a
    render bug and loses the text entirely.
    """
    if normalize(language) == AUTHORED_LANGUAGE:
        return code

    def swap(match: re.Match[str]) -> str:
        english = TRANSLATIONS.get(match.group(1))
        return f'"{english}"' if english is not None else match.group(0)

    return _QUOTED_CJK.sub(swap, code)


def untranslated(code: str, language: str | None = DEFAULT_LANGUAGE) -> list[str]:
    """On-screen literals with no translation for ``language``.

    Reported rather than raised. A scene whose caption is still Chinese is a
    real problem for a non-Chinese channel, but it is a *labelling* problem —
    the geometry is fine and the render is worth keeping while it is fixed.

    Short-circuits on the *authored* language, where by definition nothing is
    missing. Testing the default instead would report nothing for English, which
    is the one language the check exists to police.
    """
    if normalize(language) == AUTHORED_LANGUAGE:
        return []
    return sorted({lit for lit in _QUOTED_CJK.findall(code)
                   if lit not in TRANSLATIONS})
