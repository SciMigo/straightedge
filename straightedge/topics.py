"""Where a topic says what it is, once, instead of in five places.

The figure lane has worked this way from the start: templates self-register into
``diagrams.DIAGRAM_REGISTRY`` and ``diagrams/__init__`` imports them for the side
effect. Thirty-five templates, no central list. :func:`preconditions.register`
is the same pattern again.

The animation lane was the exception, and adding one topic showed the cost.
Linear algebra had to be threaded into four hardcoded lists in four modules —
``Topic.ALL``, the concept enums in :mod:`straightedge.catalog`, and the
``_PLAN_BUILDERS`` / ``_SCENE_BUILDERS`` dicts — plus a keyword tuple and a
priority tuple in :mod:`straightedge.planner`. Each omission failed differently
and none failed loudly:

* miss the catalog's enum tuple and the concept renders perfectly but is
  invisible to :func:`~straightedge.list_templates`, so no agent can find it;
* miss ``_SCENE_BUILDERS`` and every request for the topic silently draws the
  *geometry* scene, because that is the fallback;
* miss the keyword tuple and no prompt ever reaches it.

All three are the failure this library exists to refuse — confident output that
answers a different question. So they are now impossible to write: a topic
declares itself here, its builders attach themselves where they are defined, and
:func:`verify` raises at import if any piece is missing.

Declaring a topic::

    @topic(Topic.LINEAR_ALGEBRA, keywords=("线性变换", "特征值"), priority=0)
    class LinearAlgebra:
        \"\"\"One matrix acting on the plane, or two matrices meeting.\"\"\"
        concepts = ConceptLinAlg

and attaching its builders, next to the code they build::

    @plan_for(Topic.LINEAR_ALGEBRA)      # in planner.py
    def _linear_algebra_plan(request): ...

    @scene_for(Topic.LINEAR_ALGEBRA)     # in templates.py
    def _linalg_scene(plan): ...

The builders stay where they are rather than moving into the topic modules.
That is deliberate: ``templates.py`` is ~3000 lines of scene source and moving
it would bury this change in code motion. What matters is that no *list* names
them — a builder registers itself at its own definition, so it cannot be defined
and forgotten.

**Internal registration only.** Nothing here reads entry points, and that is a
property worth keeping rather than an omission: the catalog verifies its claims
by *probing* — rendering a bare prompt to see whether a topic is generic, running
each canonical prompt to see which concepts a prompt truly reaches. Those
guarantees hold because everything listed shipped in this package. A third-party
topic would appear in the same catalog with the same authority and none of the
same verification, so opening this up is a decision about what
``list_templates`` means, not a loader to bolt on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import AnimationPlan, Topic

#: Builds a plan from a normalised request string.
PlanBuilder = Callable[[str], AnimationPlan]

#: Builds the body of a Manim scene from a plan.
SceneBuilder = Callable[[AnimationPlan], str]

#: Priority for a topic that does not state one. Higher sorts later, so an
#: unranked topic loses a keyword tie to any topic that bothered to rank itself.
DEFAULT_PRIORITY = 50


@dataclass
class TopicSpec:
    """Everything the rest of the library needs to know about one topic.

    Mutable, unlike most of the dataclasses here, because it is filled in two
    stages: the topic module declares its identity at import, and the plan and
    scene builders attach themselves when their own modules load. :func:`verify`
    is what makes that safe — a spec still missing a builder afterwards is an
    error, not a default.
    """

    id: str
    summary: str = ""
    #: Words that route a prompt here. Empty means the topic is unreachable by
    #: keyword and is entered some other way — ``function`` is matched by an
    #: expression in the request, not by vocabulary.
    keywords: tuple[str, ...] = ()
    #: Tie-break when two topics match the same number of keywords. Lower wins.
    priority: int = DEFAULT_PRIORITY
    #: The ``Concept*`` class holding this topic's concept ids, if it has one.
    concepts: type | None = None
    plan: PlanBuilder | None = None
    scene: SceneBuilder | None = None

    @property
    def concept_ids(self) -> list[str]:
        """The concept id strings this topic declares, sorted."""
        if self.concepts is None:
            return []
        return sorted(
            value for name, value in vars(self.concepts).items()
            if not name.startswith("_") and isinstance(value, str)
        )


_REGISTRY: dict[str, TopicSpec] = {}


def topic(topic_id: str, *, keywords: tuple[str, ...] = (),
          priority: int = DEFAULT_PRIORITY, summary: str = "") -> Callable:
    """Declare a topic. Applied to a class whose body carries its ``concepts``.

    A class rather than a call because the docstring belongs somewhere a reader
    will find it, and because ``concepts = ConceptLinAlg`` reads as a statement
    about the topic rather than as an argument.
    """

    def decorator(cls: type) -> type:
        if topic_id in _REGISTRY:
            raise ValueError(
                f"topic {topic_id!r} is already declared by "
                f"{_REGISTRY[topic_id].summary or 'another module'}")
        _REGISTRY[topic_id] = TopicSpec(
            id=topic_id,
            summary=summary or (cls.__doc__ or "").strip().split("\n")[0],
            keywords=tuple(keywords),
            priority=priority,
            concepts=getattr(cls, "concepts", None),
        )
        return cls

    return decorator


def _attach(field_name: str, topic_id: str) -> Callable:
    def decorator(func):
        spec = _REGISTRY.get(topic_id)
        if spec is None:
            raise ValueError(
                f"no topic {topic_id!r} to attach {func.__name__} to; the topic "
                "must be declared with @topic before its builders are imported")
        existing = getattr(spec, field_name)
        if existing is not None:
            raise ValueError(
                f"topic {topic_id!r} already has a {field_name} builder "
                f"({existing.__name__}); {func.__name__} would replace it")
        setattr(spec, field_name, func)
        return func

    return decorator


def plan_for(topic_id: str) -> Callable:
    """Register the decorated function as this topic's plan builder."""
    return _attach("plan", topic_id)


