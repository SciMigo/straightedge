"""Cost estimation, and the honest signal in it.

The estimate exists so an agent knows which renders are seconds and which are a
minute-plus before spending one — the 30× spread that was invisible until you
paid for it. What is worth pinning is the *tier* (the reliable part), that it
keys on the 3D camera rather than the topic name (the whole reason it is
accurate), and that it costs no Manim to compute.
"""

from __future__ import annotations

import sys

import pytest

from straightedge import build_plan, estimate
from straightedge.estimate import Estimate


def _est(request, quality="l"):
    return estimate(build_plan(request), quality)


class TestTheTier:
    def test_a_flat_scene_is_quick(self):
        e = _est("画一个椭圆")
        assert e.tier == "quick"
        assert e.seconds < 30

    def test_a_3d_camera_scene_is_slow(self):
        e = _est("球的截面是什么形状")           # 3d/sphere_section, a ThreeDScene
        assert e.tier == "slow"
        assert e.seconds > 30

    def test_the_topic_name_does_not_decide_the_tier(self):
        """3d/three_views is a 3d *topic* but renders flat 2D projections — and it
        is one of the fastest scenes. Keying on the topic would call it slow;
        keying on the camera calls it quick, which is what it is."""
        e = _est("画一个正方体，展示三视图")
        assert e.tier == "quick"


class TestQualityScaling:
    def test_higher_quality_costs_more(self):
        low = _est("画一个椭圆", "l").seconds
        high = _est("画一个椭圆", "h").seconds
        assert high > low

    def test_the_baseline_quality_is_the_measured_number(self):
        """At 480p the estimate is the measured baseline, unscaled."""
        assert _est("画一个椭圆", "l").seconds == pytest.approx(8.0)


class TestItStaysCheap:
    def test_estimating_pulls_in_no_manim(self):
        """It reads the emitted scene text; it must never import Manim to do so —
        an estimate that costs a render defeats its own purpose.

        Checked in a clean subprocess, because another test in this suite may
        have imported Manim already; only a fresh interpreter proves estimate
        does not pull it in itself."""
        import subprocess
        code = (
            "import sys; from straightedge import build_plan, estimate; "
            "estimate(build_plan('球的截面是什么形状')); "
            "sys.exit(1 if 'manim' in sys.modules else 0)"
        )
        assert subprocess.run([sys.executable, "-c", code]).returncode == 0

    def test_it_serialises(self):
        d = _est("画一个椭圆").to_dict()
        assert set(d) == {"seconds", "tier", "quality", "basis"}
        assert isinstance(d["basis"], str) and d["basis"]


class TestMatchIsHonestAboutFallback:
    def test_a_supported_concept_reports_a_concept_match(self):
        assert build_plan("画 y=x^2 的导数").match == "concept"

    def test_an_unsupported_request_admits_the_fallback(self):
        """No builder draws the Pythagorean theorem, so the request falls through
        to a generic geometry scene. match must say so rather than let an agent
        present a stock triangle as the thing that was asked for."""
        plan = build_plan("画一个直角三角形，动态展示勾股定理")
        assert plan.concept is None
        assert plan.match == "topic-fallback"
