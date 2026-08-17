"""Typed errors serialise to a stable, branchable shape.

The value of these over a bare exception is that a caller reads ``code`` to
decide what to do and ``remedy`` to know what to try — so those fields, and the
fact that ``to_dict`` always produces them, are the contract worth pinning.
"""

from __future__ import annotations

from straightedge.errors import (
    PreconditionError, RenderError, StraightedgeError,
)


def test_to_dict_always_has_the_four_fields():
    err = StraightedgeError("something went wrong")
    assert err.to_dict() == {
        "code": "error",
        "message": "something went wrong",
        "remedy": None,
        "details": {},
    }


def test_a_subclass_carries_its_own_code_and_remedy():
    err = PreconditionError("won't draw what was asked",
                            remedy="Re-run with --force.",
                            details={"violations": ["v1"]})
    d = err.to_dict()
    assert d["code"] == "blocking_precondition"
    assert d["remedy"] == "Re-run with --force."
    assert d["details"]["violations"] == ["v1"]


def test_it_is_still_an_exception():
    """Raisable and catchable as a normal error; the shape is an addition."""
    try:
        raise RenderError("nope", details={"returncode": 1})
    except StraightedgeError as caught:
        assert caught.details["returncode"] == 1
        assert str(caught) == "nope"


def test_absent_remedy_is_none_not_invented():
    """A missing remedy is information; None says 'nothing you can do', honestly."""
    assert StraightedgeError("x").to_dict()["remedy"] is None
