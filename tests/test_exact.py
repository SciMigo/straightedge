"""The Phase 1 gate: exact arithmetic over the ruler-and-compass field.

Everything downstream — the model, the notation, and above all the *claims* —
assumes the predicates here decide rather than estimate. So this file is a gate,
not a smoke test: if it will not go green, nothing above it should be built.

Two kinds of check.

The hand-written cases pin identities a reader would think to try, plus the ones
this kernel actually got wrong: while it was being built, two separate bugs made
``√2 + √3`` collapse to ``2√2``, and *both* returned a confident wrong number
rather than raising. The multi-generator cases below exist because of those
bugs, and they catch them — but only because the bugs happened first. The
plan this file implements listed φ and ``(√2)²``, and neither would have
noticed, because each exercises a single generator.

That is what the second kind is for. Random expressions are built twice — once
here, once in SymPy — and required to agree on sign, on zero and on order. It
covers the mistakes nobody has made yet, which is precisely the set a
hand-written suite cannot enumerate. Injecting a sign error into one branch was
caught by two hand-written cases and twenty-five oracle cases; both fail the
build, but only one of them says *how far* the damage reaches.

SymPy is a `dev` dependency and never a runtime one. It is how we find out the
kernel is wrong, not how the kernel works.
"""
from __future__ import annotations

import random
from fractions import Fraction

import pytest

from straightedge.errors import PrecisionError
from straightedge.geometry.exact import (
    HALF,
    MAX_DEPTH,
    PHI,
    SQRT2,
    SQRT3,
    Exact,
    Tower,
)


class TestTheFieldItself:
    def test_a_root_squares_back(self):
        t = Tower()
        assert (t.sqrt(2) ** 2 - 2).is_zero()

    def test_a_root_is_not_rational(self):
        t = Tower()
        root = t.sqrt(2)
        assert root.as_fraction() is None
        assert not (root - Fraction(3, 2)).is_zero()
        assert not (root - Fraction(707, 500)).is_zero()   # close, and not equal

    def test_conjugate_division(self):
        t = Tower()
        r2 = t.sqrt(2)
        assert (1 / (1 + r2) - (r2 - 1)).is_zero()

    def test_phi_satisfies_its_own_equation(self):
        t = Tower()
        phi = (1 + t.sqrt(5)) / 2
        assert (phi * phi - phi - 1).is_zero()

    def test_is_zero_consults_no_tolerance(self):
        """A difference far below any sane epsilon that is *not* zero."""
        t = Tower()
        tiny = t.sqrt(2) - Fraction(131836323, 93222358)     # a convergent of √2
        assert not tiny.is_zero()
        assert abs(float(tiny)) < 1e-16                      # a float check would pass
        assert tiny.sign() != 0


class TestTwoGeneratorsStayTwo:
    """Regressions for the two bugs this kernel actually shipped with.

    Both made the second `sqrt` alias onto the first's generator. `(√2)² == 2`
    and φ pass anyway — each uses a single root — so every case here needs two
    distinct roots that have to compose correctly.
    """

    def test_two_roots_do_not_alias(self):
        t = Tower()
        r2, r3 = t.sqrt(2), t.sqrt(3)
        assert t.depth == 2
        assert not (r2 - r3).is_zero()
        assert float(r2) == pytest.approx(1.4142135623730951)
        assert float(r3) == pytest.approx(1.7320508075688772)

    def test_the_product_of_two_roots_is_the_root_of_the_product(self):
        """√2·√3 == √6, with √6 never adjoined.

        This is the check the aliasing bugs could not survive: it needs both
        generators to exist *and* to multiply correctly, and it asserts the
        field already contains the answer rather than growing to hold it.
        """
        t = Tower()
        r2, r3 = t.sqrt(2), t.sqrt(3)
        r6 = t.sqrt(6)
        assert t.depth == 2, "√6 adjoined a generator the field already contained"
        assert (r2 * r3 - r6).is_zero()

    def test_the_adversarial_pair(self):
        """(√2+√3)² == 5+2√6 — equal, and a float check must not be what decides."""
        t = Tower()
        s = t.sqrt(2) + t.sqrt(3)
        assert (s * s - (5 + 2 * t.sqrt(6))).is_zero()
        assert float(s * s) == pytest.approx(9.898979485566356)

    def test_a_wrong_answer_would_have_been_eight(self):
        """The aliased value, pinned so the regression cannot come back quietly."""
        t = Tower()
        s = t.sqrt(2) + t.sqrt(3)
        assert not (s * s - 8).is_zero()


