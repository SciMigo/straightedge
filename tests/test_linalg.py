"""The linear-algebra topic: the maths first, then what the scene does with it.

The geometry is resolved in Python and baked into the emitted scene, so it can
be tested without starting Manim — which is the point of computing it there.
"""

import ast
import re

import pytest

from straightedge import blocking, list_templates, plan_from_template, scene_code_for, validate
from straightedge.linalg import (
    MAX_DIM,
    VIEWS,
    ConceptLinAlg,
    check_view,
    coerce_grid,
    coerce_matrix,
    coerce_vectors,
    determinant,
    eigenpairs,
    matmul,
    span_dimension,
    steps_for,
)
from straightedge.models import Topic
from straightedge.templates import _fit_plane_reach, _matmul_layout


# ------------------------------------------------------------------ the maths


def test_shear_and_scale_has_the_eigenpairs_worked_out_by_hand():
    pairs = eigenpairs([[3, 1], [0, 2]])
    values = [lam for lam, _ in pairs]
    assert values == pytest.approx([3.0, 2.0])

    # lambda=3 fixes the x-axis; lambda=2 fixes the -45 degree direction.
    (_, v3), (_, v2) = pairs
    assert v3 == pytest.approx((1.0, 0.0))
    assert v2[0] == pytest.approx(-v2[1])


def test_a_rotation_reports_no_real_eigenvectors():
    """The finding that matters most: there is nothing invariant to draw.

    A quarter turn moves every direction, so any "eigenvector" drawn on it is
    confidently wrong — the one output this library is built to not produce.
    """
    assert eigenpairs([[0, -1], [1, 0]]) == []


def test_a_repeated_eigenvalue_lists_its_direction_once():
    # 2I scales everything by 2. Reporting two "different" eigenvectors for one
    # eigenvalue would draw two lines where the maths has one eigenspace basis.
    pairs = eigenpairs([[2, 0], [0, 2]])
    assert len(pairs) == 1
    assert pairs[0][0] == pytest.approx(2.0)


def test_a_singular_matrix_has_a_zero_eigenvalue_and_zero_determinant():
    pairs = eigenpairs([[1, 2], [2, 4]])
    assert min(abs(lam) for lam, _ in pairs) == pytest.approx(0.0)
    assert determinant([[1, 2], [2, 4]]) == pytest.approx(0.0)


def test_eigenvectors_come_back_unit_length():
    for lam, vec in eigenpairs([[2, 1], [1, 2]]):
        assert (vec[0] ** 2 + vec[1] ** 2) == pytest.approx(1.0)


@pytest.mark.parametrize("vectors,expected", [
    ([[1, 0], [2, 0]], 1),          # parallel: a line, not a plane
    ([[1, 2], [2, 4]], 1),
    ([[1, 0], [0, 1]], 2),
    ([[0, 0]], 0),
    ([[0, 0], [0, 0]], 0),
])
def test_span_dimension(vectors, expected):
    assert span_dimension(vectors) == expected


def test_a_malformed_matrix_degrades_to_the_identity_rather_than_raising():
    assert coerce_matrix("not a matrix") == ((1.0, 0.0), (0.0, 1.0))
    assert coerce_matrix([[1, 2, 3], [4, 5, 6]]) == ((1.0, 0.0), (0.0, 1.0))


# ------------------------------------------------------------- preconditions


# ----------------------------------------------------------- the preconditions
#
# Reached through ``validate`` rather than by calling the check directly: the
# registry is the part that was missing, and a check nothing dispatches to is
# indistinguishable from no check at all.


def _violations(**params):
    return validate(plan_from_template(ConceptLinAlg.LINEAR_MAP, params))


def test_asking_for_eigenvectors_on_a_rotation_is_reported():
    found = _violations(matrix=[[0, -1], [1, 0]], show_eigenvectors=True)
    assert [v.param for v in found] == ["show_eigenvectors"]
    assert "no real eigenvalues" in found[0].message
    # The scene degrades honestly, so this must not stop the render.
    assert blocking(found) == []


def test_a_drawable_request_reports_nothing():
    assert _violations(matrix=[[3, 1], [0, 2]], show_eigenvectors=True) == []


def test_a_malformed_matrix_blocks_rather_than_drawing_the_identity():
    """The expensive case: a video that narrates a map and shows none."""
    found = blocking(_violations(matrix=[[1, 2, 3], [4, 5, 6]]))
    assert [v.param for v in found] == ["matrix"]


def test_the_identity_passed_deliberately_is_not_reported():
    assert _violations(matrix=[[1, 0], [0, 1]], vectors=[[3, 1], [1, 2]]) == []


