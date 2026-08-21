"""What this library can draw, enumerated for a caller that cannot guess.

Two lanes reach two renderers, and until now neither could be listed. The
animation builders were private module-level dicts in :mod:`straightedge.planner`
and :mod:`straightedge.templates`; the figure templates had a public registry but
no one function that reported the set. So the only way to find out what existed
was to read the source and guess prompts — which is exactly how the two
text-unreachable concepts below stayed hidden, and why ``mini_lecture`` grew a
private copy of this catalog to check its own drift against.

:func:`list_templates` is that missing function. It answers the question an agent
actually has — *what can this produce, how do I invoke it, and what may I pass* —
across both lanes at once.

The two lanes are invoked differently, and the catalog says which:

``animation`` (Manim → MP4)
    Driven by a **prompt**. ``build_plan`` reads the request and fills the plan;
    the caller does not hand over parameters. ``invocation`` is ``"prompt"`` for
    a concept the planner can route to, and ``"concept-id"`` for one reachable
    only by naming it directly (the job API does this) — the honest label for a
    builder that ships and renders but that no phrasing reaches.

``figure`` (pure-Python → SVG)
    Called by **name** through :func:`straightedge.diagrams.render_diagram` with
    a ``params`` dict. ``invocation`` is ``"name"``.

**On parameters.** Neither lane declares parameter *types* anywhere — both read
an untyped dict at render time. Rather than invent a schema, this reports the
parameter *names* each template actually reads, recovered from the code:

* figure names come from the keys the ``render`` method reads off ``params``;
* animation names come from the precondition check that guards each concept,
  which is the one place a concept's parameters are named and validated.

Extraction reads one level deep: a template whose ``render`` forwards ``params``
to a module-level helper reports the keys read in ``render`` itself, which for
two of the figure templates is none. That is an under-report, never a wrong one
— a listed parameter is always real.

A typed JSON Schema is a declared follow-up; it needs a declaration on each of
the ~50 templates, and inventing types here would be the kind of plausible lie
the rest of this project exists to refuse.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Template:
    """One thing the library can draw."""

    id: str                     # concept string, or diagram type name
    lane: str                   # "animation" | "figure"
    output: str                 # "mp4" | "svg"
    invocation: str             # "prompt" | "concept-id" | "name"
    params: list[str] = field(default_factory=list)
    # Names alone left a caller guessing the shape: an agent asked for the unit
    # circle at "pi/4" because nothing said `angle` is a number of degrees, and
    # got a blank figure. Kept beside `params` rather than replacing it.
    parameters: list[dict] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def list_templates() -> list[Template]:
    """Every template in both lanes, animation first, each lane sorted by id."""
    return _animation_templates() + _figure_templates()


def as_dicts() -> list[dict]:
    """:func:`list_templates` as plain dicts, ready for ``json.dumps``."""
    return [t.to_dict() for t in list_templates()]


# --------------------------------------------------------------- animation lane


def _animation_templates() -> list[Template]:
    from straightedge import topics

    reachable = _text_reachable_concepts()
    param_names = _precondition_params()

    templates = []

    # The topic-level builders. Some topics — geometry, function — have no
    # concepts at all and are reachable *only* here, so omitting the topic layer
    # drops them from the catalog entirely. A topic is listed when its generic
    # form (``concept=None``) actually renders, which the probe verifies.
    for topic in sorted(_generic_topics()):
        templates.append(Template(
            id=topic,
            lane="animation",
            output="mp4",
            invocation="prompt",
            params=[],
            parameters=[],
            summary=f"{topic} (generic)",
        ))

    # Read from the topic registry rather than from a tuple of enums listed
    # here. That tuple was the quietest of the four lists a new topic had to
    # join: a concept missing from it renders perfectly and is invisible to
    # every agent, which is the one failure a *discovery* API must not have.
    for concept in topics.concept_ids():
        reach = concept in reachable
        templates.append(Template(
            id=concept,
            lane="animation",
            output="mp4",
            # A concept no prompt reaches is not a bug to hide — it renders
            # perfectly when named. Saying so is the point; a silent gap is how
            # cone_slice and tangent_shift went unnoticed until a sweep.
            invocation="prompt" if reach else "concept-id",
            params=param_names.get(concept, []),
            # Names only in this lane: an animation parameter is declared by a
            # precondition, which states the name and not a default to read a
            # type off. Saying nothing beats guessing.
            parameters=[{"name": name} for name in param_names.get(concept, [])],
            summary=_concept_summary(concept),
        ))
    return templates


#: Canonical prompts, one per concept the planner is meant to route. Reachability
#: is *verified* against these rather than declared: the test suite asserts each
#: routes to its concept, and that the orphans below are reached by none of them.
CANONICAL_PROMPTS: dict[str, str] = {
    "calculus/derivative_tangent": "画 y=x^2 的导数，用割线逼近切线",
    "calculus/riemann_integral": "画 y=x^2+1 的积分面积，用黎曼矩形展示",
    "calculus/ftc_accumulation": "用 y=x^2 展示微积分基本定理，变上限面积函数 F(x)",
    "calculus/taylor_series": "画 sin(x) 的泰勒展开，多项式逼近",
    "trig/graph_transform": "画 y=2sin(3x)+1 的图像",
    "trig/unit_circle_to_sine": "用单位圆展示正弦函数的生成",
    "conic/ellipse_foci": "画一个圆锥曲线中的椭圆，显示焦点和长轴",
    "conic/parabola_focus_directrix": "画抛物线的焦点和准线",
    "3d/solid_overview": "画一个圆柱",
    "3d/three_views": "画一个正方体，展示三视图",
    "3d/cube_section": "画一个正方体的截面，过 A B C 三点",
    "3d/sphere_section": "球的截面是什么形状",
    "linear_algebra/linear_map": "画一个线性变换，展示特征向量",
    "linear_algebra/matmul_views": "画矩阵乘法，用外积的方式展示",
}


#: One bare prompt per topic, to find which render generically. A topic that
#: always specialises to a concept (3d, calculus) is reachable only through that
#: concept and is not listed twice.
TOPIC_PROMPTS: dict[str, str] = {
    "geometry": "画一个三角形，展示相似",
    "function": "画 y=x^2-4x+3",
    "trig": "画一个正弦函数",
    "conic": "画一个椭圆",
    "3d": "画一个正方体",
    "calculus": "画一个导数",
}


def _generic_topics() -> set[str]:
    """Topics whose bare prompt renders a generic scene (``concept=None``).

    Verified, not declared: a topic appears here only if its probe prompt comes
    back with no concept, so a topic that grew a concept and stopped rendering
    generically would drop out of the catalog on its own rather than linger.
    """
    from straightedge.planner import build_plan

    generic = set()
    for topic, prompt in TOPIC_PROMPTS.items():
        plan = build_plan(prompt)
        if plan.topic == topic and plan.concept is None:
            generic.add(topic)
    return generic


def _text_reachable_concepts() -> set[str]:
    """Concepts a prompt actually routes to, computed rather than remembered.

    Runs each canonical prompt through the planner. Computing this — instead of
    hard-coding the reachable set — means a routing change that stranded a
    concept would show up here as an unreachable template, not as a lie in a
    list nobody updated.
    """
    from straightedge.planner import build_plan

    reached = set()
    for prompt in CANONICAL_PROMPTS.values():
        concept = build_plan(prompt).concept
        if concept:
            reached.add(concept)
    return reached


def _precondition_params() -> dict[str, list[str]]:
    """Parameter names each concept's precondition check reads and validates.

    The precondition check is the one place a concept names its parameters —
    the scene builders reach them through shared helpers, where they cannot be
    pinned to a single concept. So this is a best-effort *names* source, not a
    complete one: a concept with no check reports no params, which is honest
    about what can be introspected rather than wrong about what exists.
    """
    from straightedge import preconditions

    out: dict[str, list[str]] = {}
    for concept, checks in preconditions._CHECKS.items():
        names: set[str] = set()
        for check in checks:
            names |= _dict_get_keys(check, receiver="parameters")
        if names:
            out[concept] = sorted(names)
    return out


def _concept_summary(concept: str) -> str:
    """A concept read as prose: ``calculus/derivative_tangent`` → the topic and
    the concept, since the builders carry no per-concept docstring to lift."""
    topic, _, name = concept.partition("/")
    return f"{name.replace('_', ' ')} ({topic})" if name else topic


# ------------------------------------------------------------------ figure lane


def _figure_templates() -> list[Template]:
    from straightedge.diagrams import DIAGRAM_REGISTRY

    templates = []
    for name in sorted(DIAGRAM_REGISTRY):
        template = DIAGRAM_REGISTRY[name]
        templates.append(Template(
            id=name,
            lane="figure",
            output="svg",
            invocation="name",
            params=sorted(_dict_get_keys(template.render, receiver="params")),
            parameters=_dict_get_parameters(template.render, receiver="params"),
            summary=_first_docline(type(template)),
        ))
    return templates


def _first_docline(obj) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.split("\n", 1)[0].strip()


# ----------------------------------------------------------------- shared: AST


def _dict_get_keys(func: Callable, *, receiver: str) -> set[str]:
    """String keys ``func`` reads off ``<receiver>`` — the params it consumes.

    Read from the code rather than a docstring because the code cannot drift
    from itself: ``params.get("n")`` and ``params["n"]`` both count, and a
    parameter the template stops reading stops being reported. ``receiver`` is
    ``"params"`` (figure ``render``) or ``"parameters"`` (a plan's field).

    The function is located inside its parsed module rather than dedented out of
    context — a method is indented and a check is decorated, and both defeat a
    naive reindent. The module always parses.
    """
    keys: set[str] = set()
    for scope, inner in _scopes(func, receiver):
        for node in ast.walk(scope):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and _names(node.func.value) == inner
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
            elif (isinstance(node, ast.Subscript)
                  and _names(node.value) == inner
                  and isinstance(node.slice, ast.Constant)
                  and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
    return keys


# A default that cannot be represented faithfully is omitted rather than
# flattened: publishing `[]` for a matrix whose default is [[1, 0], [0, 1]] is
# a wrong answer where no answer was available.
_OMIT = object()


def _plain(value):
    """Tuples become lists, so the published default is JSON-shaped."""
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _module_consts(func: Callable, root) -> dict:
    """Named defaults a template falls back to, resolved to their values.

    ``params.get("width") or DEFAULT_WIDTH`` states a default as plainly as a
    literal does; the value merely has a name, and the name is usually imported
    from a shared module, so reading the one file's syntax tree would not find
    it. The module is already imported, so ask it — that resolves imported and
    computed constants alike, and gives the value the template will really use.

    Two guards keep this from guessing: a name the function assigns to itself is
    a local and is skipped (the global of the same name is not what it reads),
    and only JSON-shaped values are accepted.
    """
    module = inspect.getmodule(func)
    if module is None or root is None:
        return {}
    local = {target.id
             for node in ast.walk(root) if isinstance(node, ast.Assign)
             for target in node.targets if isinstance(target, ast.Name)}
    local |= {node.target.id for node in ast.walk(root)
              if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    consts = {}
    for name, value in vars(module).items():
        if name in local or name.startswith("__"):
            continue
        if isinstance(value, (bool, int, float, str, list, tuple, dict)):
            consts[name] = value
    return consts


def _default_shape(node, consts: dict | None = None) -> tuple[str, object] | None:
    """Classify a literal default, keeping its contents where they are literal."""
    if consts and isinstance(node, ast.Name) and node.id in consts:
        value = _plain(consts[node.id])
        return _classify(value)
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        # Not a literal — a name or a call. The kind is still worth saying when
        # the node itself declares it; the value is not knowable from here.
        if isinstance(node, (ast.List, ast.Tuple)):
            return "array", _OMIT
        if isinstance(node, ast.Dict):
            return "object", _OMIT
        return None
    if value is None:
        return None
    return _classify(_plain(value))


def _classify(value) -> tuple[str, object] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "boolean", value
    if isinstance(value, (int, float)):
        return "number", value
    if isinstance(value, str):
        return "string", value
    if isinstance(value, list):
        return "array", value
    if isinstance(value, dict):
        return "object", value
    return None


_COERCIONS = {"str": "string", "int": "number", "float": "number", "bool": "boolean"}


def _dict_get_parameters(func: Callable, *, receiver: str) -> list[dict]:
    """The parameters ``func`` reads, with a type and default where the code says.

    Inferred from the default in ``params.get(name, default)``, because that is
    the one place the template states what it expects. A parameter read without
    a usable default is reported with its name alone rather than a guess: saying
    nothing is recoverable, and saying "string" about a number is not.
    """
    scopes = _scopes(func, receiver)
    if not scopes:
        return []
    consts = _module_consts(func, scopes[0][0])
    found: dict[str, dict] = {}
    for root, inner in scopes:
        for node in ast.walk(root):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and _names(node.func.value) == inner
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                continue
            name = node.args[0].value
            entry = found.setdefault(name, {"name": name})
            if "type" in entry or len(node.args) < 2:
                continue
            shape = _default_shape(node.args[1], consts)
            if shape:
                entry["type"] = shape[0]
                if shape[1] is not _OMIT:
                    entry["default"] = shape[1]
        # `params.get("x") or []` states its default just as plainly as
        # `params.get("x", [])` does — it is simply to the right of the `or`, where
        # the walk above was not looking. Half of every parameter read in the lane
        # is written this way (72 of 144), so reading only the two-argument form
        # left most templates publishing names with no types at all: an agent could
        # see that `angle` exists and nothing saying it is a number of degrees,
        # which is how one came to send "pi/4".
        for node in ast.walk(root):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
                continue
            fallback = node.values[-1]
            shape = _default_shape(fallback, consts)
            if not shape:
                continue
            # Every get in the chain shares the one fallback:
            # `params.get("steps") or params.get("construction") or []`.
            for value in node.values[:-1]:
                name = _get_key(value, inner)
                if name is None:
                    continue
                entry = found.setdefault(name, {"name": name})
                if "type" in entry:
                    continue
                entry["type"] = shape[0]
                if shape[1] is not _OMIT:
                    entry["default"] = shape[1]

        # `float(params.get("angle") or DEFAULT)` names the type outright, and does
        # it more firmly than any default can: the coercion is what the template
        # *enforces*, whatever the fallback turns out to be. This is the read that
        # answers "is `angle` degrees or radians?" with "it is a number" instead of
        # with silence — the silence a caller filled in with `pi/4`.
        for node in ast.walk(root):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in _COERCIONS
                    and node.args):
                continue
            # Only gets sitting directly under the coercion: in
            # `int(params.get("rows", len(params.get("data") or [])))` the coercion
            # speaks for `rows`, and says nothing whatever about `data`.
            arg = node.args[0]
            direct = (arg.values if isinstance(arg, ast.BoolOp)
                      and isinstance(arg.op, ast.Or) else [arg])
            for value in direct:
                name = _get_key(value, inner)
                if name is None:
                    continue
                found.setdefault(name, {"name": name})["type"] = _COERCIONS[node.func.id]

    for name in _dict_get_keys(func, receiver=receiver):
        found.setdefault(name, {"name": name})
    return [found[name] for name in sorted(found)]


def _get_key(node, receiver: str) -> str | None:
    """``params.get("name")`` → ``"name"``, for any node that is one."""
    if (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and _names(node.func.value) == receiver
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)):
        return node.args[0].value
    return None


def _names(node) -> str | None:
    """The attribute or name a node ends in: ``plan.parameters`` → ``parameters``."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


_MODULE_CACHE: dict[str, ast.Module] = {}


def _is_the_dict(node, name: str) -> bool:
    """Whether ``node`` hands on the params dict itself, not something from it.

    ``params`` and ``params or {}`` are the dict; ``params.get("root")`` and
    ``params["rows"][0]`` are values *inside* it, and a helper receiving one of
    those reads item fields, not parameters. Deliberately narrow: failing to
    follow a hand-off loses a parameter, which the caller can recover from, and
    following the wrong one publishes a parameter that does not exist, which
    they cannot.
    """
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        # `params or {}` — still the dict, or an empty stand-in for it.
        return (any(_is_the_dict(v, name) for v in node.values)
                and all(_is_the_dict(v, name) or isinstance(v, ast.Dict)
                        for v in node.values))
    return False


def _scopes(func: Callable, receiver: str) -> list[tuple[ast.AST, str]]:
    """Every function that reads the params dict, and the name each reads it under.

    A template need not do its reading in ``render``. Some hand the dict
    straight on — ``return _render(params or {})`` — and some keep ``render``
    as an outline that calls ``_normalise_components(params)``,
    ``_tasks_from_params(params)`` and so on. Walking ``render`` alone reported
    the first kind as taking *no parameters at all* (worse than untyped: it
    reads as a template needing no input) and silently dropped whole parameters
    from the second — `gantt` never listed `tasks`, which is the only parameter
    it really has.

    So collect the whole set, and follow each hand-off by position: a helper is
    free to call its argument something else, and the name to look for
    downstream is whatever *it* called the parameter the dict arrived in.
    """
    root = _func_node(func)
    if root is None:
        return []
    module = inspect.getmodule(func)
    tree = _MODULE_CACHE.get(module.__name__) if module is not None else None
    if tree is None:
        return [(root, receiver)]

    module_functions = {n.name: n for n in tree.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    scopes: list[tuple[ast.AST, str]] = [(root, receiver)]
    seen: set[tuple[str, str]] = set()
    queue = list(scopes)
    while queue:
        node, name_here = queue.pop(0)
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
                continue
            target = module_functions.get(call.func.id)
            if target is None:
                continue
            # Which argument carries the dict *itself*? Looking for the name
            # anywhere in the argument is too loose, and loose here means
            # inventing: `_build_tree_from_dict(params.get("root"))` mentions
            # `params` while passing a value out of it, and following that
            # promoted the node's own `left`, `right` and `value` into
            # `binary_tree`'s top-level parameters.
            index = next((i for i, arg in enumerate(call.args)
                          if _is_the_dict(arg, name_here)), None)
            if index is None or index >= len(target.args.args):
                continue
            inner = target.args.args[index].arg
            key = (target.name, inner)
            if key in seen:  # recursion, or two call sites of the same helper
                continue
            seen.add(key)
            scopes.append((target, inner))
            queue.append((target, inner))
    return scopes


def _func_node(func: Callable) -> ast.AST | None:
    """The ``FunctionDef`` for ``func``, found in its parsed module by line.

    Parsing the whole module sidesteps every reindentation problem, and it is
    cached per module so listing the catalog parses each source once, not once
    per template.
    """
    try:
        module = inspect.getmodule(func)
        lineno = func.__code__.co_firstlineno
        source = inspect.getsource(module)
    except (OSError, TypeError, AttributeError):
        return None

    tree = _MODULE_CACHE.get(module.__name__)
    if tree is None:
        tree = _MODULE_CACHE[module.__name__] = ast.parse(source)

    # Match by name, then by nearest line — a decorator shifts the node's own
    # lineno a line or two from ``co_firstlineno``, and taking the closest
    # candidate is robust to that without hard-coding the offset.
    candidates = [n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == func.__name__]
    if not candidates:
        return None
    return min(candidates, key=lambda n: abs(n.lineno - lineno))