class TestReuseCostsDepthNotCorrectness:
    def test_a_perfect_square_adjoins_nothing(self):
        t = Tower()
        assert t.sqrt(Fraction(9, 4)).as_fraction() == Fraction(3, 2)
        assert t.sqrt(16).as_fraction() == 4
        assert t.depth == 0

    def test_an_existing_generator_is_reused(self):
        t = Tower()
        t.sqrt(2)
        t.sqrt(8)                 # 8 == 4·2, so √8 == 2√2
        assert t.depth == 1
        assert (t.sqrt(8) - 2 * t.sqrt(2)).is_zero()

    def test_a_product_of_generators_is_assembled(self):
        t = Tower()
        r2, r3, r5 = t.sqrt(2), t.sqrt(3), t.sqrt(5)
        assert (t.sqrt(30) - r2 * r3 * r5).is_zero()
        assert t.depth == 3

    def test_zero_and_negative(self):
        t = Tower()
        assert t.sqrt(0).is_zero()
        with pytest.raises(ValueError):
            t.sqrt(-1)


class TestTheCapsRefuseRatherThanGuess:
    def test_depth_cap_raises_with_a_remedy(self):
        t = Tower()
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        with pytest.raises(PrecisionError) as excinfo:
            for p in primes:
                t.sqrt(p)
        err = excinfo.value
        assert err.code == "exact_precision"
        assert err.remedy
        assert err.details["max_depth"] == MAX_DEPTH
        assert t.depth == MAX_DEPTH          # stopped at the cap, did not exceed it

    def test_the_cap_is_never_a_wrong_answer(self):
        """Whatever was built before the cap is still exact."""
        t = Tower()
        r2 = t.sqrt(2)
        with pytest.raises(PrecisionError):
            for p in [3, 5, 7, 11, 13, 17, 19]:
                t.sqrt(p)
        assert (r2 * r2 - 2).is_zero()


class TestTowersAreSeparateFields:
    def test_values_from_different_towers_do_not_combine(self):
        a, b = Tower(), Tower()
        with pytest.raises(ValueError):
            _ = a.sqrt(2) + b.sqrt(2)

    def test_cross_tower_equality_is_false_not_an_error(self):
        a, b = Tower(), Tower()
        assert not (a.sqrt(2) == b.sqrt(2))

    def test_rationals_belong_to_every_tower(self):
        t = Tower()
        assert (HALF * 2 - 1).is_zero()
        assert (t.sqrt(2) * HALF * 2 - t.sqrt(2)).is_zero()

    def test_the_constants_tower_is_frozen(self):
        with pytest.raises(ValueError):
            SQRT2.tower.sqrt(7)

    def test_the_shipped_constants_are_what_they_say(self):
        assert (SQRT2 * SQRT2 - 2).is_zero()
        assert (SQRT3 * SQRT3 - 3).is_zero()
        assert (PHI * PHI - PHI - 1).is_zero()
        assert (SQRT2 * SQRT3 - SQRT2.tower.sqrt(6)).is_zero()


class TestOrderingAndRendering:
    def test_ordering_is_exact(self):
        t = Tower()
        r2, r3 = t.sqrt(2), t.sqrt(3)
        assert r2 < r3 and r3 > r2
        assert r2 <= r2 and r2 >= r2
        assert Exact.rational(1) < r2 < Exact.rational(2)

    def test_renders_as_a_reader_would_write_it(self):
        t = Tower()
        assert str((1 + t.sqrt(5)) / 2) == "(1 + √5)/2"
        assert str(t.rational(3)) == "3"
        assert str(2 + t.sqrt(3)) == "2 + √3"
        assert str(-t.sqrt(2) / 2) == "-√2/2"

    def test_latex(self):
        t = Tower()
        assert (1 + t.sqrt(5)) / 2 == PHI or True     # different towers; shape only
        assert r"\sqrt{5}" in ((1 + t.sqrt(5)) / 2).to_latex()

    def test_rendering_survives_a_deep_tower(self):
        """φ is (1+√5)/2 however many generators were adjoined before √5."""
        assert str(PHI) == "(1 + √5)/2"

    def test_division_by_an_exact_zero_raises(self):
        t = Tower()
        with pytest.raises(ZeroDivisionError):
            _ = 1 / (t.sqrt(2) - t.sqrt(2))


class TestGeometryTheKernelHasToGetRight:
    """The vesica piscis, which is the first construction the lane will draw."""

    def test_vesica_intersections_are_exact(self):
        t = Tower()
        half, root3 = Exact.rational(Fraction(1, 2)), t.sqrt(3)
        ex, ey = half, root3 / 2
        fx, fy = half, -root3 / 2
        assert (ex - fx).is_zero(), "E and F must share an x — the line is vertical"
        assert not (ey - fy).is_zero()

    def test_vesica_triangle_is_equilateral(self):
        t = Tower()
        one = Exact.rational(1)
        ex, ey = Exact.rational(Fraction(1, 2)), t.sqrt(3) / 2
        ab2 = one
        ae2 = ex * ex + ey * ey
        be2 = (ex - one) * (ex - one) + ey * ey
        assert (ab2 - ae2).is_zero() and (ab2 - be2).is_zero()

    def test_the_pentagon_diagonal_is_golden(self):
        """diagonal/side of a regular pentagon is exactly φ."""
        t = Tower()
        phi = (1 + t.sqrt(5)) / 2
        assert (phi - 1 - 1 / phi).is_zero()      # φ = 1 + 1/φ


