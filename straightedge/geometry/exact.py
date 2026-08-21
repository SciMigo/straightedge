"""Exact arithmetic over the numbers ruler and compass can reach.

A construction is only worth checking if the check is a *proof*. Measuring a
drawing with floats and calling a difference below 1e-9 "equal" is the failure
this project keeps refusing elsewhere: an answer that is plausible and
unfounded. So the coordinates here are exact, and ``is_zero`` decides rather
than estimates.

The field is not arbitrary. Ruler and compass reach exactly the tower of
quadratic extensions of the rationals --- a straightedge gives linear equations,
a compass gives quadratic ones, and nothing either tool can do escapes
``Q(√r₁)(√r₂)…(√rₙ)``. That is the classical theorem, and it is why the cube
cannot be doubled: a cube root has degree 3, and every element here has degree a
power of 2. Implementing that tower is therefore not an approximation of the
geometry; it is the geometry's own arithmetic.

An element at level *k* is ``a + b·√gₖ`` where ``a`` and ``b`` are elements at
level *k-1* and ``gₖ`` --- the generator --- is itself a level *k-1* element.
Level 0 is :class:`fractions.Fraction`. Addition and multiplication are
componentwise; division goes through the conjugate; and **sign is decidable**,
which is the whole reason for the exercise::

    sign(a + b√g), with g > 0 and therefore √g > 0:
        a, b both ≥ 0   →  positive (or zero if both are)
        a, b both ≤ 0   →  negative (or zero if both are)
        opposite signs  →  compare a² against b²g, recursively

No tolerance appears anywhere in that path. ``is_zero`` is a proof.

Stdlib only, and imports nothing else from this package: the figure lane
declares no runtime dependencies, and this is the lane it belongs to.

    >>> t = Tower()
    >>> phi = (Exact.rational(1) + t.sqrt(5)) / 2
    >>> (phi * phi - phi - 1).is_zero()
    True
    >>> str(phi)
    '(1 + √5)/2'

Two towers are separate fields. Values from one cannot be combined with values
from another --- there is no meaningful ``√2`` shared between constructions that
each adjoined their own --- and attempting it raises :class:`ValueError`. Plain
rationals are the exception: they belong to every tower, so they carry none.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Iterator, Union

from ..errors import PrecisionError

__all__ = [
    "Tower",
    "Exact",
    "MAX_DEPTH",
    "MAX_BITS",
    "PHI",
    "SQRT2",
    "SQRT3",
    "SQRT5",
    "HALF",
]

#: Levels of extension a single construction may reach. Each level doubles the
#: rationals a coordinate costs (a level-6 value is 64 of them), so this is a
#: cost ceiling rather than a mathematical one. Classroom constructions --- the
#: vesica, the perpendicular bisector, the pentagon --- are depth 1 to 3.
MAX_DEPTH = 6

#: Bit ceiling on any single numerator or denominator. Depth alone does not
#: bound cost: repeated division grows integers without adjoining anything, and
#: a construction of large rational coordinates never leaves level 0 at all — so
#: the check applies to plain rationals as much as to tower values. It did not
#: at first, which left the commonest growth path the only unguarded one.
MAX_BITS = 4096

#: How far :func:`_squarefree_part` trial-divides before giving up. Square
#: factors of a radicand are found for cost, never for correctness, so a bound
#: here trades a possible extra generator for a guaranteed finish. Covers every
#: square factor a classroom construction produces; a 32-bit prime is the point
#: past which the search is no longer worth its own runtime.
TRIAL_DIVISION_LIMIT = 100_000

Rationalish = Union[int, Fraction, "Exact"]


def _as_fraction(value: object) -> Fraction | None:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    return None


def _isqrt_exact(n: int) -> int | None:
    """Integer square root of ``n``, or ``None`` when ``n`` is not a square."""
    if n < 0:
        return None
    r = math.isqrt(n)
    return r if r * r == n else None


def _squarefree_part(value: Fraction) -> tuple[Fraction, Fraction]:
    """Split ``value`` as ``(c, m)`` with ``value == c² · m`` and ``m`` squarefree.

    Works on the integer ``numerator · denominator``, because
    ``p/q == (p·q)/q²`` --- so the rational's squarefree part is the integer's,
    and the square factor carries the denominator.
    """
    if value == 0:
        return Fraction(0), Fraction(1)
    n = value.numerator * value.denominator
    sign = 1 if n > 0 else -1
    n = abs(n)
    square, rest = 1, n
    d = 2
    # Bounded. Trial division to √n is unbounded work on an integer this class
    # will happily carry to MAX_BITS: a 50-bit prime already takes four seconds,
    # and a construction with a large coordinate reaches this through a circle
    # intersection — so an ordinary request could pin the process indefinitely.
    #
    # Giving up early costs nothing but tidiness. An unreduced radicand is still
    # a positive radicand, so `√n` is adjoined whole rather than as `c√m`: the
    # tower gains a generator it might have shared, which spends depth and
    # leaves every answer exactly as correct.
    while d * d <= rest and d <= TRIAL_DIVISION_LIMIT:
        while rest % (d * d) == 0:
            rest //= d * d
            square *= d
        d += 1 if d == 2 else 2
    return Fraction(square, value.denominator), Fraction(sign * rest)


class Tower:
    """The generators one construction's coordinates are built over.

    One tower per construction, shared by every value in it. A generator is
    added once and earlier values embed into the taller tower with zero
    coefficients, so nothing has to be rewritten when the field grows.
    """

    __slots__ = ("_gens", "_frozen")

    def __init__(self, frozen: bool = False) -> None:
        self._gens: list[Exact] = []
        self._frozen = frozen

    @property
    def depth(self) -> int:
        """Number of generators adjoined so far."""
        return len(self._gens)

    def generator(self, level: int) -> "Exact":
        """``g`` for the extension at ``level`` (1-based), as a level-1 element."""
        return self._gens[level - 1]

    def rational(self, value: Rationalish) -> "Exact":
        """A rational in this tower. Rationals carry no tower of their own."""
        return Exact.rational(value)

    def sqrt(self, value: Rationalish) -> "Exact":
        """``√value``, reusing the field where it already contains the root.

        Reuse matters for cost, not correctness: adjoining ``√6`` to a tower that
        already holds ``√2`` and ``√3`` gives a field no larger but a level
        deeper, and depth is what the cap is spent on. Three cases are caught,
        in order of cheapness --- a perfect rational square needs no generator at
        all, an existing generator is reused outright, and a product of existing
        rational generators is assembled from the roots already present.

        Anything else adjoins. That is a cost decision and never a correctness
        one: ``sign`` compares real numbers by recursion and does not require the
        tower to be a genuine degree-2ⁿ extension, so a redundant generator
        spends depth and leaves every answer intact.
        """
        val = value if isinstance(value, Exact) else Exact.rational(value)
        if val.sign() < 0:
            raise ValueError(f"√ of a negative value: {val}")
        if val.is_zero():
            return Exact.rational(0)

        rational = val.as_fraction()
        if rational is not None:
            square, free = _squarefree_part(rational)
            if free == 1:
                return Exact.rational(square)
            root = self._root_of_squarefree(free)
            if root is not None:
                return root * Exact.rational(square)
            return self._adjoin(Exact.rational(free)) * Exact.rational(square)

        for level in range(1, self.depth + 1):
            if (self._gens[level - 1] - val).is_zero():
                return self._root_at(level)
        return self._adjoin(val)

    # -- internals -------------------------------------------------------
    def _rational_generators(self) -> list[tuple[int, Fraction]]:
        out = []
        for i, gen in enumerate(self._gens, start=1):
            frac = gen.as_fraction()
            if frac is not None:
                out.append((i, frac))
        return out

    def _root_of_squarefree(self, free: Fraction) -> "Exact | None":
        """``√free`` assembled from generators already in the tower, or ``None``.

        ``√6`` over a tower holding ``√2`` and ``√3`` is ``√2·√3``. In general a
        subset of the rational generators whose product has the same squarefree
        part will do: their product is ``free · t²``, so the product of their
        roots is ``t·√free`` and dividing by ``t`` recovers the root.
        """
        gens = self._rational_generators()
        for level, gen in gens:
            if gen == free:
                return self._root_at(level)
        # No separate ceiling is needed: MAX_DEPTH bounds the generator count, so
        # this enumerates at most 2**MAX_DEPTH subsets — 64 at the shipped cap,
        # measured at well under a millisecond. A second limit here would be a
        # constant that drifts away from the one actually doing the work.
        if len(gens) < 2:
            return None
        for mask in range(3, 1 << len(gens)):
            if mask & (mask - 1) == 0:    # singletons already handled above
                continue
            product = Fraction(1)
            chosen = []
            for bit, (level, gen) in enumerate(gens):
                if mask >> bit & 1:
                    product *= gen
                    chosen.append(level)
            square, part = _squarefree_part(product)
            if part != free:
                continue
            root = Exact.rational(1)
            for level in chosen:
                root = root * self._root_at(level)
            return root / Exact.rational(square)
        return None

    def _root_at(self, level: int) -> "Exact":
        """``√gₗ`` as a level-``l`` element: ``0 + 1·√gₗ``."""
        return Exact(self, level, Exact._zero_at(self, level - 1),
                     Exact._one_at(self, level - 1))

    def _adjoin(self, generator: "Exact") -> "Exact":
        if self._frozen:
            raise ValueError(
                "this tower is frozen; build a Tower() of your own to adjoin roots")
        if self.depth + 1 > MAX_DEPTH:
            raise PrecisionError(
                f"construction needs more than {MAX_DEPTH} levels of extension",
                remedy=("Reuse roots already in the construction, or split it into "
                        "separate constructions; raise exact.MAX_DEPTH only if you "
                        "have measured the cost."),
                details={"depth": self.depth + 1, "max_depth": MAX_DEPTH},
            )
        self._gens.append(generator)
        return self._root_at(self.depth)


class Exact:
    """A number reachable by ruler and compass, held exactly.

    Immutable. Arithmetic accepts ``int`` and :class:`~fractions.Fraction` on
    either side; comparison and :meth:`is_zero` are exact.
    """

    __slots__ = ("_tower", "_level", "_a", "_b")

    def __init__(self, tower: Tower | None, level: int,
                 a: "Exact | Fraction", b: "Exact | None" = None) -> None:
        self._tower = tower
        self._level = level
        self._a = a
        self._b = b

    # -- construction ----------------------------------------------------
    @classmethod
    def rational(cls, value: Rationalish) -> "Exact":
        if isinstance(value, Exact):
            return value
        frac = _as_fraction(value)
        if frac is None:
            raise TypeError(f"not a rational: {value!r}")
        return cls(None, 0, frac)

    @classmethod
    def _zero_at(cls, tower: Tower, level: int) -> "Exact":
        if level == 0:
            return cls(None, 0, Fraction(0))
        z = cls._zero_at(tower, level - 1)
        return cls(tower, level, z, z)

    @classmethod
    def _one_at(cls, tower: Tower, level: int) -> "Exact":
        if level == 0:
            return cls(None, 0, Fraction(1))
        return cls(tower, level, cls._one_at(tower, level - 1),
                   cls._zero_at(tower, level - 1))

    # -- shape -----------------------------------------------------------
    @property
    def level(self) -> int:
        return self._level

    @property
    def tower(self) -> Tower | None:
        return self._tower

    def as_fraction(self) -> Fraction | None:
        """The value as a rational, or ``None`` when it needs a root.

        A level-*k* element whose upper coefficients are all zero *is* rational;
        this reports that rather than only recognising level 0.
        """
        if self._level == 0:
            assert isinstance(self._a, Fraction)
            return self._a
        if not self._b.is_zero():           # type: ignore[union-attr]
            return None
        return self._a.as_fraction()        # type: ignore[union-attr]

    def _rationals(self) -> Iterator[Fraction]:
        if self._level == 0:
            yield self._a                   # type: ignore[misc]
        else:
            yield from self._a._rationals()  # type: ignore[union-attr]
            yield from self._b._rationals()  # type: ignore[union-attr]

    def _check_bits(self) -> "Exact":
        for frac in self._rationals():
            if (frac.numerator.bit_length() > MAX_BITS
                    or frac.denominator.bit_length() > MAX_BITS):
                raise PrecisionError(
                    "an exact coordinate outgrew the integer size this lane carries",
                    remedy=("Simplify the construction, or raise exact.MAX_BITS if "
                            "you have measured the cost of doing so."),
                    details={"bits": max(frac.numerator.bit_length(),
                                         frac.denominator.bit_length()),
                             "max_bits": MAX_BITS},
                )
        return self

    # -- tower plumbing --------------------------------------------------
    def _common(self, other: "Exact") -> tuple[Tower | None, "Exact", "Exact"]:
        tower = self._tower or other._tower
        if (self._tower is not None and other._tower is not None
                and self._tower is not other._tower):
            raise ValueError(
                "these values are from different towers, which are different "
                "fields; a construction shares one Tower")
        level = max(self._level, other._level)
        return tower, self._embed(tower, level), other._embed(tower, level)

    def _embed(self, tower: Tower | None, level: int) -> "Exact":
        value = self
        while value._level < level:
            zero = Exact._zero_at(tower, value._level)   # type: ignore[arg-type]
            value = Exact(tower, value._level + 1, value, zero)
        return value

    def _coerce(self, other: object) -> "Exact | None":
        if isinstance(other, Exact):
            return other
        frac = _as_fraction(other)
        return None if frac is None else Exact.rational(frac)

    # -- arithmetic ------------------------------------------------------
    def __add__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        if rhs is None:
            return NotImplemented
        tower, x, y = self._common(rhs)
        if x._level == 0:
            return Exact.rational(x._a + y._a)._check_bits()   # type: ignore[operator]
        return Exact(tower, x._level, x._a + y._a, x._b + y._b)._check_bits()

    __radd__ = __add__

    def __neg__(self) -> "Exact":
        if self._level == 0:
            return Exact.rational(-self._a)              # type: ignore[operator]
        return Exact(self._tower, self._level, -self._a, -self._b)

    def __sub__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else self + (-rhs)

    def __rsub__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else rhs + (-self)

    def __mul__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        if rhs is None:
            return NotImplemented
        tower, x, y = self._common(rhs)
        if x._level == 0:
            return Exact.rational(x._a * y._a)._check_bits()   # type: ignore[operator]
        gen = tower.generator(x._level)._embed(tower, x._level - 1)  # type: ignore[union-attr]
        # (a + b√g)(c + d√g) = (ac + bdg) + (ad + bc)√g
        return Exact(tower, x._level,
                     x._a * y._a + x._b * y._b * gen,
                     x._a * y._b + x._b * y._a)._check_bits()

    __rmul__ = __mul__

    def inverse(self) -> "Exact":
        """``1/self``, by rationalising with the conjugate."""
        if self.is_zero():
            raise ZeroDivisionError("inverse of an exact zero")
        if self._level == 0:
            return Exact.rational(1 / self._a)._check_bits()   # type: ignore[operator]
        tower = self._tower
        gen = tower.generator(self._level)._embed(tower, self._level - 1)  # type: ignore[union-attr]
        # 1/(a + b√g) = (a − b√g) / (a² − b²g)
        norm = (self._a * self._a - self._b * self._b * gen).inverse()
        return Exact(tower, self._level, self._a * norm,
                     (-self._b) * norm)._check_bits()

    def __truediv__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else self * rhs.inverse()

    def __rtruediv__(self, other: object) -> "Exact":
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else rhs * self.inverse()

    def __pow__(self, exponent: int) -> "Exact":
        if not isinstance(exponent, int):
            return NotImplemented
        if exponent < 0:
            return self.inverse() ** (-exponent)
        result = Exact.rational(1)
        base = self
        while exponent:
            if exponent & 1:
                result = result * base
            base = base * base
            exponent >>= 1
        return result

    # -- decision --------------------------------------------------------
    def sign(self) -> int:
        """``-1``, ``0`` or ``1``. Exact --- no tolerance is consulted."""
        if self._level == 0:
            frac = self._a
            return (frac > 0) - (frac < 0)                # type: ignore[operator]
        a, b = self._a, self._b
        sa, sb = a.sign(), b.sign()                       # type: ignore[union-attr]
        if sa >= 0 and sb >= 0:
            return 1 if (sa or sb) else 0
        if sa <= 0 and sb <= 0:
            return -1 if (sa or sb) else 0
        # Opposite signs: the comparison is a² against b²g, and √g > 0 decides
        # which way the answer points.
        tower = self._tower
        gen = tower.generator(self._level)._embed(tower, self._level - 1)  # type: ignore[union-attr]
        diff = (a * a - b * b * gen).sign()               # type: ignore[operator]
        return diff if sa > 0 else -diff

    def is_zero(self) -> bool:
        return self.sign() == 0

    def __eq__(self, other: object) -> bool:
        rhs = self._coerce(other)
        if rhs is None:
            return NotImplemented
        try:
            return (self - rhs).is_zero()
        except ValueError:                  # different towers: not equal, not an error
            return False

    def __lt__(self, other: object) -> bool:
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else (self - rhs).sign() < 0

    def __le__(self, other: object) -> bool:
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else (self - rhs).sign() <= 0

    def __gt__(self, other: object) -> bool:
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else (self - rhs).sign() > 0

    def __ge__(self, other: object) -> bool:
        rhs = self._coerce(other)
        return NotImplemented if rhs is None else (self - rhs).sign() >= 0

    #: Deliberately unhashable. Equality here is exact and holds across `int`,
    #: `Fraction` and `Exact` alike, and no cheap hash agrees with all three:
    #: the rounded-float bucket this used to return made
    #: `Exact.rational(Fraction(1, 3)) == Fraction(1, 3)` true while their hashes
    #: differed, so a dict keyed on one could not be read with the other. Two
    #: structurally different representations of the same irrational have the
    #: same problem at any rounding boundary.
    #:
    #: A wrong hash does not raise — it silently loses set membership and dict
    #: lookups, which is a worse failure than not being hashable at all. Nothing
    #: in this package hashes these; use the exact comparisons.
    __hash__ = None       # type: ignore[assignment]

    def __float__(self) -> float:
        if self._level == 0:
            return float(self._a)                         # type: ignore[arg-type]
        tower = self._tower
        gen = tower.generator(self._level)._embed(tower, self._level - 1)  # type: ignore[union-attr]
        return float(self._a) + float(self._b) * math.sqrt(max(float(gen), 0.0))

    def sqrt(self) -> "Exact":
        """``√self`` within this value's own tower."""
        if self._tower is None:
            raise ValueError(
                "a bare rational has no tower to adjoin into; call Tower.sqrt()")
        return self._tower.sqrt(self)

    # -- rendering -------------------------------------------------------
    def _parts(self) -> tuple[Fraction, Fraction, Fraction] | None:
        """``(a, b, g)`` as rationals when the value is ``a + b√g``, else ``None``.

        Level is not the test --- φ built on a tower that already held √2 and √3
        sits at level 3 and is still plainly ``(1 + √5)/2``. What matters is that
        both coefficients and the generator reduce to rationals, which
        :meth:`as_fraction` decides for a value of any height.
        """
        if self._level == 0 or self._tower is None:
            return None
        a = self._a.as_fraction()                          # type: ignore[union-attr]
        b = self._b.as_fraction()                          # type: ignore[union-attr]
        if a is None or b is None:
            return None
        g = self._tower.generator(self._level).as_fraction()
        return None if g is None else (a, b, g)

    def __str__(self) -> str:
        frac = self.as_fraction()
        if frac is not None:
            return str(frac)
        parts = self._parts()
        if parts is None:
            return f"({self._a} + {self._b}√g{self._level})"
        a, b, g = parts
        den = a.denominator * b.denominator // math.gcd(a.denominator, b.denominator)
        an, bn = a.numerator * (den // a.denominator), b.numerator * (den // b.denominator)
        root = f"√{g}" if bn in (1, -1) else f"{abs(bn)}√{g}"
        if an == 0:
            body = f"{'-' if bn < 0 else ''}{root}"
            return body if den == 1 else f"{body}/{den}"
        body = f"{an} {'-' if bn < 0 else '+'} {root}"
        return body if den == 1 else f"({body})/{den}"

    def to_latex(self) -> str:
        frac = self.as_fraction()
        if frac is not None:
            return (str(frac.numerator) if frac.denominator == 1
                    else rf"\frac{{{frac.numerator}}}{{{frac.denominator}}}")
        parts = self._parts()
        if parts is None:
            return rf"{self._a.to_latex()} + {self._b.to_latex()}\sqrt{{g_{self._level}}}"  # type: ignore[union-attr]
        a, b, g = parts
        den = a.denominator * b.denominator // math.gcd(a.denominator, b.denominator)
        an, bn = a.numerator * (den // a.denominator), b.numerator * (den // b.denominator)
        root = rf"\sqrt{{{g}}}" if bn in (1, -1) else rf"{abs(bn)}\sqrt{{{g}}}"
        body = (f"{'-' if bn < 0 else ''}{root}" if an == 0
                else f"{an} {'-' if bn < 0 else '+'} {root}")
        return body if den == 1 else rf"\frac{{{body}}}{{{den}}}"

    def __repr__(self) -> str:
        return f"Exact({self}, level={self._level})"


#: A frozen tower for the named constants below, so importing them cannot grow a
#: field some construction is relying on. Build a :class:`Tower` for real work.
_CONSTANTS = Tower()
SQRT2 = _CONSTANTS.sqrt(2)
SQRT3 = _CONSTANTS.sqrt(3)
SQRT5 = _CONSTANTS.sqrt(5)
PHI = (Exact.rational(1) + SQRT5) / 2
HALF = Exact.rational(Fraction(1, 2))
_CONSTANTS._frozen = True
