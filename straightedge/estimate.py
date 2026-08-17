"""How long a render will take, before spending it.

A render costs about ten minutes of one core — but *which* render varies 30×,
and until now that was invisible until you paid for it. Measured across every
builder at 480p (2026-08-17, Manim 0.21.0): a flat 2D scene renders in 3–12
seconds, while a 3D one with a moving camera takes 40–95. An agent scheduling a
batch, or deciding whether to render at all, needs that number in front of the
render, not after.

The estimate keys on the one thing that actually predicts the cost — whether the
scene drives a 3D camera — rather than on the concept name, which does not: the
``3d/three_views`` concept renders as flat 2D projections and is among the
fastest scenes there is, while ``3d/sphere_section`` rotates a real surface and
is the slowest. So the split is read from the emitted scene, not the topic.

It is deliberately a *rough* number with a tier attached, not false precision.
The 480p baselines are measured; the scaling to higher qualities multiplies by
frames × pixels, which is an approximation — real per-frame cost is not perfectly
linear in resolution. An agent should read the tier ("quick" vs "slow") as the
reliable signal and the seconds as an order-of-magnitude budget.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .aspect import LANDSCAPE, resolution_for
from .models import AnimationPlan
from .templates import scene_code_for

#: Central wall-clock seconds at 480p/15fps, measured across the builder sweep.
#: A 2D scene ranged 2.7–12.3s and a 3D-camera scene 38–95s, cleanly separated
#: with no overlap — so one baseline per tier is honest, and a tighter per-concept
#: table would only add precision the scaling approximation then throws away.
_BASE_2D_SECONDS = 8.0
_BASE_3D_SECONDS = 60.0

#: The quality the baselines were measured at.
_BASELINE_QUALITY = "l"


@dataclass(frozen=True)
class Estimate:
    """A rough render-time budget, with the tier that is the reliable part."""

    seconds: float          # order-of-magnitude wall clock at ``quality``
    tier: str               # "quick" (2D, seconds) | "slow" (3D camera, ~minute)
    quality: str
    basis: str              # one line on how the number was derived

    def to_dict(self) -> dict:
        return asdict(self)


def estimate(plan: AnimationPlan, quality: str = "l") -> Estimate:
    """Roughly how long rendering ``plan`` at ``quality`` will take.

    Reads the emitted scene to decide the tier, so it costs a template render and
    no Manim — cheap enough to call before every render, which is the point.
    """
    is_3d = _drives_a_camera(scene_code_for(plan))
    base = _BASE_3D_SECONDS if is_3d else _BASE_2D_SECONDS
    seconds = round(base * _quality_factor(quality), 1)
    tier = "slow" if is_3d else "quick"
    basis = (f"{'3D camera' if is_3d else '2D'} scene; "
             f"{base:.0f}s measured baseline at 480p"
             + ("" if quality == _BASELINE_QUALITY
                else f", scaled ×{_quality_factor(quality):.1f} for quality "
                     f"'{quality}'"))
    return Estimate(seconds=seconds, tier=tier, quality=quality, basis=basis)


def _drives_a_camera(scene_code: str) -> bool:
    """Whether the scene rotates a 3D camera — the one strong cost predictor.

    ``ThreeDScene`` is Manim's base class for a scene with a camera to orient;
    its per-frame cost dwarfs a flat scene's. Matched textually so this needs no
    Manim import and stays as cheap as generating the scene.
    """
    return "ThreeDScene" in scene_code


def _quality_factor(quality: str) -> float:
    """Multiplier from the 480p baseline, as frames × pixels.

    Render time grows with the number of frames (the frame rate) and the work per
    frame (the pixel count). This multiplies both, relative to the 480p/15fps
    baseline — an approximation, because per-frame cost is not perfectly linear in
    resolution, and the reason the tier matters more than the seconds at high
    qualities.
    """
    base_w, base_h, base_fps = resolution_for(_BASELINE_QUALITY, LANDSCAPE, None)
    baseline = base_fps * base_w * base_h
    width, height, fps = resolution_for(quality, LANDSCAPE, None)
    return (fps * width * height) / baseline
