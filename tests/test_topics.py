"""The topic registry, and the four silent failures it is meant to make loud.

Adding linear algebra meant threading it into four hardcoded lists across four
modules. Each omission failed differently and none failed loudly — a concept
missing from the catalog's enum tuple rendered perfectly and was invisible to
every agent; a topic missing from ``_SCENE_BUILDERS`` silently drew the geometry
scene. Those are the tests below: not that the registry stores things, but that
it refuses to be incomplete.
"""

from __future__ import annotations

import pytest

from straightedge import list_templates
from straightedge.models import AnimationPlan, Topic
from straightedge.planner import build_plan
from straightedge.templates import scene_code_for
from straightedge import topics


# --------------------------------------------------------------- completeness


def test_every_declared_topic_is_registered_and_complete():
    """The check that runs at import; asserted here so a failure names itself."""
    topics.verify()


def test_every_topic_constant_has_a_declaration():
    """A name in ``Topic`` that nobody registered is a topic that cannot work."""
    declared = {v for k, v in vars(Topic).items()
                if not k.startswith("_") and isinstance(v, str)}
    assert declared == set(topics.all_ids())


@pytest.mark.parametrize("spec", topics.all_specs(), ids=lambda s: s.id)
def test_every_topic_can_build_a_scene(spec):
    """The gap that used to render the geometry scene under another topic's name."""
    plan = AnimationPlan(topic=spec.id, title_zh="", objective_zh="",
                         english_prompt="")
    assert topics.scene_builder(spec.id) is not None
    assert "class GeneratedScene" in scene_code_for(plan)


@pytest.mark.parametrize("spec", [s for s in topics.all_specs() if s.keywords],
                         ids=lambda s: s.id)
def test_every_keyword_routed_topic_has_a_plan_builder(spec):
    assert topics.plan_builder(spec.id) is not None


def test_a_topic_reached_by_expression_needs_no_keywords():
    """``function`` is entered by finding an expression, not by vocabulary.

    Giving it keywords would have it compete for prompts naming no function at
    all, so its empty keyword tuple is a decision rather than an omission — and
    ``verify`` has to accept it without also accepting a genuinely unrouted
    topic.
    """
    assert topics.spec(Topic.FUNCTION).keywords == ()
    assert build_plan("画 y=x^2-4x+3").topic == Topic.FUNCTION


# ---------------------------------------------------------- the four failures


def _spec_snapshot():
    return {s.id: (s.plan, s.scene) for s in topics.all_specs()}


@pytest.fixture
def restore_registry():
    """Put every builder back, whatever a test does to the registry."""
    snapshot = _spec_snapshot()
    yield
    for topic_id, (plan, scene) in snapshot.items():
        spec = topics.spec(topic_id)
        spec.plan, spec.scene = plan, scene


def test_a_topic_without_a_scene_builder_is_refused(restore_registry):
    topics.spec(Topic.CONIC).scene = None
    with pytest.raises(RuntimeError, match="no scene builder"):
        topics.verify()


def test_a_keyword_routed_topic_without_a_plan_builder_is_refused(restore_registry):
    topics.spec(Topic.CONIC).plan = None
    with pytest.raises(RuntimeError, match="no plan builder"):
        topics.verify()


def test_declaring_the_same_topic_twice_is_refused():
    with pytest.raises(ValueError, match="already declared"):
        @topics.topic(Topic.CONIC)
        class _Duplicate:
            pass


def test_attaching_a_second_builder_is_refused():
    """Two builders for one topic means one of them never runs."""
    with pytest.raises(ValueError, match="already has a scene builder"):
        @topics.scene_for(Topic.CONIC)
        def _shadow(plan):
            return ""


def test_attaching_to_an_undeclared_topic_is_refused():
    with pytest.raises(ValueError, match="no topic 'nonsense'"):
        @topics.plan_for("nonsense")
        def _orphan(request):
            return None


# ------------------------------------------------------------- what it feeds


def test_the_catalog_lists_every_registered_concept():
    """The quietest of the four: a concept that renders and cannot be found."""
    listed = {t.id for t in list_templates() if t.lane == "animation"}
    assert set(topics.concept_ids()) <= listed


def test_no_concept_belongs_to_two_topics():
    seen: dict[str, str] = {}
    for spec in topics.all_specs():
        for concept in spec.concept_ids:
            assert concept not in seen, (concept, seen.get(concept), spec.id)
            seen[concept] = spec.id


def test_a_concept_id_is_prefixed_by_its_own_topic():
    """The registry and the ``topic/concept`` convention must agree.

    Checked rather than assumed, because ``topic_of`` reads the registry while
    most callers split the string, and a concept where those disagree would
    route one way and be catalogued another.
    """
    for concept in topics.concept_ids():
        assert topics.topic_of(concept) == concept.split("/")[0]


def test_priority_breaks_a_keyword_tie_the_declared_way():
    """圆锥 is 3D vocabulary and 圆锥曲线 is conic; the more specific wins."""
    assert build_plan("画一个圆锥曲线的椭圆，焦点在哪").topic == Topic.CONIC
    assert topics.spec(Topic.CONIC).priority < topics.spec(Topic.THREE_D).priority


def test_nothing_matching_falls_back_to_geometry():
    assert topics.detect("完全无关的请求", default=Topic.GEOMETRY) == Topic.GEOMETRY
