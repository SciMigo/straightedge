"""The same input renders the same bytes — stated as a test, not a hope.

An agent that caches a figure by the hash of its request, a docs build that
commits generated SVG, a plugin that diffs one render against the last: all of
them are already relying on this. It is worth checking rather than assuming,
because the ways it breaks are quiet. A figure does not fail when it stops being
reproducible; it just renders differently tomorrow, and the diff is attributed
to something else.

The check that matters is `test_the_hash_seed_does_not_change_a_render`, and it
has to spend two subprocesses to be worth anything. Python randomises string
hashing per process, so a stray `for x in some_set` reorders output between
runs while looking perfectly stable inside a single one. A same-process
double-render cannot see it. Dict iteration is insertion-ordered since 3.7 and
is *not* seed-dependent, so sets are the live hazard, and a subprocess pair is
the only thing that catches them.
"""

import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY
from straightedge.diagrams.registry import count_data_marks

from straightedge.examples import EXAMPLES

REPO = Path(__file__).resolve().parents[1]


def _figures():
    return [t for t in list_templates() if t.lane == "figure"]


def _figure(template_id):
    return next(t for t in _figures() if t.id == template_id)


def _payload(template):
    """Real parameters for this template, from the shared corpus.

    Every figure has one, and every one of them changes the output: a template
    rendered with `{}` takes its empty defaults and never enters the loops
    where ordering could vary, so a sweep over bare renders agrees with itself
    however badly ordered the code beneath it is.
    """
    return dict(EXAMPLES[template.id]["params"])


# The program run under two different hash seeds. Kept as source rather than a
# helper import so the child starts a genuinely fresh interpreter.
_CHILD = """
import hashlib, json, sys
sys.path.insert(0, %r)
from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY
from tests.test_determinism import _payload

out = {}
for t in list_templates():
    if t.lane != "figure":
        continue
    for label, arg in (("bare", {}), ("full", _payload(t))):
        try:
            svg = DIAGRAM_REGISTRY[t.id].render(dict(arg))
        except Exception as exc:
            svg = "ERR %%s: %%s" %% (type(exc).__name__, exc)
        out["%%s/%%s" %% (t.id, label)] = hashlib.sha256(svg.encode()).hexdigest()
out["__catalog__"] = hashlib.sha256(
    json.dumps([t.to_dict() for t in list_templates()]).encode()).hexdigest()
# Proof the seed was actually applied. A string's hash is randomised per
# process; if this came back equal under two seeds, PYTHONHASHSEED never
# reached the child and the whole sweep would agree for the wrong reason.
out["__seed_probe__"] = str(hash("straightedge"))
print(json.dumps(out, sort_keys=True))
"""


def _under_seed(seed: str) -> dict:
    # Inherit the environment and override one variable, rather than replacing
    # it. A hand-built env has to be right on every platform this runs on, and
    # the previous one supplied a POSIX `PATH` and nothing else — on Windows
    # that drops `SystemRoot`, which CPython needs to start at all, so the test
    # would fail as a broken test rather than report on the figure lane.
    env = {**os.environ, "PYTHONHASHSEED": seed}
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD % str(REPO)],
        capture_output=True, text=True, timeout=180,
        env=env, cwd=REPO)
    assert proc.returncode == 0, f"child failed under seed {seed}:\n{proc.stderr[-2000:]}"
    return json.loads(proc.stdout)


