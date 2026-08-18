"""Calculus concept identifiers and request classification helpers."""

from __future__ import annotations

from .models import Topic
from .topics import topic


class ConceptCalculus:
    """Sub-topic identifiers under ``Topic.CALCULUS``."""

    DERIVATIVE_TANGENT = "calculus/derivative_tangent"
    RIEMANN_INTEGRAL = "calculus/riemann_integral"
    FTC_ACCUMULATION = "calculus/ftc_accumulation"
    TAYLOR_SERIES = "calculus/taylor_series"
    #: A line against a vertically shiftable curve, with the shift raised until
    #: the two touch. The shape behind a family of exam questions — "for what a
    #: does line/(curve + a) have maximum 1" — where the answer is the shift
    #: that turns two crossings into one.
    TANGENT_SHIFT = "calculus/tangent_shift"


DERIVATIVE_KEYWORDS = (
    "导数",
    "微分",
    "切线",
    "斜率",
    "变化率",
    "瞬时变化",
    "dy/dx",
    "f'",
)

# Unambiguous integral cues — these route to the Riemann scene on their own.
INTEGRAL_KEYWORDS = (
    "积分",
    "黎曼",
    "riemann",
    "dx",
    "定积分",
    "累加",
)

# ``面积`` (area) is far too common in plain geometry/3D requests (三角形的面积,
# 圆的面积, 各面的面积...) to route on its own. It only signals a definite
# integral when paired with a curve/region cue.
AREA_KEYWORDS = ("面积", "区域")
AREA_CONTEXT_KEYWORDS = ("曲线", "区间", "矩形", "下方", "下面", "围成", "原函数")

FTC_KEYWORDS = (
    "微积分基本定理",
    "基本定理",
    "累积函数",
    "面积函数",
    "变上限",
    "ftc",
)

TAYLOR_KEYWORDS = (
    "泰勒",
    "taylor",
    "麦克劳林",
    "maclaurin",
    "级数展开",
    "逐项",
    "多项式逼近",
)


def is_derivative_request(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in DERIVATIVE_KEYWORDS)


def is_integral_request(text: str) -> bool:
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in INTEGRAL_KEYWORDS):
        return True
    if any(keyword in lowered for keyword in AREA_KEYWORDS):
        return any(context in lowered for context in AREA_CONTEXT_KEYWORDS)
    return False


def is_ftc_request(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in FTC_KEYWORDS)


def is_taylor_request(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in TAYLOR_KEYWORDS)


@topic(Topic.CALCULUS, priority=10,
       keywords=("导数", "微分", "切线", "斜率", "变化率", "积分", "黎曼", "dx", "极限",
              "泰勒", "麦克劳林", "级数", "多项式逼近"))
class Calculus:
    """Derivatives, integrals, the fundamental theorem, Taylor series."""

    concepts = ConceptCalculus
