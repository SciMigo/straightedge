# Narration-driven timing

Let the voice own the clock. Hand the renderer the measured length of each
narration clip and every step of the animation runs for exactly as long as the
sentence spoken over it — no trimming the audio to fit the video, no padding the
video to fit the audio.

The contract in one sentence:

> A measured narration length decides how long its step runs, and a step with no
> measurement keeps exactly the timing it was written with.

That second half matters more than it looks. It is what lets you convert one
scene at a time, and it means a silent render is unaffected by this feature
existing.

## The seam: durations are data, not a dependency

Straightedge does not synthesise speech. It takes a JSON file mapping a **beat
key** to seconds:

```json
{ "b01": 3.4, "b02": 5.1, "b03": 2.8 }
```

Whatever produced your audio already knows those numbers — a TTS pipeline
computed them, or `ffprobe` can read them off a recording. Passing them as a
file rather than calling a speech API from inside the scene buys three things:

- **The render is offline and reproducible.** No key, no network, no per-render
  cost, and the same inputs give the same frames.
- **Any voice works.** A cloud TTS clip, a local model, or a human at a
  microphone are all just durations by the time they reach the renderer.
- **Audio and video stay separable.** You can re-render the animation without
  re-synthesising a word, and re-record a single line without re-rendering
  anything else.

