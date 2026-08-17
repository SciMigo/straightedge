"""The version is written once, and everything else reads it.

A hardcoded version in a second place does not fail anything at release time —
it just quietly starts lying. `mcp_server.build_server()` advertised ``"0.1"``
through the whole 0.1.x line and would have gone out as ``"0.1"`` on a 0.2.0
package, telling every connected client it was talking to an older server than
it was. Nothing would have caught that, because nothing compared the two.

So the checks here are structural rather than about any particular number: the
package exposes one version literal, `pyproject.toml` derives its own from that
attribute instead of restating it, and the MCP server advertises the same value.
Bumping the literal is then the whole release edit, and these tests fail if
anyone reintroduces a second copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import straightedge
from straightedge import mcp_server

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_the_package_exposes_a_version():
    assert isinstance(straightedge.__version__, str)
    assert "__version__" in straightedge.__all__


def test_the_version_is_a_release_number():
    """Guards against a bump that lands something unpublishable."""
    assert re.fullmatch(r"\d+\.\d+\.\d+([abrc.\-+].*)?$", straightedge.__version__), (
        f"{straightedge.__version__!r} is not a version PyPI will accept"
    )


def test_pyproject_derives_the_version_rather_than_restating_it():
    """The whole point: one literal, so a bump cannot be applied by halves."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in text, (
        "pyproject should declare the version dynamic, not hardcode it"
    )
    assert 'attr = "straightedge.__version__"' in text, (
        "pyproject should read the version from straightedge.__version__"
    )
    assert not re.search(r"(?m)^version\s*=\s*[\"']", text), (
        "a static version = \"...\" reintroduces the drift this prevents"
    )


def test_the_mcp_server_advertises_the_package_version():
    """The regression this file exists for.

    Needs the SDK to construct a real server, so it is skipped when the ``mcp``
    extra is absent — the same gate the rest of the MCP suite uses.
    """
    pytest.importorskip("mcp")
    server = mcp_server.build_server()
    assert server.version == straightedge.__version__


def test_no_module_hardcodes_a_version_string():
    """Catches a new copy before it has a chance to drift.

    Scoped to assignments of a dotted numeric literal to a ``version`` name, so
    it does not trip on the many unrelated uses of the word.
    """
    package = Path(straightedge.__file__).parent
    offenders = []
    for path in sorted(package.rglob("*.py")):
        if path.name == "__init__.py" and path.parent == package:
            continue  # the one place it is allowed to live
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"""(?<!_)version\s*=\s*["']\d+\.\d""", line):
                offenders.append(f"{path.relative_to(package)}:{number}: {line.strip()}")
    assert not offenders, "hardcoded version(s) found:\n" + "\n".join(offenders)
