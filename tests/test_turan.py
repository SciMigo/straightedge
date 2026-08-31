from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.turan import graph_params
from straightedge.graphs import GraphError, turan_graph


def test_course_instances_have_balanced_parts_and_exact_edge_counts():
    expected = {(6, 2): ([3, 3], 9), (6, 3): ([2, 2, 2], 12),
                (7, 3): ([3, 2, 2], 16)}
    for (n, r), (sizes, edge_count) in expected.items():
        graph, parts = turan_graph(n, r)
        assert [len(part) for part in parts] == sizes
        assert len(graph.edges) == edge_count
        assert all(not graph.has_edge(left, right)
                   for part in parts for left in part for right in part
                   if left != right)


def test_t73_draws_three_colored_parts_and_the_checked_claim():
    params = graph_params({"n": 7, "r": 3})
    assert len(params["nodes"]) == 7 and len(params["edges"]) == 16
    assert set(params["highlights"]["nodes"].values()) == {
        "color-1", "color-2", "color-3"}
    svg = render_diagram({"type": "turan", "params": {"n": 7, "r": 3}})
    assert "16 edges" in svg and "no K" in svg


def test_invalid_part_count_is_refused_with_a_witness():
    low = refusal_findings("turan", {"n": 7, "r": 0})[0]
    high = refusal_findings("turan", {"n": 7, "r": 8})[0]
    assert low.check == high.check == "turan_input"
    assert low.label == "0" and high.label == "7, 8"


def test_non_integer_parameters_are_rejected_by_the_builder():
    for n, r in ((7.0, 3), (7, True)):
        try:
            turan_graph(n, r)
        except GraphError:
            pass
        else:
            raise AssertionError("non-integer Turán parameter was accepted")


def test_oversized_input_is_refused_before_the_graph_is_materialized(monkeypatch):
    """The 11-vertex drawing cap is a precondition, not a post-build check.

    Constructing T(n,r) first allocates O(n squared) edges merely to discover
    that the resulting figure cannot be drawn.
    """
    import straightedge.diagrams.templates.turan as template

    def should_not_build(*_args, **_kwargs):
        raise AssertionError("oversized Turán graph was materialized")

    monkeypatch.setattr(template, "turan_graph", should_not_build)
    finding = refusal_findings("turan", {"n": 2500, "r": 2})[0]
    assert finding.check == "turan_input" and "at most 11 fit" in finding.message


def test_catalog_publishes_the_template_surface():
    template = {item.id: item for item in list_templates()}["turan"]
    assert {"n", "r", "highlight_clique_free"} <= set(template.params)
    assert template.motion == "none"
