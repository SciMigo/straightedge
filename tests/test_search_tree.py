"""Search-tree figures compute or verify the invariants they teach."""

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.search_tree import _avl_check, _prepare, _rb_check


def test_template_is_registered():
    assert "search_tree" in DIAGRAM_REGISTRY


def test_bst_is_constructed_from_insertion_order():
    svg = render_diagram({
        "type": "search_tree",
        "params": {"kind": "bst", "values": [8, 3, 10, 1, 6]},
    })
    assert "BST tree" in svg
    for value in (8, 3, 10, 1, 6):
        assert f">{value}<" in svg
    assert 'class="tree-node tree-node-default tree-node-color-black"' not in svg


def test_invalid_explicit_bst_is_refused():
    params = {"kind": "bst", "root": {
        "value": 8, "left": {"value": 10}, "right": {"value": 3}
    }}
    findings = refusal_findings("search_tree", params)
    assert findings[0].check == "bst_order"
    assert render_diagram({"type": "search_tree", "params": params}) == ""


def test_avl_insertion_rotates_and_stays_balanced():
    findings, root, _ = _prepare({"kind": "avl", "values": [30, 20, 10, 25, 28]})
    assert not findings
    assert root is not None and root.value == 20
    assert _avl_check(root)[1] is None


def test_unbalanced_explicit_avl_is_refused():
    params = {"kind": "avl", "root": {
        "value": 3, "left": {"value": 2, "left": {"value": 1}}
    }}
    findings = refusal_findings("search_tree", params)
    assert findings[0].check == "avl_balance"
    assert "balance factor" in findings[0].message


def test_avl_can_show_computed_height_and_balance_factor():
    svg = render_diagram({
        "type": "search_tree",
        "params": {"kind": "avl", "values": [30, 20, 10], "show_balance": True},
    })
    assert "bf=" in svg and "h=" in svg


def test_red_black_insertion_produces_a_valid_colored_tree():
    findings, root, _ = _prepare({
        "kind": "red_black", "values": [7, 3, 18, 10, 22, 8, 11, 26]
    })
    assert not findings
    assert root is not None and root.color == "black"
    assert _rb_check(root)[1] is None
    svg = render_diagram({
        "type": "search_tree",
        "params": {"kind": "red_black", "values": [7, 3, 18, 10, 22]},
    })
    assert "tree-node-color-red" in svg
    assert "tree-node-color-black" in svg


def test_red_root_is_refused():
    params = {"kind": "red_black", "root": {"value": 2, "color": "red"}}
    assert refusal_findings("search_tree", params)[0].check == "red_black_root"


def test_red_parent_with_red_child_is_refused():
    params = {"kind": "red_black", "root": {
        "value": 4, "color": "black",
        "left": {"value": 2, "color": "red", "left": {"value": 1, "color": "red"}},
        "right": {"value": 6, "color": "black"},
    }}
    findings = refusal_findings("search_tree", params)
    assert findings[0].check == "red_black_invariant"
    assert "red child" in findings[0].message


def test_insertion_sequence_can_render_as_animated_svg():
    svg = render_diagram({
        "type": "search_tree",
        "params": {"kind": "avl", "values": [30, 20, 10], "animate": True,
                   "duration_s": 0.5},
    })
    assert "animated-trace" in svg
    assert svg.count("data:image/svg+xml;base64,") == 3
    assert "AVL insertion" in svg


def test_explicit_tree_cannot_claim_an_insertion_animation():
    params = {"kind": "bst", "root": {"value": 1}, "animate": True}
    assert refusal_findings("search_tree", params)[0].check == "search_tree_animation"


def test_duplicate_insertions_are_refused():
    params = {"kind": "bst", "values": [2, 1, 2]}
    assert "duplicate key" in refusal_findings("search_tree", params)[0].message
