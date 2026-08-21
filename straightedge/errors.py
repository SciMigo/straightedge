"""Errors that tell the caller what to do next, not just what went wrong.

A human reads ``Refusing to render: 2 preconditions failed`` on stderr and knows
to look. An agent cannot: it has to pattern-match prose that is free to change,
and prose carries no ``--force`` to try instead. So the failures a caller is
expected to handle are raised as typed errors, each carrying a machine-readable
``code``, the ``details`` behind it, and — the part that matters — the
``remedy`` that would resolve it.

This is a library concern, not a CLI one. A program calling
:func:`straightedge.render` wants the same structured failure the CLI's
``--json`` mode emits; both read :meth:`StraightedgeError.to_dict`. The CLI is a
consumer of these, not the definition of them.

Only *expected* failures belong here — a plan that will not draw what was asked,
a render host without Manim, an unreadable input. A bug should still raise its
own ``TypeError`` with a traceback; wrapping everything would hide the failures a
caller cannot act on behind the ones it can.
"""

from __future__ import annotations

from typing import Any


class StraightedgeError(Exception):
    """A failure a caller is meant to handle, with the remedy attached.

    ``code`` is a stable slug to branch on (never parse ``message``). ``remedy``
    is one sentence naming the action that resolves it, or ``None`` when nothing
    the caller can do would — a genuinely absent remedy is information too, and
    inventing one would be the plausible lie the rest of this project refuses.
    """

    code = "error"

    def __init__(self, message: str, *, remedy: str | None = None,
                 details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.remedy = remedy
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "remedy": self.remedy,
            "details": self.details,
        }


class RequestError(StraightedgeError):
    """No request to work from — neither text nor a transcribable audio file."""

    code = "no_request"


class InputFileError(StraightedgeError):
    """A file the caller pointed at could not be read or parsed."""

    code = "bad_input_file"


class PreconditionError(StraightedgeError):
    """The plan will not draw what was asked for, and the caller did not force it.

    Carries the blocking violations in ``details["violations"]`` so a caller can
    show or reason about them, and names ``--force`` (or ``force=True``) as the
    override — the whole point of a precondition being a prediction rather than a
    wall.
    """

    code = "blocking_precondition"


class FontError(StraightedgeError):
    """The CJK font a render needs is not installed on this host."""

    code = "font_unavailable"


class RenderError(StraightedgeError):
    """Manim ran and did not produce the expected file.

    ``details`` carries the return code and, when captured, the tail of the
    render log — an agent debugging a failed render needs the log, not a
    pointer to a terminal it cannot see.
    """

    code = "render_failed"


class DependencyError(StraightedgeError):
    """A capability this host lacks — Manim for rendering, a backend for the STT."""

    code = "dependency_missing"


class BlankFigureError(StraightedgeError):
    """A figure drew its frame and no data.

    Reported as a failure rather than a successful empty result: the tool can
    tell from its own mark count that nothing landed, and `ok: true` beside zero
    marks is a claim of success it has already disproved.
    """

    code = "blank_figure"


class UnknownTemplateError(StraightedgeError):
    """A template was named by an id the registry does not hold.

    Distinct from :class:`RequestError`, whose ``no_request`` code means there
    was nothing to work from at all. An agent that named `orgchart` instead of
    `org_chart` has a request; it has a typo, and a code saying "no request"
    sends it looking in the wrong place. ``details["known"]`` carries the ids
    that do exist, so the fix is in the reply rather than one call away.
    """

    code = "unknown_template"
