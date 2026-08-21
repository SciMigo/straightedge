"""Phase 5: the claims — the reason the rest of the lane exists.

A construction that draws is easy. What is checked here is a construction that
*asserts*, and is refused when the assertion is false.

The case worth reading is ``test_a_three_decimal_approximation_is_not_golden``.
1.618 is right to three places and is not φ, and every float-based checker in
existence says it is golden. This one says it is not, because ``is_zero`` is a
proof. That single distinction is the whole argument for the exact kernel
underneath.
"""
from __future__ import annotations

from fractions import Fraction

import pytest

from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.construction import verify
from straightedge.geometry import exact as exact_module
from straightedge.geometry.claims import CLAIMS, Claim, check
from straightedge.geometry.model import Construction
from straightedge.qc import worst_severity


def vesica() -> Construction:
    c = Construction("vesica")
    a, b = c.set_point(0, 0), c.set_point(1, 0)
    c.construct_circle(a, b)
    c.construct_circle(b, a)
    c.construct_line("C", "D")
    c.construct_line(a, b)
    return c


def holds(construction: Construction, *claims) -> bool:
    return check(construction, list(claims)) == []


class TestTheVesicaProvesItself:
    def test_the_axis_is_perpendicular_to_the_base(self):
        assert holds(vesica(), {"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]})

    def test_the_axis_passes_through_the_midpoint(self):
        assert holds(vesica(), {"claim": "midpoint", "of": ["G", "A", "B"]})

    def test_the_triangle_is_equilateral(self):
        c = vesica()
        c.set_polygon("A", "B", "C")
        assert holds(c, {"claim": "equilateral", "of": "< A B C >"})

    def test_congruence_of_the_three_sides(self):
        assert holds(vesica(), {"claim": "congruent",
                                "of": [["A", "B"], ["A", "C"], ["B", "C"]]})

    def test_the_new_points_are_on_both_circles(self):
        c = vesica()
        assert holds(c, {"claim": "on", "of": ["C", "( A B )"]},
                     {"claim": "on", "of": ["C", "( B A )"]})

    def test_what_is_false_is_reported_as_false(self):
        findings = check(vesica(), [
            {"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]},
            {"claim": "on", "of": ["A", "( A B )"]},
            {"claim": "midpoint", "of": ["A", "C", "D"]},
        ])
        assert len(findings) == 3
        assert all(f.severity == "error" for f in findings)
        assert all(f.box is not None for f in findings)


class TestGolden:
    def test_an_exact_golden_section_holds(self):
        c = Construction()
        phi = (1 + c.tower.sqrt(5)) / 2
        a = c.set_point(0, 0)
        b = c.set_point(phi, 0)
        d = c.set_point(phi + 1, 0)
        assert holds(c, {"claim": "golden", "of": c.set_section(a, b, d)})

    def test_a_three_decimal_approximation_is_not_golden(self):
        """1.618 is not φ, and saying so is the point of the whole lane."""
        c = Construction()
        a = c.set_point(0, 0)
        b = c.set_point(Fraction(1618, 1000), 0)
        d = c.set_point(Fraction(2618, 1000), 0)
        findings = check(c, [{"claim": "golden", "of": c.set_section(a, b, d)}])
        assert len(findings) == 1 and findings[0].severity == "error"

    def test_it_holds_whichever_part_is_the_greater(self):
        c = Construction()
        phi = (1 + c.tower.sqrt(5)) / 2
        a = c.set_point(0, 0)
        b = c.set_point(1, 0)                 # short part first
        d = c.set_point(1 + phi, 0)
        assert holds(c, {"claim": "golden", "of": c.set_section(a, b, d)})

    def test_deciding_it_adjoins_nothing(self):
        """AB⁴ == AC²·BC² has no root in it, so checking costs the field nothing."""
        c = Construction()
        phi = (1 + c.tower.sqrt(5)) / 2
        a, b, d = (c.set_point(0, 0), c.set_point(phi, 0), c.set_point(phi + 1, 0))
        section = c.set_section(a, b, d)
        before = c.tower.depth
        check(c, [{"claim": "golden", "of": section}])
        assert c.tower.depth == before


class TestHarmonic:
    """The cross ratio, derived rather than ported.

    ``(A,B;C,D) == −1`` is ``(AC·BD)/(AD·BC) == −1``. A published implementation
    of this used ``CD`` where ``BD`` belongs, which is a different quantity and
    therefore a different predicate — so the condition here is derived from the
    cross ratio and pinned against a set worked out by hand.
    """

    def test_a_known_harmonic_range(self):
        # A=0, B=1, C=1/3, D=-1: (C-A)(D-B) + (D-A)(C-B) = -2/3 + 2/3 = 0
        c = Construction()
        names = [c.set_point(x, 0) for x in (0, 1, Fraction(1, 3), -1)]
        assert holds(c, {"claim": "harmonic", "of": names})

    def test_a_near_miss_is_rejected(self):
        c = Construction()
        names = [c.set_point(x, 0) for x in (0, 1, Fraction(1, 3), -2)]
        assert not holds(c, {"claim": "harmonic", "of": names})

    def test_the_wrong_segment_would_have_passed_the_wrong_set(self):
        """Guards the specific error: using CD in place of BD.

        For A=0, B=1, C=1/3, D=1/2 the *mistaken* condition AD·BC == AC·CD is
        satisfied while the true cross ratio is not −1. A port of the published
        predicate accepts this set; this one must not.
        """
        c = Construction()
        names = [c.set_point(x, 0) for x in (0, 1, Fraction(1, 3), Fraction(1, 2))]
        assert not holds(c, {"claim": "harmonic", "of": names})

    def test_four_points_must_be_collinear(self):
        c = Construction()
        names = [c.set_point(*xy) for xy in ((0, 0), (1, 0), (2, 0), (1, 1))]
        findings = check(c, [{"claim": "harmonic", "of": names}])
        assert len(findings) == 1 and "collinear" in findings[0].message


class TestTheRest:
    def test_ratio(self):
        c = Construction()
        a, b, d = c.set_point(0, 0), c.set_point(2, 0), c.set_point(3, 0)
        section = c.set_section(a, b, d)
        assert holds(c, {"claim": "ratio", "of": section, "value": 2})
        assert not holds(c, {"claim": "ratio", "of": section, "value": 3})

    def test_tangent(self):
        c = Construction()
        o, r = c.set_point(0, 0), c.set_point(1, 0)
        t1, t2 = c.set_point(1, -1), c.set_point(1, 1)
        circle = c.construct_circle(o, r)
        assert holds(c, {"claim": "tangent", "of": [circle, c.construct_line(t1, t2)]})

    def test_a_secant_is_not_tangent(self):
        c = Construction()
        o, r = c.set_point(0, 0), c.set_point(1, 0)
        t1, t2 = c.set_point(0, -2), c.set_point(0, 2)
        circle = c.construct_circle(o, r)
        assert not holds(c, {"claim": "tangent", "of": [circle, c.construct_line(t1, t2)]})

    def test_concurrent(self):
        c = vesica()
        assert holds(c, {"claim": "concurrent", "of": ["[ C D ]", "[ A B ]", "[ C D ]"]})

    def test_collinear_and_parallel(self):
        c = Construction()
        a, b, d = c.set_point(0, 0), c.set_point(1, 1), c.set_point(2, 2)
        assert holds(c, {"claim": "collinear", "of": [a, b, d]})
        e, f = c.set_point(0, 1), c.set_point(1, 2)
        assert holds(c, {"claim": "parallel",
                         "of": [c.construct_line(a, b), c.construct_line(e, f)]})

    def test_every_claim_in_the_table_is_reachable(self):
        """The vocabulary and the documented table cannot drift apart."""
        assert set(CLAIMS) == {
            "on", "collinear", "parallel", "perpendicular", "congruent",
            "midpoint", "equilateral", "tangent", "concurrent", "ratio",
            "golden", "harmonic"}


class TestRefusalsRatherThanSilence:
    def test_an_unknown_claim_is_an_error_not_a_pass(self):
        findings = check(vesica(), [{"claim": "wobbly", "of": ["A"]}])
        assert len(findings) == 1 and findings[0].severity == "error"
        assert "known claims are" in findings[0].message

    def test_a_claim_about_something_absent_fails(self):
        """An assertion about what is not there is failed, never skipped."""
        findings = check(vesica(), [{"claim": "perpendicular", "of": ["[ C D ]", "ZZ"]}])
        assert len(findings) == 1 and findings[0].severity == "error"

    def test_a_malformed_claim_is_an_error(self):
        assert check(vesica(), [{"of": ["A"]}])[0].check == "claim:malformed"
        assert check(vesica(), ["not a mapping"])[0].check == "claim:malformed"

    def test_a_claim_that_cannot_be_certified_warns_and_never_passes(self, monkeypatch):
        """The cap is reached: neither proved nor disproved, and never a pass.

        Coordinates large enough that the products in the predicate outgrow a
        lowered ceiling — the vesica's own coefficients are 0 and 1 and would
        never reach it.
        """
        c = Construction()
        big = 10 ** 30
        a, b, d = c.set_point(0, 0), c.set_point(big, big), c.set_point(2 * big, 2 * big)
        monkeypatch.setattr(exact_module, "MAX_BITS", 16)
        findings = check(c, [{"claim": "collinear", "of": [a, b, d]}])
        assert len(findings) == 1
        assert findings[0].severity == "warn"
        assert "neither proved nor disproved" in findings[0].message

    def test_the_float_stage_can_only_ever_reject(self):
        """A holding claim is decided exactly, not dismissed by a float.

        The pre-check exists to skip work; if it could confirm, a claim true only
        to 1e-9 would pass. Scaling coordinates far up keeps the residual
        exactly zero while the float arithmetic grows noisier.
        """
        c = Construction()
        big = 10 ** 12
        a, b, d = c.set_point(0, 0), c.set_point(big, big), c.set_point(2 * big, 2 * big)
        assert holds(c, {"claim": "collinear", "of": [a, b, d]})


class TestTheTemplateRefusesToDrawAFalsehood:
    STEPS = [
        {"point": [0, 0], "id": "A"}, {"point": [1, 0], "id": "B"},
        {"circle": ["A", "B"]}, {"circle": ["B", "A"]},
        {"line": ["C", "D"]}, {"line": ["A", "B"]},
    ]

    def _render(self, claims):
        return render_diagram({"type": "construction",
                               "params": {"steps": self.STEPS, "claims": claims}})

    def test_a_true_claim_draws(self):
        svg = self._render([{"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]}])
        assert count_data_marks(svg) > 0

    def test_a_false_claim_draws_nothing(self):
        svg = self._render([{"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}])
        assert count_data_marks(svg) == 0

    def test_a_warning_does_not_block_the_drawing(self, monkeypatch):
        """Uncertified is not disproved, so the figure still renders.

        The cap is set where the construction builds comfortably but `golden`
        does not: its predicate squares a squared length, so it reaches fourth
        powers of the coordinates while building never leaves second.
        """
        params = {"steps": [{"point": [0, 0], "id": "A"},
                            {"point": [10 ** 4, 0], "id": "B"},
                            {"point": [3 * 10 ** 4, 0], "id": "C"},
                            {"section": ["A", "B", "C"], "id": "S"}],
                  "claims": [{"claim": "golden", "of": "S"}]}
        monkeypatch.setattr(exact_module, "MAX_BITS", 32)
        svg = render_diagram({"type": "construction", "params": params})
        assert count_data_marks(svg) > 0

    def test_verify_reports_without_drawing(self):
        params = {"steps": self.STEPS,
                  "claims": [{"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}]}
        findings = verify(params)
        assert worst_severity(findings) == "error"
        assert verify({"steps": self.STEPS}) == []

    def test_verify_reports_an_unbuildable_construction(self):
        assert verify({"steps": [{"line": ["A", "B"]}]})[0].check == "construction:unbuildable"
        assert verify({})[0].check == "construction:empty"


class TestClaimParsing:
    def test_a_claim_renders_readably(self):
        assert str(Claim.parse({"claim": "golden", "of": "/ A B C /"})) == "golden(/ A B C /)"
        assert str(Claim.parse({"claim": "ratio", "of": "s", "value": 2})) == "ratio(s) == 2"

    def test_a_bare_argument_is_accepted(self):
        assert Claim.parse({"claim": "golden", "of": "/ A B C /"}).of == ("/ A B C /",)


class TestAPredicateOwnsItsDomain:
    """Exact arithmetic on a degenerate figure proves undefined statements.

    Every squared length of a section on one repeated point is zero, so
    `AB² == r²·BC²` holds for *every* r and `AB⁴ == AC²·BC²` holds trivially.
    The collapsed section was reported as being in ratio 12345 *and* as golden,
    with total confidence and by exact arithmetic — which is the failure this
    whole lane exists to prevent, arriving through the door it was guarding.
    """

    @staticmethod
    def _collapsed():
        c = Construction()
        a = c.set_point(0, 0)
        return c, c.set_section(a, a, a), a

    @pytest.mark.parametrize("claim", [
        {"claim": "ratio", "value": 12345},
        {"claim": "ratio", "value": 1},
        {"claim": "golden"},
    ])
    def test_a_section_with_no_length_decides_nothing(self, claim):
        c, section, _ = self._collapsed()
        findings = check(c, [dict(claim, of=section)])
        assert len(findings) == 1 and findings[0].severity == "error"
        assert "zero length" in findings[0].message

    def test_a_degenerate_range_is_not_harmonic(self):
        c, _, a = self._collapsed()
        findings = check(c, [{"claim": "harmonic", "of": [a, a, a, a]}])
        assert len(findings) == 1
        assert "four distinct points" in findings[0].message

    def test_two_coincident_points_break_a_harmonic_range(self):
        c = Construction()
        names = [c.set_point(x, 0) for x in (0, 1, Fraction(1, 3), -1)]
        findings = check(c, [{"claim": "harmonic", "of": [names[0], names[0],
                                                          names[2], names[3]]}])
        assert len(findings) == 1 and "coincide" in findings[0].message

    def test_a_negative_ratio_is_refused_rather_than_squared_away(self):
        """Squaring loses the sign, so -2 would be satisfied by 2."""
        c = Construction()
        a, b, d = c.set_point(0, 0), c.set_point(2, 0), c.set_point(3, 0)
        section = c.set_section(a, b, d)
        findings = check(c, [{"claim": "ratio", "of": section, "value": -2}])
        assert len(findings) == 1 and "must be positive" in findings[0].message
        assert check(c, [{"claim": "ratio", "of": section, "value": 2}]) == []

    def test_a_real_section_is_untouched_by_the_guards(self):
        c = Construction()
        phi = (1 + c.tower.sqrt(5)) / 2
        a, b, d = c.set_point(0, 0), c.set_point(phi, 0), c.set_point(phi + 1, 0)
        assert check(c, [{"claim": "golden", "of": c.set_section(a, b, d)}]) == []


class TestArityIsCheckedBeforeDispatch:
    """The predicates read `claim.of` positionally.

    An argument that is not there raised out of an unpacking rather than
    returning a finding, so a malformed claim came back through the MCP tool as
    a ValueError with a traceback instead of something a caller could act on.
    """

    @pytest.mark.parametrize("claim,given", [
        ({"claim": "midpoint", "of": ["A"]}, 1),
        ({"claim": "harmonic", "of": ["A", "B"]}, 2),
        ({"claim": "on", "of": ["A"]}, 1),
        ({"claim": "collinear", "of": ["A", "B"]}, 2),
        ({"claim": "congruent", "of": [["A", "B"]]}, 1),
        ({"claim": "equilateral", "of": ["A", "B"]}, 2),
        ({"claim": "concurrent", "of": ["A", "B"]}, 2),
        ({"claim": "tangent", "of": ["A"]}, 1),
    ])
    def test_the_wrong_number_of_arguments_is_a_finding(self, claim, given):
        c = Construction()
        c.set_point(0, 0)
        findings = check(c, [claim])          # must not raise
        assert len(findings) == 1 and findings[0].severity == "error"
        assert f"got {given}" in findings[0].message

    def test_every_claim_declares_its_arity(self):
        from straightedge.geometry.claims import ARITY
        assert set(ARITY) == set(CLAIMS)

    def test_a_correct_arity_still_dispatches(self):
        assert holds(vesica(), {"claim": "midpoint", "of": ["G", "A", "B"]})
