"""Classical constructive geometry — compass, straightedge, and exact coordinates.

The library is named after a tool it could not draw with. This is that lane.

What distinguishes it from drawing two circles and a line is that a construction
here can *assert what it demonstrates*, and the assertion is decided exactly
rather than measured. ``preconditions`` checks that a plan is well-formed, ``qc``
checks that a rendered frame is legible, and ``labels`` checks that text was
translated — but none of the three can tell you that the line you drew through
two circle intersections really is the perpendicular bisector. That is a fourth
failure mode, *the picture is legible and the mathematics is wrong*, and
:mod:`straightedge.geometry.exact` is what makes it decidable.

Stdlib only. The figure lane declares no runtime dependencies and this belongs
to it; :mod:`straightedge.geometry.exact` imports nothing from the rest of the
package except the typed errors.
"""

from __future__ import annotations

from .exact import MAX_BITS, MAX_DEPTH, Exact, Tower
from .model import (
    Circle,
    Construction,
    Element,
    Line,
    Point,
    Polygon,
    Section,
    Segment,
)

__all__ = [
    "Construction",
    "Element",
    "Point",
    "Line",
    "Circle",
    "Segment",
    "Section",
    "Polygon",
    "Exact",
    "Tower",
    "MAX_DEPTH",
    "MAX_BITS",
]