def test_vectors_the_scene_would_drop_are_reported_and_are_the_ones_dropped():
    raw = [[1, 2], [1, 2, 3], "nope", [0, 1]]
    found = blocking(_violations(vectors=raw))
    assert [v.param for v in found] == ["vectors"]
    assert "2 of 4" in found[0].message
    assert len(coerce_vectors(raw)) == 2      # the check counted what is drawn


def test_labels_past_the_last_vector_are_reported():
    found = _violations(vectors=[[1, 0], [0, 1]], labels=["u", "v", "w"])
    assert [v.param for v in found] == ["labels"]
    assert found[0].severity == "warn"


def test_a_singular_determinant_is_a_warning_not_a_refusal():
    found = _violations(matrix=[[1, 2], [2, 4]], show_determinant=True)
    assert [v.param for v in found] == ["show_determinant"]
    assert blocking(found) == []


def test_the_catalog_reports_the_parameters_this_concept_is_driven_by():
    """The concept's whole interface is its parameters; listing none is a lie."""
    entry = next(t for t in list_templates()
                 if t.id == ConceptLinAlg.LINEAR_MAP)
    assert set(entry.params) == {
        "matrix", "vectors", "labels", "show_eigenvectors", "show_determinant"}


# ------------------------------------------------------------------ the scene


def _code(**params):
    """Just the generated scene, without the preamble shared by every topic.

    The preamble defines helpers that mention ``Rectangle`` and ``DashedLine``
    for other builders, so asserting on the whole file would pass on text this
    builder never emitted.
    """
    whole = scene_code_for(plan_from_template(ConceptLinAlg.LINEAR_MAP, params))
    return "class GeneratedScene" + whole.split("class GeneratedScene", 1)[1]


def test_the_template_is_in_the_catalog_and_routes_to_the_topic():
    plan = plan_from_template(ConceptLinAlg.LINEAR_MAP, {})
    assert plan.topic == Topic.LINEAR_ALGEBRA
    assert plan.concept == ConceptLinAlg.LINEAR_MAP
    assert plan.match == "concept"


def test_a_rotation_draws_no_eigenline_even_when_asked():
    code = _code(matrix=[[0, -1], [1, 0]], show_eigenvectors=True)
    assert "DashedLine" not in code


def test_eigenlines_are_not_fed_to_the_matrix():
    """An eigenline is invariant *as a set*, so it must not be transformed.

    Passing it to ApplyMatrix redraws the same line lambda times longer, which
    put it 11.8 units outside a 14.2-unit frame and implied to the viewer that
    the invariant direction had moved.
    """
    code = _code(matrix=[[3, 1], [0, 2]], show_eigenvectors=True)
    moving = [ln for ln in code.splitlines() if "moving = VGroup(" in ln]
    assert moving and "eig" not in moving[0]


def test_beat_keys_are_sequential_whatever_is_switched_on():
    import re

    for params in (
        {"vectors": [[1, 0]]},
        {"matrix": [[3, 1], [0, 2]], "show_eigenvectors": True,
         "show_determinant": True},
        {"vectors": [[1, 2], [2, 4]], "show_span": True},
    ):
        keys = re.findall(r'_beat\w*\(self, "(b\d\d)"', _code(**params))
        assert keys == ["b%02d" % i for i in range(1, len(keys) + 1)], params


def test_parallel_vectors_span_a_line_not_the_plane():
    code = _code(vectors=[[1, 2], [2, 4]], show_span=True)
    assert "Rectangle(" not in code       # a plane would be the wrong picture
    assert "the span is a line" in code


def test_independent_vectors_span_the_plane():
    code = _code(vectors=[[1, 0], [0, 1]], show_span=True)
    assert "the span is the whole plane" in code


def test_the_determinant_caption_states_the_computed_area():
    code = _code(matrix=[[3, 1], [0, 2]], show_determinant=True)
    assert "det = 6" in code


# ----------------------------------------------------------------- the frame


def test_the_plane_is_sized_so_its_image_fits_the_frame():
    """Fitting the image, not the grid, is what keeps a big map on screen."""
    half_w, half_h = 7.11, 4.0
    for matrix in ([[3, 1], [0, 2]], [[5, 0], [0, 5]], [[1, 0], [0, 1]],
                   [[0, -1], [1, 0]]):
        x, y = _fit_plane_reach(matrix, half_w, half_h)
        (m00, m01), (m10, m11) = coerce_matrix(matrix)
        assert x * abs(m00) + y * abs(m01) <= half_w + 1e-6
        assert x * abs(m10) + y * abs(m11) <= half_h + 1e-6


def test_a_small_matrix_does_not_inflate_the_grid():
    # Scaling *up* to fill the frame would push a gentle map off the edges.
    assert _fit_plane_reach([[0.1, 0], [0, 0.1]], 7.11, 4.0) == (6.0, 4.0)


