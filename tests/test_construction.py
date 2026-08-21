"""Phase 2: the construction model.

The claims are checked in Phase 5; what is checked here is that the model these
claims will be made *about* is right — that the vesica really produces four
points and not five, that the line through them really is vertical, and that
re-drawing something already present changes nothing.

Every assertion below is exact. ``(E.x - F.x).is_zero()`` is a proof that the
line is vertical, not a measurement that it nearly is, and that distinction is
the whole reason the kernel underneath exists.
"""
from __future__ import annotations

from fractions import Fraction

import pytest

from straightedge.geometry.exact import Exact
from straightedge.geometry.model import (
    Circle,
    Construction,
    Line,
    Point,
    intersect_circles,
    intersect_line_circle,
    intersect_lines,
    radical_line,
)


def vesica() -> Construction:
    """A=(0,0), B=(1,0), the two circles each through the other's centre."""
    c = Construction("vesica")
    a = c.set_point(0, 0)
    b = c.set_point(1, 0)
    c.construct_circle(a, b)
    c.construct_circle(b, a)
    return c


class TestTheVesica:
    def test_two_circles_make_exactly_four_points(self):
        c = vesica()
        assert sorted(c.points) == ["A", "B", "C", "D"]

    def test_the_new_points_are_exactly_where_they_belong(self):
        c = vesica()
        for name in ("C", "D"):
            point = c.points[name]
            assert (point.x - Fraction(1, 2)).is_zero()
            assert (point.y * point.y - Fraction(3, 4)).is_zero()

    def test_the_line_through_them_is_exactly_vertical(self):
        c = vesica()
        e, f = c.points["C"], c.points["D"]
        assert (e.x - f.x).is_zero()
        assert not (e.y - f.y).is_zero()

    def test_the_triangle_is_exactly_equilateral(self):
        c = vesica()
        a, b, e = c.points["A"], c.points["B"], c.points["C"]
        from straightedge.geometry.model import Segment
        ab, ae, be = (Segment(a, b).length_sq, Segment(a, e).length_sq,
                      Segment(b, e).length_sq)
        assert (ab - ae).is_zero() and (ab - be).is_zero()

    def test_it_costs_exactly_one_generator(self):
        """√3 and nothing else. A construction that adjoins more than it needs
        spends a depth budget it will want later."""
        assert vesica().tower.depth == 1

    def test_drawing_the_line_adds_no_new_points(self):
        """CD already meets both circles at C and D; dedup must see that."""
        c = vesica()
        before = len(c)
        c.construct_line("C", "D")
        assert sorted(c.points) == ["A", "B", "C", "D"]
        assert len(c) == before + 1              # the line itself, nothing more


