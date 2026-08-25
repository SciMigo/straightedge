# SVG diagram themes

The pure-SVG figure lane accepts an optional `theme` parameter on selected
templates. It changes colour, contrast and corner treatment only; dates,
geometry, labels and ordering stay deterministic.

```python
from straightedge.diagrams import render_diagram

svg = render_diagram({"type": "unit_circle", "params": {
    "angle": 45,
    "show_tan": True,
    "theme": "classroom",
}})
```

Theme choices are deliberately family-specific:

| Family | Templates | Themes |
|---|---|---|
| Project plans | `roadmap` | `professional`, `presentation`, `pastel`, `high-contrast`, `print-friendly` |
| Organisations | `org_chart` | `professional`, `friendly`, `pastel`, `high-contrast`, `print-friendly` |
| Mathematics | `unit_circle` | `professional`, `classroom`, `dark`, `high-contrast`, `print-friendly` |
| Data structures | `linked_list` | `professional`, `classroom`, `playful`, `dark`, `high-contrast` |

`professional` is the default and is the pre-theme renderer, byte for byte:
each template declares its own `professional` palette from the constants it
always drew with, and reads the theme unconditionally, so there is no separate
"default" code path to drift. A name the family does not offer falls back to
that default — an optional visual must not abort a larger document build — but
the fallback is logged (`straightedge.diagrams.themes`), the same way a figure
that draws no data is.

Agents do not need to hard-code this table. `straightedge.list_templates()` and
the MCP `list_templates` result publish `theme` as a string parameter with an
`enum` containing the values supported by that exact template; the enum is the
template's own family, so it cannot disagree with what the template accepts.

Every palette keeps its categorical roles — the colours a roadmap tells five
statuses apart by, or a unit circle its sin, cos and tan — visibly apart, and
`print-friendly` is white paper with distinct dark inks rather than five greys,
which do not survive a photocopier. Text drawn over a saturated role colour
(a linked list's comparison node) is drawn in whichever ink reads on it.

These are separate from the animation themes in `straightedge.style`.
Animation themes control generated Manim scenes and use the names `textbook`,
`paper`, and `dataflow`; SVG themes are dependency-free renderer tokens and are
passed inside the diagram's `params`.