The trade is that Straightedge will not fetch the audio for you. If you want a
scene that calls a TTS service directly,
[`manim-voiceover`](https://github.com/ManimCommunity/manim-voiceover) is the
established way to do that, and it is a better fit when you want one command to
produce a narrated file from nothing.

## Walkthrough

### 1. Scaffold the scene and read its beat keys

Beat keys are assigned by the builder, so read them from the generated source
rather than assuming a range:

```bash
straightedge scaffold "riemann sum of x squared" --output-dir build/riemann
grep -o '_beat[a-z_]*(self, "b[0-9]*"' build/riemann/scene.py
```

```
_beat(self, "b01"
_beat(self, "b02"
_beat(self, "b03"
_beat_stretch(self, "b04"
_beat(self, "b05"
_beat(self, "b06"
```

**Do not assume the keys are contiguous.** `conic/cone_slice`, for example, uses
three beats numbered up to `b08`: a builder that dropped a step kept the numbers
of the ones around it rather than renumbering, so the map it wants has gaps.
Read what the scene actually calls.

Note which calls are `_beat_stretch` — those steps behave differently (below),
and they are the ones where the pacing choice is visible.

### 2. Measure the narration

One clip per beat, then read each length:

```bash
for f in audio/b*.wav; do
  printf '%s %s\n' "$(basename "$f" .wav)" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"
done
```

Turn that into the JSON map any way you like — a TTS pipeline usually already
has the durations and can write the file directly, without measuring anything.

### 3. Render against the map

```bash
straightedge render "riemann sum of x squared" \
  --output-dir build/riemann \
  --beat-seconds build/riemann/beats.json \
  --quality h
```

`--beat-seconds` applies to `scaffold` and `render`. Mux the audio afterwards
with whatever you already use; Straightedge produces the silent video whose
steps line up with it.

## What the two helpers do

Every generated scene carries these. They are ordinary functions, and knowing
their shape is the difference between narration that fits and narration that
merely doesn't overflow.

**`_beat(scene, key, *anims)` — move, then hold.** The animation plays at its
written pace and the step waits out the rest of the sentence:

```python
used = min(reveal or run_time or 1.4, max(span - 0.2, 0.2))
scene.play(*anims, run_time=used)
scene.wait(span - used)          # when the remainder is worth waiting for
```

So a 6-second sentence over a 1.4-second reveal shows the movement early and
holds the finished frame for 4.6 seconds. That is right when the *result* is
what the voice is discussing — a label appearing, a curve completed.

**`_beat_stretch(scene, key, *anims, tail=…)` — move for the whole sentence.**
The animation is slowed to fill the beat, at a linear rate:

```python
scene.play(*anims, run_time=max(span - tail, 0.3), rate_func=linear)
scene.wait(tail)
```

Right when the *motion* is the content — a sweeping angle, a Riemann partition
refining. Using `_beat` there finishes the movement in the first second and
leaves a frozen frame under five seconds of description, which is the most
common way narrated animation looks wrong.

With no measurement for a key, both fall back to the timing written into the
builder and nothing waits.

## Failure modes

**Silent, and the reason to read this section.**

- **A key that isn't in the scene is never looked up.** Type `"bo1"` for `"b01"`
  and the render succeeds, ignores the voice for that step, and looks completely
  normal. Nothing can detect this for you — the map is data, and a renderer
  cannot know which keys you meant.
- **Not every template is converted.** A correct map handed to a builder with no
  `_beat` calls does exactly nothing, successfully. Check the table below, or
  grep the scaffolded scene: no matches means no beats.

**Loud, and already handled.** The file is validated strictly before anything
renders: unreadable file, invalid JSON, a non-object at the top level, a
non-numeric value, or a value `<= 0` each fail with the remedy in the message.

```
$ straightedge scaffold "riemann sum" --beat-seconds zero.json
--beat-seconds['b01'] must be positive, got 0; a beat with no narration
should be left out, not set to zero
```

## Which builders follow the voice

Measured against the current tree — 9 of 14 concepts:

| Concept | Beats |
|---|---|
| `calculus/derivative_tangent` | 6 (`b01`–`b06`) |
| `calculus/riemann_integral` | 6 (`b01`–`b06`) |
| `calculus/ftc_accumulation` | 6 (`b01`–`b06`) |
| `calculus/taylor_series` | 4 (`b01`–`b04`) |
| `calculus/tangent_shift` | 7 (`b01`–`b07`) |
| `conic/ellipse_foci` | 7 (`b01`–`b08`) |
| `conic/cone_slice` | 3 (numbered up to `b08`) |
| `trig/graph_transform` | 7 (`b01`–`b07`) |
| `trig/unit_circle_to_sine` | 7 (`b01`–`b08`) |

The four `graph/*` concepts are converted too, with `1 + steps` beats — the
count depends on the graph, which is why they are not in the table; read the
keys off the scaffolded scene as above.

Not yet converted: `conic/parabola_focus_directrix`, `3d/solid_overview`,
`3d/sphere_section`, `3d/cube_section`, `3d/three_views`. They render normally
and ignore a beat map.

Reproduce this table after any change:

```bash
python3 - <<'PY'
import re
from straightedge.models import AnimationPlan, Topic
from straightedge.templates import scene_code_for
plan = AnimationPlan(topic=Topic.CALCULUS, title_zh="t", objective_zh="o",
                     english_prompt="p", concept="calculus/riemann_integral")
print(sorted(set(re.findall(r'_beat(?:_stretch)?\(self, "(b\d+)"',
                            scene_code_for(plan)))))
PY
```

## From Python

`--beat-seconds` is a thin wrapper over the same argument on the writer:

```python
from pathlib import Path
from straightedge import build_plan, write_scene, render_scene

plan = build_plan("riemann sum of x squared")
scene = write_scene(
    plan,
    Path("build/riemann"),
    beat_seconds={"b01": 3.4, "b02": 5.1, "b03": 2.8,
                  "b04": 4.0, "b05": 6.2, "b06": 3.1},
)
render_scene(scene, quality="h")
```

`write_scene` is the only writer, so this is the only place the numbers need to
go — there is no separate timing pass to keep in step.

## Converting a builder

If a builder you need is on the unconverted list, the change is mechanical.
Wrap each `self.play(...)` that corresponds to one narrated sentence:

```python
# before
self.play(Create(curve), run_time=2.5)

# after
_beat(self, "b04", Create(curve), run_time=2.5)
```

Keep the existing `run_time`: it stays the reveal pace, and it is what the step
falls back to when no measurement is supplied. Use `_beat_stretch` where the
motion is the content. The regression test to extend lives in
`tests/test_narration_driven_timing.py`, which asserts both halves of the
contract — timing follows a measured beat, and an unmeasured beat is untouched.