# ------------------------------------------------------- the matrix product
#
# The claim this concept makes on screen is that four different-looking
# procedures compute the same product. That is a claim about arithmetic, so it
# is tested as one — against a product worked out by hand, not against
# whichever of the four happens to be implemented first.


A = [[1, 2], [3, 4]]
B = [[0, 1], [1, 1]]
AB = ((2.0, 3.0), (4.0, 7.0))          # by hand: [[0+2, 1+2], [0+4, 3+4]]


def test_the_reference_product_is_the_one_worked_out_by_hand():
    assert matmul(coerce_grid(A), coerce_grid(B)) == AB


@pytest.mark.parametrize("view", VIEWS)
def test_every_view_reproduces_the_product(view):
    """The load-bearing assertion: the readings differ, the answer does not."""
    assert check_view(coerce_grid(A), coerce_grid(B), view) == AB


@pytest.mark.parametrize("view", VIEWS)
def test_a_views_steps_partition_or_accumulate_to_the_whole_product(view):
    """Nothing is contributed twice, and nothing is left out.

    ``check_view`` asserts the sum; this asserts the *shape* of how it is
    reached, which is what distinguishes the readings from one another. Three of
    them settle disjoint sets of cells; ``outer`` writes every cell every step.
    """
    steps = steps_for(coerce_grid(A), coerce_grid(B), view)
    covered = [cell for step in steps for cell in step.out_cells]
    every = {(i, j) for i in range(2) for j in range(2)}
    assert set(covered) == every
    if view == "outer":
        assert len(covered) == len(every) * len(steps)     # accumulation
    else:
        assert len(covered) == len(every)                  # partition


def test_the_outer_view_terms_are_each_rank_one():
    """The whole point of the reading, and the property tensor parallelism uses."""
    for step in steps_for(coerce_grid(A), coerce_grid(B), "outer"):
        rows = [list(r) for r in step.contribution]
        # Rank 1 in 2x2 terms: the determinant of every 2x2 minor vanishes.
        assert abs(rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]) < 1e-9


def test_a_view_that_did_not_reproduce_the_product_would_refuse_to_render(monkeypatch):
    """A scene is not emitted for a procedure that computes the wrong thing."""
    import straightedge.linalg as linalg

    real = linalg.steps_for          # captured before patching, or `broken` recurses

    def broken(a, b, view):
        step = real(a, b, view)[0]
        return [linalg.Step(step.caption, step.a_cells, step.b_cells,
                            step.out_cells, ((0.0, 0.0), (0.0, 0.0)))]

    monkeypatch.setattr(linalg, "steps_for", broken)
    with pytest.raises(ValueError, match="does not reproduce"):
        linalg.check_view(coerce_grid(A), coerce_grid(B), "entry")


def test_non_conforming_shapes_have_no_product():
    with pytest.raises(ValueError, match="do not conform"):
        matmul(coerce_grid([[1, 2, 3]]), coerce_grid([[1, 2]]))


def test_a_ragged_grid_is_refused_rather_than_padded():
    assert coerce_grid([[1, 2], [3]]) is None
    assert coerce_grid([]) is None
    assert coerce_grid("nope") is None


# ------------------------------------------------- the product, as a scene


def _mm(**params):
    params.setdefault("a", A)
    params.setdefault("b", B)
    whole = scene_code_for(plan_from_template(ConceptLinAlg.MATMUL_VIEWS, params))
    return "class GeneratedScene" + whole.split("class GeneratedScene", 1)[1]


@pytest.mark.parametrize("view", VIEWS)
def test_every_view_emits_parsable_python(view):
    ast.parse(_mm(view=view))


@pytest.mark.parametrize("view", VIEWS)
def test_text_is_never_swapped_with_transform(view):
    """``Transform`` zips glyph families, so "0" -> "16" raises at render time.

    ``examples/README.md`` documents this and recommends zero-padding; a matrix
    cell reading ``02`` is a lie about the number, so this builder uses the
    structure-agnostic ``FadeTransform`` everywhere instead.
    """
    code = _mm(view=view)
    assert "FadeTransform(" in code
    assert "Transform(" not in code.replace("FadeTransform(", "")


def test_the_outer_view_counts_up_rather_than_revealing_the_answer():
    """Seeding the grid with the finished product flashes it for a frame."""
    code = _mm(view="outer")
    first_grid = next(ln for ln in code.splitlines() if "_grid('P'" in ln)
    assert "'2'" not in first_grid and "'7'" not in first_grid   # not the answer
    assert code.index("_put('P', 0, 0, '0')") < code.index("_put('P', 0, 0, '2')")


