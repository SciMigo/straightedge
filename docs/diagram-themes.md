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

`professional` is the default and reproduces the pre-theme renderer. An
unrecognised value also falls back to that default, so an optional visual does
not abort a larger document build.

Agents do not need to hard-code this table. `straightedge.list_templates()` and
the MCP `list_templates` result publish `theme` as a string parameter with an
`enum` containing the values supported by that exact template.

These are separate from the animation themes in `straightedge.style`.
Animation themes control generated Manim scenes and use the names `textbook`,
`paper`, and `dataflow`; SVG themes are dependency-free renderer tokens and are
passed inside the diagram's `params`.