class TestRedrawingChangesNothing:
    def test_a_duplicate_circle_does_not_grow_the_model(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        first = c.construct_circle(a, b)
        size = len(c)
        again = c.construct_circle(a, b)
        assert again == first and len(c) == size

    def test_a_line_is_the_same_line_from_either_end(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 1)
        assert c.construct_line(a, b) == c.construct_line(b, a)
        assert len(c.lines) == 1

    def test_a_duplicate_point_returns_the_existing_name(self):
        c = Construction()
        first = c.set_point(2, 3)
        assert c.set_point(2, 3) == first
        assert c.set_point(Fraction(4, 2), 3) == first
        assert len(c.points) == 1


class TestGuidesAreScaffolding:
    def test_a_guide_circle_contributes_no_intersections(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        c.construct_circle(a, b, guide=True)
        c.construct_circle(b, a, guide=True)
        assert sorted(c.points) == ["A", "B"]

    def test_a_guide_is_still_in_the_model(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        circle = c.construct_circle(a, b, guide=True)
        assert circle in c and c[circle].guide

    def test_a_real_element_ignores_a_guide_when_crossing(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        c.construct_circle(a, b, guide=True)
        c.construct_circle(b, a)                 # real, but the only peer is a guide
        assert sorted(c.points) == ["A", "B"]


class TestLineage:
    def test_parents_are_what_defined_it_and_children_what_it_made(self):
        c = vesica()
        circle = c["( A B )"]
        assert circle.parents == ("A", "B")
        assert sorted(circle.children) == ["C", "D"]
        assert c["C"].parents == ("( B A )", "( A B )")
        assert c["C"].children == []

    def test_a_defining_point_never_gains_an_intersection_as_a_parent(self):
        """The bidirectional-parents mistake: a point's parents stay empty."""
        c = vesica()
        assert c["A"].parents == ()
        assert "( A B )" in c["A"].children

    def test_ancestors_walks_parents_only(self):
        c = vesica()
        assert set(c.ancestors("C")) == {"( A B )", "( B A )", "A", "B"}
        assert c.ancestors("A") == []

    def test_ancestors_terminates_on_a_cycle(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        c._elements[a].parents = (b,)            # force a cycle the API cannot make
        c._elements[b].parents = (a,)
        assert sorted(c.ancestors(a)) == ["A", "B"]


class TestNamingAndOrder:
    def test_points_are_named_in_order(self):
        c = Construction()
        assert [c.set_point(i, 0) for i in range(4)] == ["A", "B", "C", "D"]

    def test_structures_are_named_by_their_notation(self):
        c = vesica()
        assert "( A B )" in c and "( B A )" in c
        c.construct_line("C", "D")
        assert "[ C D ]" in c

    def test_insertion_order_is_construction_order(self):
        c = vesica()
        assert [e.id for e in c] == ["A", "B", "( A B )", "( B A )", "C", "D"]

    def test_the_same_construction_twice_gives_the_same_names(self):
        assert [e.id for e in vesica()] == [e.id for e in vesica()]


class TestIntersectionMath:
    def test_two_lines_cross_once(self):
        c = Construction()
        a, b = Point(Exact.rational(0), Exact.rational(0)), Point(Exact.rational(2), Exact.rational(2))
        p, q = Point(Exact.rational(0), Exact.rational(2)), Point(Exact.rational(2), Exact.rational(0))
        [hit] = intersect_lines(Line.through(a, b), Line.through(p, q))
        assert (hit.x - 1).is_zero() and (hit.y - 1).is_zero()

    def test_parallel_lines_do_not_cross(self):
        o, i = Exact.rational(0), Exact.rational(1)
        one = Line.through(Point(o, o), Point(i, o))
        two = Line.through(Point(o, i), Point(i, i))
        assert intersect_lines(one, two) == []

    def test_a_tangent_line_touches_once(self):
        c = Construction()
        o, r = Exact.rational(0), Exact.rational(1)
        circle = Circle(Point(o, o), Exact.rational(1))
        tangent = Line.through(Point(r, -r), Point(r, r))          # x == 1
        hits = intersect_line_circle(c.tower, tangent, circle)
        assert len(hits) == 1
        assert (hits[0].x - 1).is_zero() and hits[0].y.is_zero()

    def test_a_missing_line_touches_nothing(self):
        c = Construction()
        o = Exact.rational(0)
        circle = Circle(Point(o, o), Exact.rational(1))
        far = Line.through(Point(Exact.rational(5), Exact.rational(-1)),
                           Point(Exact.rational(5), Exact.rational(1)))
        assert intersect_line_circle(c.tower, far, circle) == []

    def test_the_radical_line_of_the_vesica_is_x_equals_a_half(self):
        o, i = Exact.rational(0), Exact.rational(1)
        one = Circle(Point(o, o), Exact.rational(1))
        two = Circle(Point(i, o), Exact.rational(1))
        line = radical_line(one, two)
        assert line is not None
        assert line.b.is_zero()                                   # no y term
        assert (line.c + Fraction(1, 2)).is_zero()                # x - 1/2 == 0

    def test_concentric_circles_have_no_radical_line(self):
        o = Exact.rational(0)
        one = Circle(Point(o, o), Exact.rational(1))
        two = Circle(Point(o, o), Exact.rational(4))
        assert radical_line(one, two) is None

    def test_disjoint_circles_do_not_meet(self):
        c = Construction()
        o = Exact.rational(0)
        one = Circle(Point(o, o), Exact.rational(1))
        two = Circle(Point(Exact.rational(10), o), Exact.rational(1))
        assert intersect_circles(c.tower, one, two) == []


class TestRefusals:
    def test_a_line_needs_two_distinct_points(self):
        c = Construction()
        a = c.set_point(0, 0)
        b = c.set_point(0, 0)                     # dedups to A
        with pytest.raises(ValueError, match="distinct"):
            c.construct_line(a, b)

    def test_a_circle_needs_a_radius(self):
        c = Construction()
        a = c.set_point(0, 0)
        with pytest.raises(ValueError, match="radius"):
            c.construct_circle(a, a)

    def test_an_unknown_id_is_refused(self):
        c = Construction()
        a = c.set_point(0, 0)
        with pytest.raises(KeyError):
            c.construct_line(a, "Z")

    def test_a_structure_cannot_stand_in_for_a_point(self):
        c = vesica()
        with pytest.raises(TypeError, match="not a point"):
            c.construct_line("( A B )", "A")

    def test_a_section_must_be_collinear(self):
        c = vesica()
        with pytest.raises(ValueError, match="collinear"):
            c.set_section("A", "B", "C")

    def test_a_collinear_section_is_accepted(self):
        c = Construction()
        a, b, d = c.set_point(0, 0), c.set_point(1, 0), c.set_point(3, 0)
        assert c.set_section(a, b, d) == "/ A B C /"

    def test_a_polygon_needs_three_points(self):
        c = Construction()
        a, b = c.set_point(0, 0), c.set_point(1, 0)
        with pytest.raises(ValueError, match="three"):
            c.set_polygon(a, b)


class TestExtent:
    def test_limits_cover_the_circles_not_just_the_points(self):
        c = vesica()
        min_x, min_y, max_x, max_y = c.limits()
        assert min_x == pytest.approx(-1.0) and max_x == pytest.approx(2.0)
        assert min_y == pytest.approx(-1.0) and max_y == pytest.approx(1.0)

    def test_an_empty_construction_still_has_a_box(self):
        assert Construction().limits() == (0.0, 0.0, 1.0, 1.0)

    def test_asking_for_the_extent_does_not_grow_the_field(self):
        """Measuring must not change what is measured: an exact bound would
        adjoin √(r²) as a side effect of asking about the viewBox."""
        c = vesica()
        before = c.tower.depth
        c.limits()
        assert c.tower.depth == before


class TestPerpendicularBisector:
    def test_the_classical_construction_is_exact(self):
        """The vesica's line is the perpendicular bisector of AB — and here that
        is proved rather than observed: it passes through the midpoint, and its
        direction dotted with AB is exactly zero."""
        c = vesica()
        c.construct_line("C", "D")
        bisector = c.lines["[ C D ]"]
        a, b = c.points["A"], c.points["B"]

        midpoint = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
        assert bisector.contains(midpoint)

        ab = Line.through(a, b)
        dot = bisector.a * ab.a + bisector.b * ab.b
        assert dot.is_zero()


class TestArcs:
    """Circles are drawn whole everywhere else, and deliberately.

    An arc is the exception a sectional figure needs: a hemisphere in section is
    a semicircle, and drawing the whole circle says something false about the
    solid.
    """

    @staticmethod
    def _hemisphere():
        c = Construction()
        o, right, left = c.set_point(0, 0), c.set_point(200, 0), c.set_point(-200, 0)
        return c, c.construct_arc(o, right, left)

    def test_an_arc_is_named_for_its_notation(self):
        c, arc = self._hemisphere()
        assert arc == "( A B ~ C )"

    def test_both_ends_must_be_on_the_circle(self):
        """An arbitrary direction would need the square root of a length, which
        is not in general constructible — so an arc could only be placed
        approximately, in the one lane where nothing is approximate."""
        c = Construction()
        o, right = c.set_point(0, 0), c.set_point(200, 0)
        with pytest.raises(ValueError, match="ends on its own circle"):
            c.construct_arc(o, right, c.set_point(0, 150))

    def test_an_arc_needs_a_radius(self):
        c = Construction()
        o = c.set_point(0, 0)
        with pytest.raises(ValueError, match="radius"):
            c.construct_arc(o, o, c.set_point(1, 0))

    def test_a_half_turn_is_not_reflex(self):
        c, arc = self._hemisphere()
        assert c[arc].geometry.reflex is False

    def test_more_than_a_half_turn_is_reflex(self):
        c = Construction()
        o = c.set_point(0, 0)
        arc = c.construct_arc(o, c.set_point(1, 0), c.set_point(0, -1))
        assert c[arc].geometry.reflex is True

    def test_an_arc_intersects_as_its_whole_circle(self):
        """It restricts what is drawn, never what is known. A point on the
        hidden part is still a fact about the construction."""
        c, _ = self._hemisphere()
        c.construct_line(c.set_point(0, -50), c.set_point(1, -50))
        # The two points that *defined* the line sit at y = -50 as well, so count
        # only the ones the crossing produced.
        found = [e for e in c
                 if e.kind == "point" and "intersection" in e.classes
                 and float(e.geometry.y) < -49]
        assert len(found) == 2, "the line met the circle where the arc is not drawn"

    def test_the_extent_is_the_sweep_not_the_circle(self):
        """Reserving the whole circle for a semicircle wastes half the page."""
        c, _ = self._hemisphere()
        min_x, min_y, max_x, max_y = c.limits()
        assert max_y == pytest.approx(200.0)
        assert min_y == pytest.approx(0.0), "the lower half is not part of the arc"

    def test_a_full_circle_still_bounds_all_four_ways(self):
        c = Construction()
        o = c.set_point(0, 0)
        c.construct_circle(o, c.set_point(200, 0))
        _, min_y, _, max_y = c.limits()
        assert min_y == pytest.approx(-200.0) and max_y == pytest.approx(200.0)