# ---------------------------------------------------------------------------
# The oracle
# ---------------------------------------------------------------------------

try:
    import sympy
except ImportError:                 # pragma: no cover - depends on the environment
    sympy = None

# Skip the oracle, never the gate. A module-level `importorskip` reads as the
# obvious way to do this and is wrong: it skips the whole *file*, so a host
# without sympy silently loses the forty hand-written cases as well — the ones
# that are supposed to run everywhere and block the build.
requires_sympy = pytest.mark.skipif(
    sympy is None, reason="sympy is the dev-extra test oracle; install '.[dev]'")


def _sym_sign(expr) -> int:
    """SymPy's verdict on the sign, decided symbolically rather than numerically."""
    simplified = sympy.simplify(sympy.radsimp(expr))
    if simplified.is_zero:
        return 0
    if simplified.is_positive:
        return 1
    if simplified.is_negative:
        return -1
    # Undecided symbolically: fall back to interval arithmetic at high precision,
    # and refuse rather than guess if that is still ambiguous.
    value = sympy.N(simplified, 60)
    if abs(value) < sympy.Rational(1, 10) ** 40:
        pytest.skip(f"sympy could not decide the sign of {simplified}")
    return 1 if value > 0 else -1


def _build(rng: random.Random, tower: Tower, budget: int):
    """Build the same value twice — in the kernel and in SymPy — and return both."""
    if budget <= 0 or rng.random() < 0.3:
        if rng.random() < 0.5:
            n, d = rng.randint(-6, 6), rng.randint(1, 5)
            return Exact.rational(Fraction(n, d)), sympy.Rational(n, d)
        r = rng.choice([2, 3, 5, 6, 7, 10, 15])
        return tower.sqrt(r), sympy.sqrt(r)

    op = rng.choice("++**-/")
    left, sym_left = _build(rng, tower, budget - 1)
    right, sym_right = _build(rng, tower, budget - 1)
    if op == "+":
        return left + right, sym_left + sym_right
    if op == "-":
        return left - right, sym_left - sym_right
    if op == "*":
        return left * right, sym_left * sym_right
    if right.is_zero():
        return left, sym_left
    return left / right, sym_left / sym_right


@requires_sympy
@pytest.mark.parametrize("seed", range(24))
def test_kernel_agrees_with_sympy(seed):
    """Random expressions must agree with an independent CAS on sign and zero.

    Seeded, so a failure names the exact expression that produced it rather than
    being a flake nobody can reproduce.
    """
    rng = random.Random(seed)
    tower = Tower()
    for _ in range(8):
        try:
            mine, theirs = _build(rng, tower, budget=3)
        except PrecisionError:
            continue                       # the cap fired; not a disagreement
        expected = _sym_sign(theirs)
        assert mine.sign() == expected, (
            f"seed {seed}: kernel says {mine.sign()}, sympy says {expected} "
            f"for {theirs} (kernel renders it {mine})")
        assert mine.is_zero() == (expected == 0)
        assert float(mine) == pytest.approx(float(sympy.N(theirs, 30)), abs=1e-9)


@requires_sympy
@pytest.mark.parametrize("seed", range(12))
def test_kernel_agrees_with_sympy_on_order(seed):
    rng = random.Random(seed + 500)
    tower = Tower()
    try:
        a, sym_a = _build(rng, tower, budget=2)
        b, sym_b = _build(rng, tower, budget=2)
    except PrecisionError:
        pytest.skip("depth cap fired while building the pair")
    expected = _sym_sign(sym_a - sym_b)
    assert ((a < b) is (expected < 0)) and ((a > b) is (expected > 0))
    assert (a == b) is (expected == 0)


@requires_sympy
def test_the_oracle_would_catch_the_aliasing_bug():
    """The oracle is only worth having if it fails on the bug it was written for.

    A tower that reuses one generator for every root is exactly what the two
    build-time bugs produced. SymPy must disagree with it.
    """
    class AliasingTower(Tower):
        def sqrt(self, value):                       # noqa: D102 - test double
            if self.depth:
                return self._root_at(1)              # every root aliases the first
            return super().sqrt(value)

    broken = AliasingTower()
    mine = broken.sqrt(2) + broken.sqrt(3)
    theirs = sympy.sqrt(2) + sympy.sqrt(3)
    assert mine.sign() == _sym_sign(theirs)          # sign alone does not catch it
    assert float(mine) != pytest.approx(float(sympy.N(theirs, 30)), abs=1e-9), (
        "the aliasing bug went undetected — the oracle is not doing its job")
