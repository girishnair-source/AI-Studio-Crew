---
name: editor-assemble
description: Editor, Colorist and Post tools - assemble.py builds a cut from a JSON cut sheet with a render cache (only changed clips re-render), meaning-gated transitions (dissolve=time passed, fade_black=ended, else cut), J-cut audio leads, eased punch-ins and captions, EDL + OTIO; title_reveal.py slams title words with synced bangs; grade.py applies grades and matches a whole scene to one hero shot; deliver.py renders masters per spec. Use for every cut, title, grade and delivery.
---

# Editor Assemble

Scripts: `scripts/assemble.py`, `scripts/title_reveal.py`, `scripts/grade.py`, `scripts/deliver.py`.

```bash
EA=<plugin>/skills/editor-assemble/scripts
python3 $EA/assemble.py --cut production/cuts/EP01_v1.json --out production/cuts/EP01_v1.mp4 --otio
python3 $EA/title_reveal.py --video hook.mp4 --out hook_title.mp4 --words "LIKE," "FOLLOW," "DIE," "OR KILL." --times 10.6 11.6 12.6 13.6 --colors white white "#ff1e28" white --black-at 14.7
python3 $EA/grade.py --in EP01_v1.mp4 --out EP01_v1_graded.mp4 --temp -12 --sat 0.92 --contrast 1.05 --grain 6
python3 $EA/grade.py match --in 4B.mp4 --ref 4A.mp4 --out 4B_matched.mp4
python3 $EA/deliver.py --in EP01_v1_mix.mp4 --show lfdk --ep EP01 --out-dir production/masters --specs 9x16:1080p 16x9:1080p --upload drive
```

## Cut sheet (`EP01_v1.json`)

```json
{"fps": 24, "width": 720, "height": 1280,
 "clips": [
   {"src": "../dailies/EP01_SC04/4A_take1.mp4", "in": 0, "out": "speech", "fade_audio_out": 0.15,
    "overlays": [{"text": "UNKNOWN NUMBER", "y": 1040, "size": 40, "from": 0.6, "to": 3.0}]},
   {"src": "../dailies/EP01_SC04/4B_take1.mp4", "in": 0, "out": "speech", "fade_audio_in": 0.1},
   {"black": 0.4}
 ]}
```
`"out": "speech"` reads `trim_to` from the scene's `qc.json` (speech end + handle).

Per-clip options (all optional): `transition` (`cut` | `dissolve` + `time_passed: true` | `fade_black` + `ended: true`), `transition_s`, `audio_lead_s` (J-cut: this clip's audio starts early under the previous picture), `punch_in: {at, to, dur}` (eased zoom landing on the stressed word), `overlays[].ease` (default true: 8-frame ease-in with a 6 px rise, 5-frame ease-out).

**Render cache / locality.** Each clip part is cached by its spec; a new version re-renders only what changed. `<out>.changes.json` lists `re_rendered` vs `reused` and any transition downgrades. `assemble_v1.py` is the previous, simpler assembler.

```bash
python3 $EA/grade.py match-scene --hero 4A_take1.mp4 --clips 4B_take1.mp4 4C_take1.mp4 --out-dir graded/   # whole scene to one hero
python3 $MX --video cut.mp4 --out cut_mix.mp4 --music cue.mp3 --music-in 2.0 --music-out 28.0 [--broadcast]  # see mixer skill
```

## Rules

1. **Text is a post layer.** Captions, lower-thirds, titles are drawn by `assemble.py` / `title_reveal.py`, never requested from the model (it mis-spells and double-captions). Use a font that has your glyphs (DejaVu has `▸ → ·`; Roboto doesn't).
2. **Hard cuts by default.** Dissolves only when the Director asks.
3. **Version everything.** `EP01_v1`, `_v2`… plus a `.md` cut sheet with reasons. Never overwrite.
4. **Trim to speech + handle**, don't fade over clipped words — a clipped last word is a retake (Voice Director).
5. **Hand off with timecodes**: cut points and hit points to Sound/Composer, the EDL/OTIO to Post.
6. Grades are applied to the **cut**, not to dailies, unless a single take needs a match (`grade.py match`).