def test_a_partitioning_view_reveals_each_cell_exactly_once():
    code = _mm(view="column")
    assert code.count("cells[('P', 0, 0)][1].animate.set_opacity(1)") == 1


def test_beat_keys_stay_sequential_across_the_views():
    for view in VIEWS:
        keys = re.findall(r'_beat\w*\(self, "(b\d\d)"', _mm(view=view))
        assert keys == ["b%02d" % i for i in range(1, len(keys) + 1)], view


def test_the_product_shown_is_the_computed_one_not_a_typed_one():
    """Change the inputs and every number on screen follows, or it is a caption."""
    code = _mm(a=[[2, 0], [0, 2]], b=[[5, 1], [1, 5]], view="entry")
    assert "'10'" in code            # 2*5, and nothing in the builder types it


# ------------------------------------------------------- and its preconditions


def _mm_violations(**params):
    return validate(plan_from_template(ConceptLinAlg.MATMUL_VIEWS, params))


def test_shapes_that_do_not_conform_block():
    found = blocking(_mm_violations(a=[[1, 2], [3, 4]], b=[[1, 2, 3]]))
    assert [v.param for v in found] == ["b"]
    assert "do not exist" in found[0].message or "does not exist" in found[0].message


def test_a_matrix_too_large_to_read_blocks():
    big = [[1] * 5 for _ in range(5)]
    assert [v.param for v in blocking(_mm_violations(a=big, b=big))] == ["a", "b"]


def test_an_unknown_view_warns_rather_than_blocking():
    found = _mm_violations(a=A, b=B, view="diagonal")
    assert [v.param for v in found] == ["view"]
    assert blocking(found) == []


def test_a_well_formed_product_reports_nothing():
    assert _mm_violations(a=A, b=B, view="outer") == []


def test_the_catalog_publishes_the_products_parameters():
    entry = next(t for t in list_templates() if t.id == ConceptLinAlg.MATMUL_VIEWS)
    assert set(entry.params) == {"a", "b", "view"}
    assert entry.invocation == "prompt"


# ------------------------------------------------------------- the layout
#
# Found by rendering: fixed offsets tuned against 2x2 put grid B on top of the
# product at 4x4, which the library's own `qc` reported as six text_overlap
# errors. Checked here in pure Python so the regression does not need Manim.


def test_the_grids_never_collide_at_any_shape_this_concept_accepts():
    for m in range(1, MAX_DIM + 1):
        for k in range(1, MAX_DIM + 1):
            for n in range(1, MAX_DIM + 1):
                cell, a_at, b_at, out_at = _matmul_layout(m, k, n)

                def span(at, rows, cols):
                    return ((at[0] - cell / 2, at[0] + (cols - 1) * cell + cell / 2),
                            (at[1] - (rows - 1) * cell - cell / 2, at[1] + cell / 2))

                a_x, a_y = span(a_at, m, k)
                b_x, b_y = span(b_at, k, n)
                p_x, p_y = span(out_at, m, n)

                # B sits above the product, sharing its columns.
                assert b_y[0] > p_y[1] + 1e-9, (m, k, n, "B overlaps AB")
                # A sits left of the product, sharing its rows.
                assert a_x[1] < p_x[0] + 1e-9, (m, k, n, "A overlaps AB")
                # A and B share neither, and must not meet at the corner.
                assert a_x[1] < b_x[0] + 1e-9 or a_y[1] < b_y[0] + 1e-9

                # And the whole block stays inside the band left for it.
                assert min(a_x[0], b_x[0], p_x[0]) > -7.11
                assert max(a_x[1], b_x[1], p_x[1]) < 7.11
                assert min(a_y[0], b_y[0], p_y[0]) > -4.0
                assert max(a_y[1], b_y[1], p_y[1]) < 4.0


def test_a_small_product_is_drawn_at_the_capped_size():
    """Small shapes take the cap; only shapes that cannot fit shrink."""
    from straightedge.templates import _MM_CELL_MAX

    cell, *_ = _matmul_layout(2, 2, 2)
    assert cell == pytest.approx(_MM_CELL_MAX)


def test_a_product_past_the_cap_shrinks_rather_than_overflowing():
    """Every shape up to 4x4 draws at full size; past it the cell gives way.

    Preconditions report, they do not mutate, so the builder still has to draw
    an oversized request rather than emit a scene running off the frame. The
    cap exists because shrinking stops being *readable* at 5x5, not because the
    geometry stops working there.
    """
    assert _matmul_layout(MAX_DIM, MAX_DIM, MAX_DIM)[0] < _matmul_layout(2, 2, 2)[0]
    assert _matmul_layout(6, 6, 6)[0] < _matmul_layout(MAX_DIM, MAX_DIM, MAX_DIM)[0]
