# Algorithm traces

A data-structure figure is one state. An algorithm is the transition between
states. `algorithm_trace` composes the existing figure templates into an ordered
SVG storyboard and can verify common operations before it draws them.

```python
from straightedge.diagrams import render_diagram

svg = render_diagram({"type": "algorithm_trace", "params": {
    "title": "One bubble-sort pass",
    "steps": [
        {
            "label": "Compare 4 and 2",
            "visual": {"type": "array_state", "params": {
                "values": [4, 2, 3],
                "highlights": {"0-1": "comparison"},
            }},
            "transition": {"type": "swap", "indices": [0, 1]},
        },
        {
            "label": "After the swap",
            "visual": {"type": "array_state", "params": {
                "values": [2, 4, 3],
                "highlights": {"1": "current"},
            }},
        },
    ],
}})
```

Each `visual` is the same envelope accepted by `render_diagram` — `{type,
params}`, or the flat form with the parameters beside the type. It may use any
registered figure except `algorithm_trace` itself. This keeps array, tree,
graph, stack, queue, linked-list, call-stack and DP layout knowledge in their
existing renderers.

## Checked transitions

A transition belongs to the step *before* the change and is checked against the
next step's `values` array:

| Type | Required fields | Meaning |
|---|---|---|
| `swap` | `indices: [i, j]` | exchange two array positions |
| `push` | `value` | append to the stack's top |
| `pop` | optional `value` | remove the stack's top |
| `enqueue` | `value`, optional `end` | add at `back` (default) or `front` |
| `dequeue` | optional `value`, optional `end` | remove at `front` (default) or `back` |

`swap` applies to adjacent `array_state` panels, `push`/`pop` to `stack`, and
`enqueue`/`dequeue` to `queue`; claiming an operation over the wrong visual
family is also an error. `type` and `end` are read case-insensitively; `end`
belongs to queue operations only, and a `push`/`pop` that names one is refused.

A `stack` or `queue` panel may draw its own `operation` (the value arriving,
the end it arrives at). Where it does, it must be the transition being
verified — a panel drawing `enqueue 9` at the front under an arrow that says
`enqueue 9` at the back is refused, because the values alone cannot tell the
two pictures apart.

An incorrect transition makes the figure blank rather than teaching a false
state change, and the reason travels with the blank: the MCP `draw` tool and
`straightedge draw --json` report it as a `blank_figure` refusal whose findings
name the check (`trace:state_transition_mismatch`) and the JSON path of the
value at fault (`$.steps[0].transition`). From Python, call
`inspect_algorithm_trace(params)` from
`straightedge.diagrams.templates.algorithm_trace` for the same findings before
rendering.

Omit `transition` for an explanatory step that should not assert one of these
operations. Every child visual must still draw data marks; a child that draws
nothing (`BLANK_STEP`), raises (`CHILD_RENDER_ERROR`), or refuses a claim of
its own — a `construction` with a false claim (`CHILD_REFUSED`) — is reported
against its step, with the child's reason where it has one.

## Layout

`layout` may be `grid` (the default), `row`, or `column`. `columns` sets the
grid's column count; an explicit `row` or `column` layout is not overridden by
it. `panel_width` and `panel_height` size every card; left unset, the cards are
sized to the largest child (within 220–600 by 160–480) so a figure is drawn at
its own scale wherever the bounds allow. `show_step_numbers` controls the
numbered discs. A trace is limited to 12 steps, and a child that would have to
be drawn below 60% of its size to fit its card is refused with the numbers
(`UNREADABLE_STEP`): longer or wider algorithms should be divided into
conceptual phases rather than reduced until their labels cannot be read.

Each child is embedded as an inline SVG image so its styles and ids stay its
own. The legibility check opens those images, so a label clipped or overlapped
inside a child is reported on the storyboard at the scale it is drawn.
