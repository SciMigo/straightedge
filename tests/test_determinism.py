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
import random
import subprocess
import sys
from pathlib import Path

from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY

from tests.figure_payloads import PAYLOADS

REPO = Path(__file__).resolve().parents[1]


def _figures():
    return [t for t in list_templates() if t.lane == "figure"]


def _payload(template):
    """Real parameters for this template, from the shared corpus.

    Every figure has one, and every one of them changes the output: a template
    rendered with `{}` takes its empty defaults and never enters the loops
    where ordering could vary, so a sweep over bare renders agrees with itself
    however badly ordered the code beneath it is.
    """
    return dict(PAYLOADS[template.id])


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
print(json.dumps(out, sort_keys=True))
"""


def _under_seed(seed: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD % str(REPO)],
        capture_output=True, text=True, timeout=180,
        env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        cwd=REPO)
    assert proc.returncode == 0, f"child failed under seed {seed}:\n{proc.stderr[-2000:]}"
    return json.loads(proc.stdout)


class TestDeterminism:

    def test_every_figure_has_a_payload_that_draws(self):
        """Guards the sweep below from going quietly hollow. If a template
        loses its payload, or its payload stops being consumed, the seed sweep
        still passes -- it would simply be comparing empty figures."""
        for t in _figures():
            assert t.id in PAYLOADS, f"{t.id} has no payload"
            impl = DIAGRAM_REGISTRY[t.id]
            assert impl.render(_payload(t)) != impl.render({}), (
                f"{t.id}'s payload renders the same as no payload at all")

    def test_a_render_repeats_itself(self):
        for t in _figures():
            impl = DIAGRAM_REGISTRY[t.id]
            first = impl.render({})
            assert first == impl.render({}) == impl.render({}), f"{t.id} drifts between renders"

    def test_the_hash_seed_does_not_change_a_render(self):
        """The one that can actually fail. Two interpreters, two seeds, and
        every figure hashed under each — a set that reached output would sort
        differently between them."""
        a, b = _under_seed("0"), _under_seed("99999")
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
            random.seed(1234)
            DIAGRAM_REGISTRY[t.id].render({})
            assert [random.random() for _ in range(5)] == expected, (
                f"{t.id} disturbed the caller's random stream")

    def test_a_seeded_figure_ignores_the_callers_seed(self):
        """The other half: its own output must not depend on global state."""
        impl = DIAGRAM_REGISTRY["dirichlet_function"]
        random.seed(1)
        first = impl.render({})
        random.seed(9999)
        assert impl.render({}) == first

    def test_no_figure_embeds_a_clock_or_a_machine_path(self):
        """Reproducible across time and across machines, not merely across runs
        on this one — a committed SVG carrying a build date diffs every day."""
        import re
        clock = re.compile(r"20\d\d-[01]\d-[0-3]\d|T\d\d:\d\d:")
        for t in _figures():
            svg = DIAGRAM_REGISTRY[t.id].render({})
            assert not clock.search(svg), f"{t.id} embeds a timestamp"
            for root in ("/home/", "/mnt/", "/tmp/", "/Users/"):
                assert root not in svg, f"{t.id} embeds a machine path ({root})"

    def test_the_catalog_itself_is_stable(self):
        first = json.dumps([t.to_dict() for t in list_templates()])
        assert hashlib.sha256(first.encode()).hexdigest() == hashlib.sha256(
            json.dumps([t.to_dict() for t in list_templates()]).encode()).hexdigest()
