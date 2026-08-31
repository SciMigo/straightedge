from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.floyd_warshall import frames


F4 = {
    "directed": True, "nodes": [{"id": x} for x in "ABCD"],
    "edges": [{"from": a, "to": b, "weight": weight} for a, b, weight in
              [("A", "B", 3), ("B", "C", -2), ("A", "C", 5),
               ("C", "D", 1), ("D", "B", 4), ("A", "D", 10)]],
}


def test_f4_draws_a_table_for_each_intermediate_and_highlights_changes():
    svg = render_diagram({"type": "floyd_warshall", "params": F4})
    assert all(label in svg for label in ("D(0)", "Via A", "Via B", "Via C", "Via D"))
    trace = frames(F4)
    assert trace[-1]["visual"]["params"]["values"][0] == ["0", "3", "1", "2"]
    assert trace[2]["visual"]["params"]["highlights"]


def test_negative_cycle_refusal_names_the_cycle():
    finding = refusal_findings("floyd_warshall", {
        "directed": True, "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B", "weight": 1},
                  {"from": "B", "to": "C", "weight": -3},
                  {"from": "C", "to": "A", "weight": 1}]})[0]
    assert finding.check == "floyd_warshall_negative_cycle"
    assert set(finding.label.split(" → ")) == {"A", "B", "C"}


def test_catalog_publishes_the_template_surface():
    template = {item.id: item for item in list_templates()}["floyd_warshall"]
    assert {"nodes", "edges", "directed", "animate"} <= set(template.params)
    assert template.motion == "optional"


def test_directed_defaults_to_true_as_the_catalog_says():
    """The catalog and render() both read `directed` defaulting to true, but
    the steps coerced the graph with coerce_graph's false — so an input with
    no `directed` key was refused as "needs a directed graph"."""
    params = {"nodes": [{"id": "A"}, {"id": "B"}],
              "edges": [{"from": "A", "to": "B", "weight": 2}]}
    assert refusal_findings("floyd_warshall", params) == []
    assert render_diagram({"type": "floyd_warshall", "params": params})
