"""Phase 3: the construction notation.

The load-bearing test here is ``test_every_documented_form_parses``. A published
implementation of this idea shipped a CLI banner advertising ``} A B C {`` for a
section while its parser implemented ``/ A B C /`` — the help text lied, and
nothing in the suite could tell. Here the documented forms and the accepted forms
are the same tuple, and the test parses every one of them.

The other theme is refusal. A construction is a sequence, and a step missing from
the middle of one does not make a smaller drawing — it makes a different drawing
that still looks finished. So a line that is not a form stops the parse with its
number, and the message says which form was nearly written rather than "invalid
syntax".
"""
from __future__ import annotations

import pytest

from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.construction import build, normalise_steps, verify
from straightedge.geometry.notation import (
    FORMS,
    NotationError,
    parse,
    parse_line,
)

VESICA = """
# the vesica, and the bisector it proves
A = 0, 0
B = 1, 0
( A B )
( B A )
[ C D ]
"""


class TestTheDocumentationIsTheGrammar:
    @pytest.mark.parametrize("form", [f for f, _ in FORMS])
    def test_every_documented_form_parses(self, form):
        """Whatever the docstring shows, the parser must accept."""
        parse_line(form)          # raises if it does not

    def test_the_module_docstring_shows_the_same_forms(self):
        from straightedge.geometry import notation
        for form, _ in FORMS:
            assert form in notation.__doc__, f"{form!r} documented nowhere"

    def test_the_forms_cover_every_element_the_model_has(self):
        kinds = set()
        for form, _ in FORMS:
            step = parse_line(form)
            if step:
                kinds |= {k for k in step if k not in ("id", "guide", "names")}
        assert kinds == {"point", "line", "circle", "polygon", "section"}


class TestTheForms:
    def test_a_named_point(self):
        assert parse_line("A = 0, 0") == {"point": ["0", "0"], "id": "A"}

    def test_an_unnamed_point(self):
        assert parse_line("* 1, 0") == {"point": ["1", "0"]}

    def test_a_line_and_a_circle(self):
        assert parse_line("[ A B ]") == {"line": ["A", "B"]}
        assert parse_line("( A B )") == {"circle": ["A", "B"]}

    def test_a_polygon_and_a_section(self):
        assert parse_line("< A B C >") == {"polygon": ["A", "B", "C"]}
        assert parse_line("/ A B C /") == {"section": ["A", "B", "C"]}

    def test_naming_what_a_step_produces(self):
        assert parse_line("( B A ) -> C D") == {
            "circle": ["B", "A"], "names": ["C", "D"]}
        assert parse_line("[ A B ] -> M") == {"line": ["A", "B"], "names": ["M"]}

    def test_a_guide(self):
        assert parse_line("( A B ) guide") == {"circle": ["A", "B"], "guide": True}

    def test_comments_and_blanks_are_not_steps(self):
        assert parse_line("# anything") is None
        assert parse_line("   ") is None
        assert parse_line("[ A B ]  # the base") == {"line": ["A", "B"]}

    def test_coordinates_keep_their_written_form(self):
        """Exactness starts here: the text is handed on, not floated."""
        assert parse_line("A = 0.1, 1/3") == {"point": ["0.1", "1/3"], "id": "A"}
        assert parse_line("A = -2, +3") == {"point": ["-2", "+3"], "id": "A"}

    def test_whitespace_is_not_significant(self):
        assert parse_line("[A B]") == parse_line("[   A   B   ]")
        assert parse_line("A=0,0") == parse_line("A  =  0 ,  0")


class TestRefusalsNameTheMistake:
    @pytest.mark.parametrize("line,expected", [
        ("[ A B", "never closed"),
        ("( A B", "never closed"),
        ("[ A ]", "two point names"),
        ("( A B C )", "a centre and a point"),
        ("/ A B /", "three collinear points"),
        ("< A B >", "at least three points"),
        ("A = 0", "written `NAME = x, y`"),
        ("* 1", "written `* x, y`"),
        ("wat", "not a construction step"),
    ])
    def test_the_reason_is_specific(self, line, expected):
        with pytest.raises(NotationError) as excinfo:
            parse_line(line)
        assert expected in excinfo.value.reason

    def test_the_line_number_is_carried(self):
        with pytest.raises(NotationError) as excinfo:
            parse("A = 0, 0\nB = 1, 0\n[ A\n")
        assert excinfo.value.line_number == 3
        assert "line 3" in str(excinfo.value)

    def test_a_bad_line_stops_the_whole_parse(self):
        """All or nothing: a construction missing its third step is a different
        construction, not a shorter one."""
        with pytest.raises(NotationError):
            parse("A = 0, 0\n[ A\nB = 1, 0")

    def test_a_name_cannot_be_a_number(self):
        with pytest.raises(NotationError):
            parse_line("[ 1 2 ]")


