"""The number-theory figures: every number is computed, and the staging contract holds.

These four draw arithmetic — rungs of a squaring ladder, a running product, a
permutation of residues, a totient — and the only thing worse than a blank
figure here is a convincing one with a wrong number in it. So the suite reads
the numbers back out of the SVG and compares them with Python's own ``pow`` and
``gcd``, rather than with literals typed beside the template.
"""
from __future__ import annotations

import re
from math import gcd
from xml.etree import ElementTree as ET

import pytest

from straightedge.diagrams import DIAGRAM_REGISTRY, natural_steps, render_diagram
from straightedge.diagrams.legibility import check_figure
from straightedge.diagrams.registry import count_data_marks, refusal_findings

TEMPLATES = ("bit_selection", "squaring_ladder", "residue_tiles", "coprime_grid")

#: The parameter sets a modular-exponentiation lecture actually uses.
LECTURE = {
    "bit_selection": {"n": 117, "base": 3, "modulus": 19},
    "squaring_ladder": {"base": 3, "modulus": 19, "n": 117, "select": True},
    "residue_tiles": {"p": 7, "a": 3},
    "coprime_grid": {"n": 100},
}


def _svg(kind: str, **params) -> str:
    return render_diagram({"type": kind, "params": params})


def _texts(svg: str) -> list[str]:
    """Every drawn label, tspans joined, so ``3<tspan>64</tspan>`` reads ``364``."""
    root = ET.fromstring(svg)
    return ["".join(el.itertext()).strip() for el in root.iter("{http://www.w3.org/2000/svg}text")]


def _residues(svg: str) -> list[int]:
    return [int(t.split()[-1]) for t in _texts(svg) if re.fullmatch(r"≡ \d+", t)]


class TestTheSquaringLadder:
    @pytest.mark.parametrize("base,modulus,n", [(3, 19, 117), (7, 13, 10), (3, 100, 26), (5, 17, 23)])
    def test_every_rung_is_the_power_pow_computes(self, base, modulus, n):
        svg = _svg("squaring_ladder", base=base, modulus=modulus, n=n)
        expected = [pow(base, 1 << k, modulus) for k in range(n.bit_length())]
        assert _residues(svg) == expected

    def test_the_lecture_ladder(self):
        assert _residues(_svg("squaring_ladder", **LECTURE["squaring_ladder"])) == [3, 9, 5, 6, 17, 4, 16]
        assert _residues(_svg("squaring_ladder", base=7, modulus=13, n=10)) == [7, 10, 9, 3]
        assert _residues(_svg("squaring_ladder", base=3, modulus=100, n=26)) == [3, 9, 81, 61, 21]
        assert _residues(_svg("squaring_ladder", base=5, modulus=17, n=23)) == [5, 8, 13, 16, 1]

    def test_each_rung_squares_the_remainder_below_it(self):
        texts = _texts(_svg("squaring_ladder", base=3, modulus=19, n=117))
        squares = [t for t in texts if "2 = " in t]
        # 9² = 81, 5² = 25, 6² = 36, 17² = 289, 4² = 16: the residue, never the power
        assert squares == ["32 = 9", "92 = 81", "52 = 25", "62 = 36", "172 = 289", "42 = 16"]

    def test_select_names_the_rungs_the_bits_pick(self):
        svg = _svg("squaring_ladder", **LECTURE["squaring_ladder"])
        assert svg.count('class="sl-chosen"') == bin(117).count("1")
        assert any(t.startswith("117 = 11101012") for t in _texts(svg))

    @pytest.mark.parametrize("params", [
        {"base": 3, "modulus": 19},                    # no n
        {"base": 3, "modulus": 1, "n": 5},             # modulus below 2
        {"base": 3, "modulus": 19, "n": 256},          # nine rungs
        {"base": 3, "modulus": 19, "n": True},         # a bool is not a count
        {"base": 3, "modulus": 19, "n": 2.5},
    ])
    def test_bad_input_is_refused_not_drawn(self, params):
        assert refusal_findings("squaring_ladder", params)
        assert _svg("squaring_ladder", **params) == ""


