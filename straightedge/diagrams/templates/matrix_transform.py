"""Matrix transformation visualization template.

Shows a shape (unit square, unit circle, or custom vectors) before and after
a 2x2 matrix transformation, displayed side by side. Optionally highlights
eigenvectors and shows the transformation grid.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ..registry import register
from ..renderer import (
    DEFAULT_STYLES,
    circle,
    defs,
    group,
    line,
    path,
    polyline,
    rect,
    style,
    svg_document,
    text,
)


def _mat_mul(matrix: List[List[float]], v: Tuple[float, float]) -> Tuple[float, float]:
    """Multiply a 2x2 matrix by a 2D vector."""
    return (
        matrix[0][0] * v[0] + matrix[0][1] * v[1],
        matrix[1][0] * v[0] + matrix[1][1] * v[1],
    )


def _unit_square_vertices() -> List[Tuple[float, float]]:
    """Return unit square vertices (closed path)."""
    return [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]


def _unit_circle_points(n: int = 64) -> List[Tuple[float, float]]:
    """Sample points along the unit circle."""
    points = []
    for i in range(n + 1):
        angle = 2 * math.pi * i / n
        points.append((math.cos(angle), math.sin(angle)))
    return points


def _basis_vectors() -> List[Tuple[Tuple[float, float], str]]:
    """Return standard basis vectors with labels."""
    return [((1, 0), "e1"), ((0, 1), "e2")]


def _eigenvalues_2x2(m: List[List[float]]) -> List[Tuple[float, Tuple[float, float]]]:
    """Compute eigenvalues and eigenvectors of a 2x2 real matrix.

    Returns list of (eigenvalue, eigenvector) pairs. Eigenvectors are normalized.
    Only returns real eigenvalues.
    """
    a, b = m[0][0], m[0][1]
    c, d = m[1][0], m[1][1]

    trace = a + d
    det = a * d - b * c
    discriminant = trace * trace - 4 * det

    if discriminant < -1e-10:
        return []  # Complex eigenvalues

    results = []
    disc_sqrt = math.sqrt(max(0, discriminant))
    for eigenvalue in [(trace + disc_sqrt) / 2, (trace - disc_sqrt) / 2]:
        # Find eigenvector: (A - λI)v = 0
        r0 = (a - eigenvalue, b)
        r1 = (c, d - eigenvalue)

        # Use the row with larger magnitude to find the eigenvector
        if abs(r0[0]) + abs(r0[1]) >= abs(r1[0]) + abs(r1[1]):
            if abs(r0[0]) > 1e-10:
                ev = (-r0[1] / r0[0], 1.0)
            elif abs(r0[1]) > 1e-10:
                ev = (1.0, 0.0)
            else:
                ev = (1.0, 0.0)
        else:
            if abs(r1[0]) > 1e-10:
                ev = (-r1[1] / r1[0], 1.0)
            elif abs(r1[1]) > 1e-10:
                ev = (1.0, 0.0)
            else:
                ev = (0.0, 1.0)

        # Normalize
        mag = math.sqrt(ev[0] ** 2 + ev[1] ** 2)
        if mag > 1e-10:
            ev = (ev[0] / mag, ev[1] / mag)
            results.append((eigenvalue, ev))

    return results


@register("matrix_transform")
class MatrixTransformTemplate:
    """Render a before/after visualization of a 2x2 matrix transformation."""

    # Layout constants
    PANEL_WIDTH = 190
    PANEL_HEIGHT = 190
    GAP = 20
    PADDING = 30

    # Colors
    COLOR_ORIGINAL = "#6366F1"  # indigo
    COLOR_TRANSFORMED = "#EC4899"  # pink
    COLOR_EIGEN = "#F59E0B"  # amber
    COLOR_GRID = "#e0e0e0"
    COLOR_AXIS = "#333"
    COLOR_E1 = "#6366F1"  # indigo
    COLOR_E2 = "#43A047"  # green

    def render(self, params: Dict[str, Any]) -> str:
        """Render the matrix transformation diagram.

        Params:
            matrix: 2x2 matrix as [[a, b], [c, d]]
            shape: "unit_square" (default), "unit_circle", or "basis_vectors"
            show_eigenvectors: Show eigenvector directions (default: False)
            show_grid: Show transformed grid lines (default: True)
            show_basis: Show e1, e2 basis vectors and their images (default: True)
            x_range: Axis range (default: auto-computed from transformation)
            caption: Optional caption text
            label_before: Label for left panel (default: "Before")
            label_after: Label for right panel (default: "After")
            matrix_label: Optional matrix notation to display (e.g., "A")
        """
        matrix = params.get("matrix", [[1, 0], [0, 1]])
        if not self._valid_matrix(matrix):
            matrix = [[1, 0], [0, 1]]

        shape = params.get("shape", "unit_square")
        show_eigen = bool(params.get("show_eigenvectors", False))
        show_grid = bool(params.get("show_grid", True))
        show_basis = bool(params.get("show_basis", True))
        caption = params.get("caption")
        label_before = params.get("label_before", "Before")
        label_after = params.get("label_after", "After")
        matrix_label = params.get("matrix_label")

        # Compute auto range from transformed shape
        x_range = params.get("x_range")
        if x_range is None:
            x_range = self._auto_range(matrix, shape)
        else:
            x_range = float(x_range)

        # SVG dimensions
        svg_width = 2 * self.PANEL_WIDTH + self.GAP + 2 * self.PADDING
        svg_height = self.PANEL_HEIGHT + 2 * self.PADDING + (25 if caption else 0)

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._styles()))
        elements.append(defs(self._arrow_markers()))

        # Left panel: original
        left_x = self.PADDING
        top_y = self.PADDING
        elements.append(
            self._render_panel(
                left_x, top_y, x_range, shape, None, show_grid, show_basis, False,
                label_before, matrix,
            )
        )

        # Right panel: transformed
        right_x = self.PADDING + self.PANEL_WIDTH + self.GAP
        elements.append(
            self._render_panel(
                right_x, top_y, x_range, shape, matrix, show_grid, show_basis,
                show_eigen, label_after, matrix,
            )
        )

        # Arrow between panels
        arrow_y = top_y + self.PANEL_HEIGHT / 2
        arrow_x1 = left_x + self.PANEL_WIDTH + 2
        arrow_x2 = right_x - 2
        mid_x = (arrow_x1 + arrow_x2) / 2
        elements.append(
            line(
                arrow_x1, arrow_y, arrow_x2, arrow_y,
                stroke=self.COLOR_AXIS, stroke_width="1.5",
                marker_end="url(#mt-arrow)",
            )
        )
        if matrix_label:
            elements.append(
                text(mid_x, arrow_y - 6, matrix_label,
                     **{"class": "mt-matrix-label", "text_anchor": "middle"})
            )

        # Caption
        if caption:
            elements.append(
                text(
                    svg_width / 2, svg_height - 5, caption,
                    **{"class": "mt-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _render_panel(
        self,
        ox: float,
        oy: float,
        x_range: float,
        shape: str,
        matrix: list | None,
        show_grid: bool,
        show_basis: bool,
        show_eigen: bool,
        label: str,
        orig_matrix: list,
    ) -> str:
        """Render one panel (before or after)."""
        pw, ph = self.PANEL_WIDTH, self.PANEL_HEIGHT
        elements: List[str] = []

        # Panel background
        elements.append(
            rect(ox, oy, pw, ph, fill="white", stroke="#ddd", stroke_width="1", rx="4")
        )

        # The panel's clip, emitted whether or not a grid asks for it. Anything
        # drawn to read as a line rather than a segment runs past the panel on
        # purpose, and needs the panel to cut it off; the eigenvector rays did
        # not have one to reach for, so they crossed the gutter, the other panel
        # and the edge of the figure.
        #
        # The id is a fragment identifier, which the browser resolves across
        # the whole page, first match wins — two figures inlined into one
        # document share the namespace. Minting it from the full clip geometry
        # (not just `ox`) makes any collision harmless by construction: two
        # clipPaths with this id cut the same rectangle, so it no longer
        # matters whose definition wins. The same rect() the visible panel uses
        # keeps clip and panel from silently desyncing.
        clip_id = f"mt-clip-{ox:.0f}-{oy:.0f}-{pw:.0f}x{ph:.0f}"
        clip_ref = f"url(#{clip_id})"
        elements.append(
            f'<clipPath id="{clip_id}">{rect(ox, oy, pw, ph, rx="4")}</clipPath>'
        )

        # Coordinate transforms
        scale = pw / (2 * x_range)
        cx = ox + pw / 2
        cy = oy + ph / 2

        def to_svg(v: Tuple[float, float]) -> Tuple[float, float]:
            return (cx + v[0] * scale, cy - v[1] * scale)

        # Grid lines
        if show_grid:
            grid_els = []
            step = 1
            n = int(x_range) + 1
            for i in range(-n, n + 1):
                if matrix is not None:
                    # Transformed grid: vertical lines x=i
                    p1 = _mat_mul(matrix, (i * step, -n * step))
                    p2 = _mat_mul(matrix, (i * step, n * step))
                    s1, s2 = to_svg(p1), to_svg(p2)
                    grid_els.append(
                        line(s1[0], s1[1], s2[0], s2[1], **{"class": "mt-grid"})
                    )
                    # Horizontal lines y=i
                    p1 = _mat_mul(matrix, (-n * step, i * step))
                    p2 = _mat_mul(matrix, (n * step, i * step))
                    s1, s2 = to_svg(p1), to_svg(p2)
                    grid_els.append(
                        line(s1[0], s1[1], s2[0], s2[1], **{"class": "mt-grid"})
                    )
                else:
                    # Regular grid
                    sx = cx + i * step * scale
                    sy = cy - i * step * scale
                    grid_els.append(
                        line(sx, oy + 2, sx, oy + ph - 2, **{"class": "mt-grid"})
                    )
                    grid_els.append(
                        line(ox + 2, sy, ox + pw - 2, sy, **{"class": "mt-grid"})
                    )
            elements.append(
                group("\n".join(grid_els), clip_path=clip_ref)
            )

        # Axes
        elements.append(
            line(ox + 2, cy, ox + pw - 2, cy, **{"class": "mt-axis"})
        )
        elements.append(
            line(cx, oy + 2, cx, oy + ph - 2, **{"class": "mt-axis"})
        )

        # Shape
        shape_points = self._get_shape_points(shape)
        if matrix is not None:
            transformed = [_mat_mul(matrix, p) for p in shape_points]
            svg_pts = [to_svg(p) for p in transformed]
            color = self.COLOR_TRANSFORMED
        else:
            svg_pts = [to_svg(p) for p in shape_points]
            color = self.COLOR_ORIGINAL

        if len(svg_pts) > 1:
            if shape == "unit_circle":
                d = f"M {svg_pts[0][0]} {svg_pts[0][1]}"
                for sp in svg_pts[1:]:
                    d += f" L {sp[0]} {sp[1]}"
                elements.append(
                    path(d, stroke=color, stroke_width="2", fill=color,
                         fill_opacity="0.1")
                )
            else:
                elements.append(
                    polyline(svg_pts, stroke=color, stroke_width="2", fill=color,
                             fill_opacity="0.15")
                )

        # Basis vectors
        basis_tips: List[Tuple[float, float]] = []
        if show_basis:
            for bv, lbl in _basis_vectors():
                if matrix is not None:
                    tv = _mat_mul(matrix, bv)
                else:
                    tv = bv
                origin = to_svg((0, 0))
                tip = to_svg(tv)
                basis_tips.append(tip)
                bcolor = self.COLOR_E1 if lbl == "e1" else self.COLOR_E2
                elements.append(
                    line(
                        origin[0], origin[1], tip[0], tip[1],
                        stroke=bcolor, stroke_width="2",
                        marker_end="url(#mt-arrow-basis)",
                    )
                )
                lbl_display = lbl if matrix is None else f"A{lbl}"
                elements.append(
                    text(tip[0] + 4, tip[1] - 4, lbl_display,
                         **{"class": "mt-vec-label", "fill": bcolor})
                )

        # Eigenvectors
        if show_eigen and matrix is not None:
            eigen_els: List[str] = []
            eigen_labels: List[str] = []
            drawn: List[Tuple[float, float]] = []
            for eigenval, eigenvec in _eigenvalues_2x2(orig_matrix):
                # A repeated eigenvalue hands back the same direction twice, and
                # the same dashed ray drawn over itself is darker, not clearer.
                if any(abs(eigenvec[0] * b - eigenvec[1] * a) < 1e-9
                       for a, b in drawn):
                    continue
                drawn.append(eigenvec)
                # Deliberately longer than the panel so the direction reads as a
                # line rather than a segment -- which is only right if the panel
                # actually cuts it off. Unclipped, it crossed the gutter, the
                # other panel and the edge of the figure.
                scale_factor = x_range * 1.5
                p1 = (-eigenvec[0] * scale_factor, -eigenvec[1] * scale_factor)
                p2 = (eigenvec[0] * scale_factor, eigenvec[1] * scale_factor)
                s1, s2 = to_svg(p1), to_svg(p2)
                eigen_els.append(
                    line(
                        s1[0], s1[1], s2[0], s2[1],
                        stroke=self.COLOR_EIGEN, stroke_width="1.5",
                        stroke_dasharray="6,3", opacity="0.8",
                    )
                )
                # Label at tip — outside the clip. The ray is clipped because
                # it overruns on purpose; a label that overruns is just a label
                # the reader cannot finish, and clipping it silently is what the
                # legibility check now calls out.
                # The ray has two ends, and the basis-image labels sit at the
                # same (+4, -4) offset from *their* tips — so whenever an
                # eigenvector is parallel to a basis image (any diagonal or
                # axis-aligned matrix) a fixed end drew the eigenvalue straight
                # over Ae1. The ray reads the same from either end; the basis
                # label has only one home. Take the end farther from every
                # basis tip.
                ends = [to_svg((eigenvec[0] * x_range * s, eigenvec[1] * x_range * s))
                        for s in (0.7, -0.7)]

                def _clearance(pt: Tuple[float, float]) -> float:
                    return min((math.hypot(pt[0] - bx, pt[1] - by)
                                for bx, by in basis_tips), default=float("inf"))

                tip = max(ends, key=_clearance)
                # Both ends crowded (both basis images on this ray): drop the
                # label under the ray instead — the basis label sits above it.
                label_dy = -4 if _clearance(tip) >= 28 else 12
                eigen_labels.append(
                    text(
                        tip[0] + 4, tip[1] + label_dy,
                        f"\u03bb={eigenval:.1f}",
                        **{"class": "mt-eigen-label"},
                    )
                )
            if eigen_els:
                elements.append(group("\n".join(eigen_els), clip_path=clip_ref))
            elements.extend(eigen_labels)

        # Panel label
        elements.append(
            text(
                ox + pw / 2, oy - 5, label,
                **{"class": "mt-panel-label", "text_anchor": "middle"},
            )
        )

        return group("\n".join(elements))

    def _get_shape_points(self, shape: str) -> List[Tuple[float, float]]:
        if shape == "unit_circle":
            return _unit_circle_points(64)
        elif shape == "basis_vectors":
            return []  # Basis vectors drawn separately
        else:
            return _unit_square_vertices()

    def _auto_range(self, matrix: List[List[float]], shape: str) -> float:
        """Compute a good axis range that fits both original and transformed shape."""
        test_points = _unit_square_vertices() + _unit_circle_points(16)
        max_coord = 1.5
        for p in test_points:
            tp = _mat_mul(matrix, p)
            max_coord = max(max_coord, abs(tp[0]) + 0.5, abs(tp[1]) + 0.5)
        return min(max_coord, 8.0)  # Cap at 8 to keep things readable

    @staticmethod
    def _valid_matrix(m: Any) -> bool:
        if not isinstance(m, list) or len(m) != 2:
            return False
        for row in m:
            if not isinstance(row, list) or len(row) != 2:
                return False
            for val in row:
                if not isinstance(val, (int, float)):
                    return False
        return True

    @staticmethod
    def _arrow_markers() -> str:
        return """
<marker id="mt-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="#333"/>
</marker>
<marker id="mt-arrow-basis" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
  <polygon points="0 0, 8 3, 0 6" fill="currentColor"/>
</marker>
"""

    @staticmethod
    def _styles() -> str:
        return """
.mt-grid { stroke: #e8e8e8; stroke-width: 0.7; }
.mt-axis { stroke: #aaa; stroke-width: 1; }
.mt-panel-label { font-size: 12px; font-family: sans-serif; fill: #555; font-weight: 600; }
.mt-caption { font-size: 12px; font-family: sans-serif; fill: #333; }
.mt-matrix-label { font-size: 13px; font-family: sans-serif; fill: #333; font-weight: bold; font-style: italic; }
.mt-vec-label { font-size: 10px; font-family: sans-serif; font-style: italic; }
.mt-eigen-label { font-size: 10px; font-family: sans-serif; fill: #F59E0B; font-weight: 600; }
"""
