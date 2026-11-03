---
name: sound-sfx
description: Synthesize SFX (no samples, no music) with sfx_synth.py - serial-drama whooshes, sub impacts, air-thuds, title bangs, glitch hits, risers, room tone, phone buzz, dial tone, keystrokes - as single files, a full bank, or a timed stem aligned to the cut. Use for every sound effect need.
---

# Sound SFX

Script: `scripts/sfx_synth.py` (numpy + ffmpeg). 48 kHz mono WAV, optional 320k MP3.

```bash
SX=<plugin>/skills/sound-sfx/scripts/sfx_synth.py
python3 $SX list
python3 $SX make --preset sub_impact --out production/sfx/EP01/dhaam.wav --mp3
python3 $SX bank --out-dir production/sfx/bank --mp3
python3 $SX stem --cues cues.json --len 131.3 --out production/sfx/EP01/sfx_stem.wav
```

`cues.json`: `[{"t": 10.6, "preset": "title_bang"}, {"t": 13.6, "preset": "title_bang_climax", "gain": 1.2}, {"t": 15.0, "preset": "air_thud"}]`

## Preset guide (Indian serial / thriller vocabulary)

| Preset | Use | Length |
|---|---|---|
| `whoosh_shimmer` | dramatic transition, reveal, snap-zoom | 3s |
| `sub_impact` | the "dhaam" shock hit, dark rumble tail | 3s |
| `air_thud` | fast head-turn / crash-zoom "dhuk" | 2s |
| `title_bang` / `title_bang_climax` | one per title word; climax on the last | 1.8 / 2.2s |
| `glitch_hit` | digital/hacker reveals, screen corruption | 1.2s |
| `riser` | into a cut or drop | 4s |
| `room_tone`, `phone_buzz`, `dial_tone`, `keystroke` | diegetic beds and props | var |

Rules: timecodes come from the Editor's cut sheet; deliver individual files **and** the stem; write `cue_sheet.md` (t · preset · gain · note); leave headroom (stem peaks at −1 dBFS) — the Mixer sets final levels.