class TestBitSelection:
    def test_the_bits_are_the_binary_expansion(self):
        svg = _svg("bit_selection", n=117)
        digits = re.findall(r'class="bs-bit-(?:on|off)"[^>]*>([01])<', svg)
        assert "".join(digits) == format(117, "b")
        assert re.findall(r'class="bs-bit-on"[^>]*>([01])<', svg) == ["1"] * bin(117).count("1")
        assert svg.count('class="bs-box-on"') == bin(117).count("1")
        assert "117 = 64 + 32 + 16 + 4 + 1" in _texts(svg)

    def test_the_running_product_is_pow(self):
        texts = _texts(_svg("bit_selection", **LECTURE["bit_selection"]))
        assert "3117 = 364 · 332 · 316 · 34 · 31" in texts
        assert "≡ 16 · 4 · 17 · 5 · 3   (mod 19)" in texts
        chain = [t for t in texts if t.startswith("× ")]
        assert chain == ["× 5 = 15", "× 17 = 255 ≡ 8", "× 4 = 32 ≡ 13", "× 16 = 208 ≡ 18"]
        assert f"3117 ≡ {pow(3, 117, 19)}   (mod 19)" in texts

    @pytest.mark.parametrize("n,base,modulus", [(10, 7, 13), (26, 3, 100), (23, 5, 17), (1, 4, 9)])
    def test_other_exponents(self, n, base, modulus):
        texts = _texts(_svg("bit_selection", n=n, base=base, modulus=modulus))
        assert any(t.endswith(f"≡ {pow(base, n, modulus)}   (mod {modulus})") for t in texts)

    def test_a_modulus_without_a_base_is_refused(self):
        assert refusal_findings("bit_selection", {"n": 117, "modulus": 19})
        assert _svg("bit_selection", n=117, modulus=19) == ""

    def test_too_many_bits_is_refused(self):
        assert refusal_findings("bit_selection", {"n": 4096})


class TestResidueTiles:
    @pytest.mark.parametrize("p,a", [(7, 3), (13, 7), (17, 10), (5, 12)])
    def test_the_second_row_is_a_times_k_and_a_permutation(self, p, a):
        svg = _svg("residue_tiles", p=p, a=a)
        numbers = [int(t) for t in _texts(svg) if t.isdigit()]
        top, middle, bottom = (numbers[i * (p - 1):(i + 1) * (p - 1)] for i in range(3))
        assert top == list(range(1, p))
        assert middle == [a * k % p for k in range(1, p)]
        assert sorted(middle) == bottom == top
        assert svg.count('class="rt-link"') == p - 1

    @pytest.mark.parametrize("params", [{"p": 9, "a": 2}, {"p": 7, "a": 14}, {"p": 19, "a": 2},
                                        {"p": 1, "a": 1}])
    def test_no_false_permutation_is_drawn(self, params):
        """Composite p, p | a, or past the legible width: blank, with the reason."""
        assert refusal_findings("residue_tiles", params)
        assert _svg("residue_tiles", **params) == ""


class TestCoprimeGrid:
    def test_phi_100_is_counted_not_supplied(self):
        svg = _svg("coprime_grid", n=100)
        texts = _texts(svg)
        assert "φ(100) = 100 − 50 − 10 = 40" in texts
        assert "even numbers: 50" in texts and "multiples of 5, not of 2: 10" in texts
        assert svg.count('class="cg-keep"') == sum(1 for k in range(1, 101) if gcd(k, 100) == 1) == 40

    @pytest.mark.parametrize("n", [2, 12, 30, 97, 210])
    def test_the_count_is_phi_for_any_n(self, n):
        svg = _svg("coprime_grid", n=n)
        phi = sum(1 for k in range(1, n + 1) if gcd(k, n) == 1)
        assert svg.count('class="cg-keep"') == phi
        assert any(t.startswith(f"φ({n}) = ") and t.endswith(f"= {phi}") for t in _texts(svg))

    def test_a_result_param_is_not_read(self):
        """There is no way to tell the figure what φ is."""
        assert _svg("coprime_grid", n=100, phi=41) == _svg("coprime_grid", n=100)

    def test_out_of_range_is_refused(self):
        assert refusal_findings("coprime_grid", {"n": 1})
        assert refusal_findings("coprime_grid", {"n": 401})