def scene_for(topic_id: str) -> Callable:
    """Register the decorated function as this topic's scene builder."""
    return _attach("scene", topic_id)


# ------------------------------------------------------------------ reading


def spec(topic_id: str) -> TopicSpec | None:
    return _REGISTRY.get(topic_id)


def all_specs() -> list[TopicSpec]:
    """Every registered topic, in tie-break order then by id."""
    return sorted(_REGISTRY.values(), key=lambda s: (s.priority, s.id))


def all_ids() -> tuple[str, ...]:
    """Every registered topic id, sorted. Replaces the old ``Topic.ALL``."""
    return tuple(sorted(_REGISTRY))


def concept_ids() -> list[str]:
    """Every concept id across every topic, sorted."""
    return sorted(cid for s in _REGISTRY.values() for cid in s.concept_ids)


def topic_of(concept_id: str) -> str | None:
    """Which topic declares this concept, or ``None``.

    Read from the registry rather than by splitting on ``/``. The two agree
    today, and a concept id that stopped agreeing would be a bug worth seeing
    rather than one the parser papers over.
    """
    for s in _REGISTRY.values():
        if concept_id in s.concept_ids:
            return s.id
    return None


def detect(text: str, *, default: str) -> str:
    """The topic whose keywords best match, ties broken by declared priority.

    ``default`` is returned when nothing matches at all, which is the planner's
    long-standing behaviour: never refuse, fall back to the generic scene, and
    let ``AnimationPlan.match`` tell the caller it was a fallback.
    """
    lowered = text.lower()
    best: TopicSpec | None = None
    best_score = 0
    for s in all_specs():                       # already in priority order
        score = sum(1 for word in s.keywords if word.lower() in lowered)
        if score > best_score:
            best, best_score = s, score
    return best.id if best is not None else default


def plan_builder(topic_id: str) -> PlanBuilder | None:
    s = _REGISTRY.get(topic_id)
    return s.plan if s else None


def scene_builder(topic_id: str) -> SceneBuilder | None:
    s = _REGISTRY.get(topic_id)
    return s.scene if s else None


# ------------------------------------------------------------------ checking


def verify() -> None:
    """Raise unless every topic is completely registered. Called at import.

    This is the function that turns the four silent failures described at the
    top of this module into one loud one. It runs once, when
    :mod:`straightedge` finishes importing, so a half-registered topic cannot
    reach a user at all — never mind reach them as a wrong video.
    """
    problems: list[str] = []

    for s in all_specs():
        # Only a keyword-routed topic needs a plan builder. ``function`` is
        # entered by finding an expression in the request rather than by
        # vocabulary, so ``detect`` can never return it and its plan is built
        # inline with the parsed expression in hand.
        if s.keywords and s.plan is None:
            problems.append(
                f"{s.id}: keyword-routed but has no plan builder — every "
                "request matching its keywords would fall back to another "
                "topic's plan")
        if s.scene is None:
            problems.append(
                f"{s.id}: no scene builder — every request for it would "
                "silently render the geometry scene")

    # A name in ``Topic`` that nobody registered is the same gap seen from the
    # other side: the constant exists, code can reference it, and no builder
    # answers to it.
    declared = {value for name, value in vars(Topic).items()
                if not name.startswith("_") and isinstance(value, str)}
    for missing in sorted(declared - set(_REGISTRY)):
        problems.append(
            f"{missing}: named in models.Topic but never declared with @topic")

    if problems:
        raise RuntimeError(
            "straightedge topic registry is incomplete:\n  "
            + "\n  ".join(problems))


# ------------------------------------------------------- topics with no module
#
# ``geometry`` and ``function`` have no module of their own — their planning and
# their scenes live directly in planner.py and templates.py. They are declared
# here rather than left implicit, because a topic that exists but is not
# declared is exactly what :func:`verify` is meant to catch, and an exemption
# for the two oldest topics would be the hole the check is supposed to close.


@topic(Topic.GEOMETRY,
       keywords=("几何", "三角形", "圆", "角", "相似", "全等", "垂直", "平行"),
       priority=90)
class _Geometry:
    """Plane geometry. Currently one stock triangle; see issue #13."""


@topic(Topic.FUNCTION, priority=80)
class _Function:
    """Plotting an arbitrary expression.

    No keywords on purpose: this topic is reached by *finding an expression* in
    the request (``parse_function``), not by vocabulary. Giving it keywords
    would have it compete for prompts that name no function at all.
    """
