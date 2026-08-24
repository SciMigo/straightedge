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

Each `visual` is the same `{type, params}` envelope accepted by
`render_diagram`. It may use any registered figure except `algorithm_trace`
itself. This keeps array, tree, graph, stack, queue, linked-list, call-stack and
DP layout knowledge in their existing renderers.

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
family is also an error.

An incorrect transition makes the figure blank rather than teaching a false
state change. Call `inspect_algorithm_trace(params)` from
`straightedge.diagrams.templates.algorithm_trace` to obtain structured findings
before rendering.

Omit `transition` for an explanatory step that should not assert one of these
operations. The renderer still requires every child visual to draw data marks.

## Layout

`layout` may be `grid` (the default), `row`, or `column`. `columns` overrides the
automatic column count. `panel_width`, `panel_height`, and `show_step_numbers`
control presentation without changing the child figures. A trace is limited to
12 steps; longer algorithms should be divided into conceptual phases rather
than reduced until their labels cannot be read.