class TestParsingAWholeConstruction:
    def test_the_vesica(self):
        assert parse(VESICA) == [
            {"point": ["0", "0"], "id": "A"},
            {"point": ["1", "0"], "id": "B"},
            {"circle": ["A", "B"]},
            {"circle": ["B", "A"]},
            {"line": ["C", "D"]},
        ]

    def test_it_builds_the_same_model_as_the_structured_form(self):
        from_notation = build(VESICA)
        from_dicts = build([
            {"point": [0, 0], "id": "A"}, {"point": [1, 0], "id": "B"},
            {"circle": ["A", "B"]}, {"circle": ["B", "A"]}, {"line": ["C", "D"]}])
        assert [e.id for e in from_notation] == [e.id for e in from_dicts]
        assert from_notation.tower.depth == from_dicts.tower.depth

    def test_it_finds_the_intersections_nobody_named(self):
        construction = build(VESICA)
        assert sorted(construction.points) == ["A", "B", "C", "D"]


class TestTheTemplateAcceptsEitherForm:
    def _marks(self, steps):
        return count_data_marks(
            render_diagram({"type": "construction", "params": {"steps": steps}}))

    def test_one_document(self):
        assert self._marks(VESICA) > 0

    def test_a_list_of_lines(self):
        assert self._marks(["A = 0, 0", "B = 1, 0", "( A B )", "( B A )"]) > 0

    def test_notation_and_mappings_mixed(self):
        assert self._marks(["A = 0, 0", {"point": [1, 0], "id": "B"}, "( A B )"]) > 0

    def test_normalise_is_idempotent_on_mappings(self):
        steps = [{"point": [0, 0], "id": "A"}]
        assert normalise_steps(steps) == steps

    def test_a_bad_line_draws_nothing(self):
        assert self._marks("A = 0, 0\n[ A ") == 0

    def test_verify_reports_the_line_rather_than_a_stack_trace(self):
        findings = verify({"steps": "A = 0, 0\n[ A "})
        assert len(findings) == 1
        assert findings[0].check == "construction:notation"
        assert "line 2" in findings[0].message

    def test_claims_still_decide_over_notation(self):
        findings = verify({
            "steps": VESICA + "[ A B ]\n",
            "claims": [{"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]}]})
        assert findings == []

    def test_a_false_claim_over_notation_still_refuses_to_draw(self):
        svg = render_diagram({"type": "construction", "params": {
            "steps": VESICA + "[ A B ]\n",
            "claims": [{"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}]}})
        assert count_data_marks(svg) == 0


class TestFoundPointsCanBeNamed:
    """Automatic names shift, and a line written against them changes meaning.

    Inserting one anonymous point moved the vesica's crossings from `C, D` to
    `D, E`, so `[ C D ]` silently joined two different points — no error, a
    plausible figure. Naming what a step produces is the fix; ordering them by
    geometry is what makes the name mean something.
    """

    BASE = ["A = 0, 0", "B = 1, 0", "( A B )"]

    def test_automatic_names_do_shift(self):
        """The problem, pinned, so the fix cannot quietly stop mattering."""
        plain = build(self.BASE + ["( B A )"])
        shifted = build(self.BASE[:2] + ["* 9, 9"] + self.BASE[2:] + ["( B A )"])
        upper_plain = [k for k, v in plain.points.items() if float(v.y) > 0.5]
        upper_shifted = [k for k, v in shifted.points.items() if float(v.y) > 0.5]
        assert upper_plain == ["C"]
        assert upper_shifted != ["C"]

    def test_a_name_survives_an_earlier_step(self):
        for extra in ([], ["* 9, 9"], ["* 9, 9", "* 8, 8"]):
            c = build(self.BASE[:2] + extra + self.BASE[2:] + ["( B A ) -> UP LOW"])
            assert float(c.points["UP"].y) > 0.5
            assert float(c.points["LOW"].y) < -0.5

    def test_the_order_is_geometric_not_algebraic(self):
        """Upper first, then left to right — a fact about the drawing."""
        c = build(self.BASE + ["( B A ) -> FIRST SECOND"])
        assert float(c.points["FIRST"].y) > float(c.points["SECOND"].y)

    def test_naming_more_points_than_a_step_makes_is_refused(self):
        """Two concentric circles produce nothing; asking to name two says so."""
        with pytest.raises(ValueError, match="name"):
            build(["O = 0, 0", "X = 2, 0", "( O X )", "E = 1, 0", "( O E ) -> P Q"])

    def test_naming_fewer_is_fine(self):
        c = build(self.BASE + ["( B A ) -> UP"])
        assert "UP" in c.points and len(c.points) == 4

    def test_a_named_point_is_still_an_intersection(self):
        c = build(self.BASE + ["( B A ) -> UP LOW"])
        assert "intersection" in c["UP"].classes