class TestDeterminism:

    def test_every_figure_has_a_payload_that_draws(self):
        """Guards the sweep below from going quietly hollow. If a template
        loses its payload, or its payload stops being consumed, the seed sweep
        still passes -- it would simply be comparing empty figures.

        "Differs from a bare render" is not enough on its own, and this test
        used to say only that. A template handed something it cannot use still
        returns a document: `project_network` was harvested with a dependency
        cycle and answered "网络图存在循环依赖，无法计算", which differs from the
        bare figure while drawing nothing whatever. Refusal chrome is a
        document and not a drawing, so the payload has to put marks on it.
        """
        for t in _figures():
            assert t.id in EXAMPLES, f"{t.id} has no example"
            impl = DIAGRAM_REGISTRY[t.id]
            drawn = impl.render(_payload(t))
            assert drawn != impl.render({}), (
                f"{t.id}'s payload renders the same as no payload at all")
            assert count_data_marks(drawn) > 0, (
                f"{t.id}'s payload draws no data marks -- it is chrome, or a "
                "refusal, standing in for a figure")

    def test_a_render_repeats_itself(self):
        """Both ways round, and the populated one is the half that can fail.

        The seed sweep renders each populated input exactly once per
        interpreter, so it compares two *first* renders and cannot see a
        template that mutates module-level state as it goes — a cache keyed on
        the last figure's extent, a list built at import and appended to. That
        drifts on the second call within one process and agrees perfectly
        across seeds. This is the test that catches it, and it was watching the
        empty case, where no such loop is entered.
        """
        for t in _figures():
            impl = DIAGRAM_REGISTRY[t.id]
            for params in ({}, _payload(t)):
                where = " (with parameters)" if params else ""
                first = impl.render(dict(params))
                assert first == impl.render(dict(params)) == impl.render(dict(params)), (
                    f"{t.id} drifts between renders{where}")

    def test_the_hash_seed_does_not_change_a_render(self):
        """The one that can actually fail. Two interpreters, two seeds, and
        every figure hashed under each — a set that reached output would sort
        differently between them."""
        a, b = _under_seed("0"), _under_seed("99999")
        probe_a, probe_b = a.pop("__seed_probe__"), b.pop("__seed_probe__")
        assert probe_a != probe_b, (
            "string hashing was identical under both seeds, so PYTHONHASHSEED "
            "never took effect — this sweep would agree no matter what")
        differing = sorted(k for k in a if a[k] != b[k])
        assert not differing, f"hash-seed dependent output: {differing}"
        assert len(a) > 70, f"only {len(a)} renders compared; the sweep shrank"

    def test_rendering_does_not_disturb_the_callers_random_stream(self):
        """`dirichlet_function` seeds a generator to place its scatter. It must
        seed one of its own: `random.seed` reaches into the process-wide stream
        and silently resets the sequence of whoever called us — a figure is not
        entitled to reach outside its own output."""
        random.seed(1234)
        expected = [random.random() for _ in range(5)]
        for t in _figures():
            # Both ways round. A template that reaches for `random` only while
            # laying out actual items would leak through a bare render exactly
            # as it would through the seed sweep -- the same blind spot, in the
            # same file, one test further down.
            for params in ({}, _payload(t)):
                random.seed(1234)
                DIAGRAM_REGISTRY[t.id].render(dict(params))
                assert [random.random() for _ in range(5)] == expected, (
                    f"{t.id} disturbed the caller's random stream"
                    f"{' (with parameters)' if params else ''}")

    def test_a_seeded_figure_ignores_the_callers_seed(self):
        """The other half: its own output must not depend on global state."""
        impl = DIAGRAM_REGISTRY["dirichlet_function"]
        for params in ({}, _payload(_figure("dirichlet_function"))):
            random.seed(1)
            first = impl.render(dict(params))
            random.seed(9999)
            assert impl.render(dict(params)) == first, (
                "the figure changed with the caller's seed"
                f"{' (with parameters)' if params else ''}")

    def test_no_figure_embeds_a_clock_or_a_machine_path(self):
        """Reproducible across time and across machines, not merely across runs
        on this one — a committed SVG carrying a build date diffs every day."""
        import re
        import datetime

        any_date = re.compile(r"20\d\d-[01]\d-[0-3]\d")
        wall_clock = re.compile(r"T\d\d:\d\d:|\d\d:\d\d:\d\d")
        today = datetime.date.today()
        # Built without `%-d`: that directive is a glibc extension and raises
        # ValueError on Windows, so the suite would fail before rendering
        # anything rather than reporting on a figure.
        todays = (today.isoformat(), today.strftime("%Y/%m/%d"),
                  today.strftime("%d %b %Y"),
                  f"{today:%B} {today.day}, {today.year}")

        for t in _figures():
            # The populated render is the one that matters: a date reaches the
            # page through a title, an item loop or a legend, none of which a
            # bare call enters. It is also the output people commit.
            for params in ({}, _payload(t)):
                svg = DIAGRAM_REGISTRY[t.id].render(dict(params))
                where = " (with parameters)" if params else ""
                for root in ("/home/", "/mnt/", "/tmp/", "/Users/"):
                    assert root not in svg, (
                        f"{t.id} embeds a machine path ({root}){where}")
                assert not wall_clock.search(svg), (
                    f"{t.id} embeds a wall-clock time{where}")
                assert not any(stamp in svg for stamp in todays), (
                    f"{t.id} embeds today's date{where} — it will render "
                    "differently tomorrow")
                if not params:
                    # Nothing was supplied, so no date is legitimate. Once
                    # parameters are given, a date on the page is usually one
                    # of *theirs* — `roadmap` draws the range it was handed —
                    # and only a date the caller never supplied is a defect.
                    assert not any_date.search(svg), (
                        f"{t.id} embeds a date though it was given none")

    def test_the_catalog_itself_is_stable(self):
        first = json.dumps([t.to_dict() for t in list_templates()])
        assert hashlib.sha256(first.encode()).hexdigest() == hashlib.sha256(
            json.dumps([t.to_dict() for t in list_templates()]).encode()).hexdigest()
