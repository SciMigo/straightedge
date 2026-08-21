"""A notation for constructions, in the shape the operations already have.

A construction is two moves and some given points, and the notation says exactly
that and nothing else::

    A = 0, 0        a given point, named
    * 1, 0          a given point, named for you
    [ A B ]         the line through A and B
    ( A B )         the circle on A through B
    < A B C >       a polygon on those points
    / A B C /       a section: three collinear points
    ( A B ) -> C D  name the points it produces, upper first
    ( A B ) guide   drawn, but excluded from intersection
    # anything      a comment

The brackets are the drawing. ``[ ]`` is a straightedge laid across two points,
``( )`` is a compass with its point on the first and its pencil on the second —
so a reader who has never seen the notation can still tell which tool made which
line, which is more than `circle(A, B)` manages.

Parsing is strict in the way :mod:`straightedge.expr` is strict: one branch per
form, an allowlist, no ``eval``, and anything unrecognised **rejected with its
line number** rather than repaired into something that draws. A construction
quietly missing the step you mistyped is worse than one that refuses to run,
because it still produces a picture.

    >>> steps = parse("A = 0, 0\\nB = 1, 0\\n( A B )\\n( B A )\\n[ C D ]")
    >>> steps[0]
    {'point': ['0', '0'], 'id': 'A'}
    >>> steps[2]
    {'circle': ['A', 'B']}

Coordinates stay strings here and become exact rationals in the model, so
``0.1`` is one tenth rather than the binary float nearest to it. Nothing in this
module does arithmetic; it decides what was written.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

__all__ = ["parse", "parse_line", "NotationError", "FORMS"]


class NotationError(ValueError):
    """A line that is not one of the forms, with where it was."""

    def __init__(self, line_number: int, line: str, reason: str) -> None:
        super().__init__(f"line {line_number}: {reason}\n  {line.strip()}")
        self.line_number = line_number
        self.line = line
        self.reason = reason


#: A name is a label, not an expression: letters and digits, starting with a
#: letter. Deliberately narrow — a name that could contain a bracket would make
#: the forms below ambiguous to read as well as to parse.
_NAME = r"[A-Za-z][A-Za-z0-9_]*"

#: A coordinate as written: an integer, a decimal, or ``p/q``. Kept as text and
#: converted by the model, which is what makes "0.1" exactly one tenth.
_NUMBER = r"[+-]?(?:\d+\.\d*|\.\d+|\d+/\d+|\d+)"

_GUIDE = r"(?:\s+guide)?"
#: ``-> C D`` names the points a step produces, in the order they are found:
#: upper first, then left to right. Without it those points take the next
#: automatic letters, which shift when an earlier step consumes one — so a line
#: written as ``[ C D ]`` can silently join two different points after an edit.
_NAMES = rf"(?:\s*->\s*(?P<names>{_NAME}(?:\s+{_NAME})*))?"

_POINT_NAMED = re.compile(
    rf"^({_NAME})\s*=\s*({_NUMBER})\s*,\s*({_NUMBER}){_GUIDE}$")
_POINT_ANON = re.compile(
    rf"^\*\s*({_NUMBER})\s*,\s*({_NUMBER}){_GUIDE}$")
_LINE = re.compile(rf"^\[\s*({_NAME})\s+({_NAME})\s*\]{_GUIDE}{_NAMES}$")
_CIRCLE = re.compile(rf"^\(\s*({_NAME})\s+({_NAME})\s*\){_GUIDE}{_NAMES}$")
# Three names at minimum: two points bound a segment, not a polygon, and the
# model refuses it downstream — better to say so here, with the line number.
_POLYGON = re.compile(rf"^<\s*({_NAME}(?:\s+{_NAME}){{2,}})\s*>{_GUIDE}$")
_SECTION = re.compile(rf"^/\s*({_NAME})\s+({_NAME})\s+({_NAME})\s*/{_GUIDE}$")

#: Every form, with the line that documents it. The test suite parses each of
#: these, so the documentation cannot describe a syntax the parser does not
#: accept — which is exactly how a published implementation of this idea came to
#: advertise `} A B C {` for a section while implementing `/ A B C /`.
FORMS: tuple[tuple[str, str], ...] = (
    ("A = 0, 0", "a given point, named"),
    ("* 1, 0", "a given point, named for you"),
    ("[ A B ]", "the line through A and B"),
    ("( A B )", "the circle on A through B"),
    ("< A B C >", "a polygon on those points"),
    ("/ A B C /", "a section: three collinear points"),
    ("( A B ) -> C D", "name the points it produces, upper first"),
    ("( A B ) guide", "drawn, but excluded from intersection"),
    ("# anything", "a comment"),
)


def parse_line(line: str, number: int = 1) -> Dict[str, Any] | None:
    """One line to one step, or ``None`` for a comment or a blank.

    Raises :class:`NotationError` on anything else. There is no repair path:
    a mistyped step that parsed as something else would draw a construction
    nobody asked for, and it would look finished.
    """
    text = line.split("#", 1)[0].strip()
    if not text:
        return None
    guide = text.endswith("guide")

    match = _POINT_NAMED.match(text)
    if match:
        return _with_guide({"point": [match.group(2), match.group(3)],
                            "id": match.group(1)}, guide)

    match = _POINT_ANON.match(text)
    if match:
        return _with_guide({"point": [match.group(1), match.group(2)]}, guide)

    match = _LINE.match(text)
    if match:
        return _named(_with_guide(
            {"line": [match.group(1), match.group(2)]}, guide), match)

    match = _CIRCLE.match(text)
    if match:
        return _named(_with_guide(
            {"circle": [match.group(1), match.group(2)]}, guide), match)

    match = _SECTION.match(text)
    if match:
        return {"section": [match.group(1), match.group(2), match.group(3)]}

    match = _POLYGON.match(text)
    if match:
        return {"polygon": match.group(1).split()}

    raise NotationError(number, line, _diagnose(text))


def _with_guide(step: Dict[str, Any], guide: bool) -> Dict[str, Any]:
    if guide:
        step["guide"] = True
    return step


def _named(step: Dict[str, Any], match: "re.Match[str]") -> Dict[str, Any]:
    names = match.groupdict().get("names")
    if names:
        step["names"] = names.split()
    return step


def _diagnose(text: str) -> str:
    """Say what is wrong with the line, not merely that something is.

    A parser that answers every mistake with "invalid syntax" makes the reader
    re-derive the grammar; naming the bracket that did not close, or the form
    that takes a different number of names, is the difference between a message
    and a fix.
    """
    pairs = {"[": "]", "(": ")", "<": ">", "/": "/"}
    head = text[0]
    if head in pairs:
        closer = pairs[head]
        if not text.rstrip().endswith(closer) and " guide" not in text:
            return f"opened with {head!r} and never closed with {closer!r}"
        names = re.findall(_NAME, text)
        if head == "[":
            return f"a line takes two point names, got {len(names)}"
        if head == "(":
            return f"a circle takes a centre and a point on it, got {len(names)}"
        if head == "/":
            return f"a section takes three collinear points, got {len(names)}"
        if head == "<":
            return f"a polygon takes at least three points, got {len(names)}"
    if "=" in text:
        return "a given point is written `NAME = x, y`"
    if text.startswith("*"):
        return "an unnamed point is written `* x, y`"
    return ("not a construction step; expected one of "
            + ", ".join(form for form, _ in FORMS[:6]))


def parse(source: str) -> List[Dict[str, Any]]:
    """A whole construction, one step per line, in order.

    Blank lines and comments are dropped. Every other line must be a form, and
    the first that is not stops the parse with its line number — the parse is
    all-or-nothing because a construction is a sequence, and a step missing from
    the middle of one does not produce a smaller drawing but a different one.
    """
    steps: List[Dict[str, Any]] = []
    for number, line in enumerate(source.splitlines(), start=1):
        step = parse_line(line, number)
        if step is not None:
            steps.append(step)
    return steps
