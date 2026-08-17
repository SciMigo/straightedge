"""Named visual roles, so one scene can be drawn in more than one style.

This module exists because the repo already had two visual styles and no way to
say so. :mod:`straightedge.templates` draws in Manim's default palette —
``YELLOW`` on black, the textbook look — across 134 bare colour literals. The
dataflow scenes under ``examples/`` draw in a dark technical palette, and all
three of them define *the same six hex values* independently, under different
names:

===============  ==============  ==============  =============================
``#4aa8ff``      ``ACT``         ``FWD``         ``OWNED``
``#f2b45b``      ``WEIGHT``      ``BWD``         ``MOVING``
``#4CAF50``      ``PSUM``        ``GOOD``        ``DONE``
``#E5533D``      ``HOT``         ``MEM``         ``COST``
``#5a6885``      ``DIM``         ``DIM``         ``DIM``
``#0d1117``      ``INK``         ``INK``         ``INK``
===============  ==============  ==============  =============================

So the shared style was already real. It was just copy-pasted, which means no
caller could ask for a different one, and a fourth example would have been a
fourth copy.

**The tokens name a visual role, not a domain concept.** That is deliberate, and
the table above is the reason: the same amber is a *stationary weight* in the
systolic array, a *backward pass* in the pipeline chart, and a *packet in
flight* in the ring. Those three have nothing in common except their job on
screen — be the counterpart to the blue. A token called ``weight`` would have
been wrong in two scenes out of three, so the token is called :attr:`hold` and
each scene aliases it to whatever it means locally:

.. code-block:: python

    from straightedge.style import DATAFLOW as S

    WEIGHT = S.hold          # amber: stationary, in this scene
    Text("B", font_size=S.size.heading, color=WEIGHT, weight="BOLD")

**No Manim import.** :mod:`straightedge` is importable without the ``render``
extra (see the package docstring), and a palette is data. Colours are hex
strings, which Manim accepts anywhere it accepts a colour; where a value is one
of Manim's own constants the comment names it, so the equivalence is checkable
by eye and is asserted in ``tests/test_style.py``.

Themes ship as module constants rather than as a config file, because a theme is
part of the library's tested surface: :data:`TEXTBOOK` is pinned to the values
``templates.py`` already draws with, and a test fails if it drifts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import RequestError

__all__ = [
    "Style", "Sizes", "Widths", "Opacities",
    "DATAFLOW", "TEXTBOOK", "PAPER",
    "THEMES", "THEME_NAMES", "theme",
]


class _Replaceable:
    """A frozen token group you can copy with changes.

    Present on the groups as well as on :class:`Style` so a scene can nudge one
    step without inventing a theme::

        S = DATAFLOW.variant(size=DATAFLOW.size.variant(title=36))
    """

    def variant(self, **overrides):
        """A copy of this group with some tokens replaced."""
        return replace(self, **overrides)


@dataclass(frozen=True)
class Sizes(_Replaceable):
    """Type scale, in Manim ``font_size`` points.

    Seven steps, chosen to cover what the existing scenes actually asked for
    rather than to be a tidy geometric run — a scale that does not contain the
    sizes in use is a scale nobody adopts. A scene that deliberately wants a
    size off the scale still passes a number; these are defaults, not a wall.
    """

    title: int = 34       #: scene title
    display: int = 26     #: a running readout meant to be read at a glance
    heading: int = 22     #: what a block of the picture is
    subtitle: int = 21    #: the qualifying line under a title
    body: int = 19        #: a sentence the viewer is expected to read
    label: int = 17       #: a legend entry, an axis caption
    small: int = 15       #: a row tag, a rank name
    tiny: int = 13        #: a value inside a cell


@dataclass(frozen=True)
class Widths(_Replaceable):
    """Stroke widths, in Manim units."""

    hairline: float = 0.8   #: grid lines that must not compete with their fill
    rule: float = 1.2       #: the edge of an inert container
    mark: float = 2.0       #: the edge of something that carries meaning
    accent: float = 2.5     #: a swatch or a cell the eye is sent to
    chip: float = 3.0       #: a moving datum, which needs to survive motion blur


@dataclass(frozen=True)
class Opacities(_Replaceable):
    """Fill opacities.

    A light theme cannot reuse a dark theme's fills — 0.25 of an accent over
    ``#0d1117`` reads as a tint, and over ``#fbfaf7`` it reads as nothing. So
    these are per-theme rather than constants.
    """

    tint: float = 0.25    #: a hint of colour, still clearly empty
    panel: float = 0.55   #: an inert surface that should read as a surface
    solid: float = 0.85   #: occupied, and meant to dominate its cell


@dataclass(frozen=True)
class Style(_Replaceable):
    """A complete visual style: colours by role, plus scale.

    Every colour is a hex string. Construct variants with :meth:`variant`
    rather than mutating — a theme handed to two scenes must not be editable by
    one of them.
    """

    name: str

    # -- surfaces ----------------------------------------------------------
    ink: str          #: the background the whole scene sits on
    well: str         #: fill of an empty container — a slot, an unfilled cell
    inert: str        #: fill of a slot that is occupied but idle (a bubble)
    rule: str         #: stroke of inert structure — grid lines, frames

    # -- text --------------------------------------------------------------
    fg: str           #: primary text
    muted: str        #: a value or legend caption, quieter than :attr:`fg`
    dim: str          #: a subtitle or a spent entry — present, de-emphasised
    on_fill: str      #: text drawn *on top of* a filled accent

    # -- data roles --------------------------------------------------------
    flow: str         #: the primary thing in motion
    hold: str         #: its counterpart — stationary, or the other phase
    deep: str         #: a darker :attr:`flow`, for partial progress
    done: str         #: complete, verified, correct
    warn: str         #: the cost, the naive baseline, the hot spot
    aux: str          #: a tracked measurement — an angle being varied, a moving
                      #: pair of dots. Reads as related to :attr:`done` without
                      #: claiming to be the result.
    warm: str         #: a second warm accent, for the counterpart of
                      #: :attr:`hold` when two related quantities have to be
                      #: told apart from each other *and* from everything else
                      #: (the two focal radii of an ellipse, which sum to a
                      #: constant and so must not read as the same line).

    size: Sizes = Sizes()
    width: Widths = Widths()
    opacity: Opacities = Opacities()

    def variant(self, **overrides) -> "Style":
        """A copy with some tokens replaced.

        For a scene that needs one thing changed without inventing a theme::

            S = DATAFLOW.variant(name="dataflow-hot", flow=DATAFLOW.warn)
        """
        return replace(self, **overrides)

    @property
    def accents(self) -> tuple[str, ...]:
        """The data-role colours, in the order a legend should list them."""
        return (self.flow, self.hold, self.done, self.warn)


#: The dark technical style the dataflow examples were already drawing in. The
#: hex values are the ones those three scenes defined by hand, unchanged — the
#: point of this theme is that porting them alters no pixel.
DATAFLOW = Style(
    name="dataflow",
    ink="#0d1117",
    well="#000000",       # Manim BLACK
    inert="#1c2534",
    rule="#444444",       # Manim GREY_D
    fg="#FFFFFF",         # Manim WHITE
    muted="#BBBBBB",      # Manim GREY_B
    dim="#5a6885",
    on_fill="#000000",    # Manim BLACK
    flow="#4aa8ff",
    hold="#f2b45b",
    deep="#2c5c86",
    done="#4CAF50",
    warn="#E5533D",
    aux="#7fd18b",        # a lighter `done`: tracked, not finished
    warm="#e2833c",       # between `hold` and `warn`
)

#: Manim's default palette, which is what :mod:`straightedge.templates` draws
#: with today. Pinned here so the generated scenes can move onto this module
#: without changing their look, and so a drift in either direction is a test
#: failure rather than a surprise in a render.
TEXTBOOK = Style(
    name="textbook",
    ink="#000000",        # Manim BLACK — Manim's own default background
    well="#000000",       # Manim BLACK
    inert="#1a1a1a",
    rule="#444444",       # Manim GREY_D
    fg="#FFFFFF",         # Manim WHITE
    muted="#BBBBBB",      # Manim GREY_B
    dim="#888888",        # Manim GREY
    on_fill="#000000",    # Manim BLACK
    flow="#58C4DD",       # Manim BLUE
    hold="#F7D96F",       # Manim YELLOW
    deep="#2E6E80",
    done="#83C167",       # Manim GREEN
    warn="#FC6255",       # Manim RED
    aux="#A6CF8C",        # Manim GREEN_B
    warm="#FF862F",       # Manim ORANGE
)

#: A light style, for print, slides, and anything read on paper. This is the
#: theme that makes the module worth having rather than merely tidy: it is the
#: one a scene cannot be recoloured into by swapping four constants, because the
#: fills have to change with the background.
PAPER = Style(
    name="paper",
    ink="#fbfaf7",
    well="#ffffff",
    inert="#e8ebf0",
    rule="#c8ccd4",
    fg="#14181f",
    muted="#4a5262",
    dim="#6b7488",
    on_fill="#14181f",
    flow="#1f6feb",
    hold="#b06f00",
    deep="#8fb8e8",
    done="#1a7f37",
    warn="#c0392b",
    aux="#4f9d69",
    warm="#c2621a",
    # Ink on white is already high contrast; dark-theme fills applied to a light
    # ground either vanish or turn the cell into a block. Both ends move.
    opacity=Opacities(tint=0.16, panel=0.30, solid=0.72),
)

#: Every theme by name. The keys are the stable surface — a caller (a CLI flag,
#: an agent's plan field) names a theme by string and gets a :class:`Style`.
THEMES: dict[str, Style] = {s.name: s for s in (DATAFLOW, TEXTBOOK, PAPER)}

#: Theme names, sorted, for a ``--style`` help string or a schema enum.
THEME_NAMES: tuple[str, ...] = tuple(sorted(THEMES))


def theme(name: str) -> Style:
    """Look up a theme by name.

    Raises :class:`~straightedge.errors.RequestError` naming the available
    themes, because the caller that got this wrong is usually a caller that
    cannot see a ``--help``.
    """
    try:
        return THEMES[name]
    except KeyError:
        raise RequestError(
            f"unknown style {name!r}",
            remedy=f"use one of: {', '.join(THEME_NAMES)}",
            details={"requested": name, "available": list(THEME_NAMES)},
        ) from None
