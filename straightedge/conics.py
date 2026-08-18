"""Conic-section concept identifiers."""

from __future__ import annotations

from .models import Topic
from .topics import topic


class ConceptConic:
    """Sub-topic identifiers under ``Topic.CONIC``."""

    ELLIPSE_FOCI = "conic/ellipse_foci"
    PARABOLA_FOCUS_DIRECTRIX = "conic/parabola_focus_directrix"
    CONE_SLICE = "conic/cone_slice"


#: Default tangent of the cone's half-angle (measured from the axis).
#:
#: Sets where the parabola falls: the cutting plane is parallel to a slant line
#: when its slope reaches ``1 / CONE_HALF_ANGLE_TAN``. At 0.8 that is a slope of
#: 1.25 — a plane tilted about 51°, steep enough to read as tilted on screen and
#: shallow enough that the hyperbola case still fits in frame. A narrow cone
#: pushes the parabola towards vertical and the sweep stops being legible.
CONE_HALF_ANGLE_TAN = 0.8

#: Bounds on that tangent, shared by the builder (which clamps) and the
#: precondition (which reports). One constant so the two cannot disagree about
#: what is drawable — a check that passes a value the builder then replaces is
#: worse than no check, because it says the render is faithful when it is not.
#:
#: 0.15 is a needle about 9° wide and 6.0 is a cone flatter than 80°: at either
#: extreme the plane's whole sweep from circle to hyperbola happens within a few
#: degrees and nothing is legible.
CONE_TAN_MIN = 0.15
CONE_TAN_MAX = 6.0


@topic(Topic.CONIC, priority=20,
       keywords=("圆锥曲线", "椭圆", "抛物线", "双曲线", "焦点", "准线", "离心率"))
class Conics:
    """Conic sections: the ellipse, the parabola, and the cone they come from."""

    concepts = ConceptConic
