---
name: composer-cue
description: Write and render score cues with Lyria 3 Pro via lyria_cue.py - section-timed cue briefs, RMS map to locate drops and hits, and window cutting to length with fades. Use for any music; never for SFX.
---

# Composer Cue

Script: `scripts/lyria_cue.py` (reuses camera-roll auth; Lyria is on the prod host).

```bash
LC=<plugin>/skills/composer-cue/scripts/lyria_cue.py
python3 $LC render --brief "$BRIEF" --out production/music/EP01/cue_signal_full.mp3
python3 $LC map    --audio production/music/EP01/cue_signal_full.mp3      # find the silence + the slam
python3 $LC cut    --audio .../cue_signal_full.mp3 --start 39.5 --len 20 --out .../cue_signal_20s.mp3
```

## Writing the brief

Lyria renders a **full track** (≈60–120s+), not an exact length; structure the brief in timed sections and cut afterwards.

```
Instrumental only, no vocals. <genre/mood>, <BPM>, <key>, about <N> seconds, in <K> sections.
Section 1 (0:00-0:20) Intro: ...
Section 2 (0:20-0:45) Build: ...
Section 3 (0:45-1:00) Drop: a sudden one-beat total silence, then ...
Section 4 (...) Outro: ... ends with <signature motif> and silence.
<palette words>, high dynamic range.
```

Rules:
- **No artist or track names** — refused as `prohibited_content`. Describe the texture.
- Ask for the silence explicitly ("one-beat total silence before the drop"); it's the most useful sync point you'll get.
- Give the Editor's hit points as section boundaries.
- Deliver full + cut window(s) + `sync_map.md` (where the drop/slam landed, suggested offset to the cut's hit point). Two windows (A/B) when the brief is open.
- Music never sits under dialogue unless the Director asks; the Mixer ducks it either way.