class TestStagedReveal:
    @pytest.mark.parametrize("kind", TEMPLATES)
    def test_no_reveal_means_no_stage_markup(self, kind):
        assert "data-stage" not in _svg(kind, **LECTURE[kind])

    @pytest.mark.parametrize("kind", TEMPLATES)
    def test_reveal_groups_each_step_with_its_stage(self, kind):
        steps = natural_steps(kind, LECTURE[kind])
        assert steps
        reveal = [i + 1 for i in range(len(steps))]
        svg = _svg(kind, **LECTURE[kind], reveal=reveal)
        found = re.findall(r'data-stage="(\d+)" data-step="([a-z_0-9]+)"', svg)
        assert [s for _stage, s in found] == steps
        assert [int(stage) for stage, _s in found] == reveal

    @pytest.mark.parametrize("kind", TEMPLATES)
    def test_staging_never_changes_what_is_drawn(self, kind):
        """A consumer that ignores the attribute must see the same final figure."""
        steps = natural_steps(kind, LECTURE[kind])
        plain = _svg(kind, **LECTURE[kind])
        staged = _svg(kind, **LECTURE[kind], reveal=[1] * len(steps))
        assert count_data_marks(plain) == count_data_marks(staged)
        assert _texts(plain) == _texts(staged)

    def test_grouping_rungs_onto_fewer_beats(self):
        svg = _svg("squaring_ladder", **LECTURE["squaring_ladder"], reveal=[1, 1, 2, 2, 3, 3, 4, 4])
        stages = [int(s) for s in re.findall(r'data-stage="(\d+)"', svg)]
        assert stages == [1, 1, 2, 2, 3, 3, 4, 4]

    @pytest.mark.parametrize("reveal", [[1, 2], "1,2,3", [1, 2, 3.5], [0, 1, 2], [2, 1, 3],
                                        [1, True, 2]])
    def test_a_bad_plan_is_refused(self, reveal):
        params = {**LECTURE["coprime_grid"], "reveal": reveal}
        findings = refusal_findings("coprime_grid", params)
        assert findings and findings[0].check == "stage_input"
        assert _svg("coprime_grid", **params) == ""

    def test_upto_draws_a_still_part_way_through(self):
        early = _texts(_svg("coprime_grid", n=100, upto=1))
        assert "even numbers: 50" in early and "multiples of 5, not of 2: 10" not in early
        assert "data-stage" not in _svg("coprime_grid", n=100, upto=1)
        full = _texts(_svg("coprime_grid", n=100, upto=3))
        assert full == _texts(_svg("coprime_grid", n=100))

    def test_upto_with_a_reveal_plan_uses_its_stages(self):
        steps = natural_steps("residue_tiles", LECTURE["residue_tiles"])
        plan = [1] * (len(steps) - 2) + [2, 3]
        still = _svg("residue_tiles", p=7, a=3, reveal=plan, upto=1)
        assert 'class="rt-link"' not in still and still.count('class="rt-tile-shuffled"') == 6

    def test_an_empty_plan_is_the_static_figure(self):
        assert _svg("coprime_grid", n=100, reveal=[]) == _svg("coprime_grid", n=100)

    def test_upto_must_be_a_count(self):
        assert refusal_findings("coprime_grid", {"n": 100, "upto": -1})

    def test_a_template_without_stages_reports_none(self):
        assert natural_steps("array_state", {"values": [1, 2]}) == []
        assert natural_steps("no_such_template", {}) == []


class TestTheyReadOnALectureSlide:
    @pytest.mark.parametrize("kind", TEMPLATES)
    @pytest.mark.parametrize("theme", ["professional", "dark", "high-contrast", "print-friendly"])
    def test_full_width_text_stays_above_the_floor(self, kind, theme):
        svg = _svg(kind, **LECTURE[kind], theme=theme)
        assert svg and DIAGRAM_REGISTRY[kind].themes
        errors = [f for f in check_figure(svg, display_width=1180) if f.severity == "error"]
        assert not errors, errors

    @pytest.mark.parametrize("kind", TEMPLATES)
    def test_deterministic(self, kind):
        assert _svg(kind, **LECTURE[kind]) == _svg(kind, **LECTURE[kind])
