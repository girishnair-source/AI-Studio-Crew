---
name: studio-protocol
description: How the AI Studio Crew runs a production - the production folder layout, show.json schema, call sheet / shot list / dailies / cut sheet templates, control modes, and the dispatch order the 1st AD follows. Read this before creating or touching any production.
---

# Studio Protocol

## 1. Create a production

```bash
python3 <plugin>/skills/studio-protocol/scripts/new_production.py \
  --dir ./production --title "Like Follow Die or Kill" --aspect 9:16 --style "gritty cinematic thriller, 35mm grain"
```

Creates the folder tree (see `rules/AGENTS.md`) and `show.json`:

```json
{
  "title": "Like Follow Die or Kill",
  "slug": "lfdk",
  "aspect": "9:16",
  "resolution_draft": "720p",
  "resolution_final": "1080p",
  "style": "gritty cinematic thriller, 35mm grain",
  "control_mode": "dailies",
  "loudness_lufs": -14,
  "episodes": {}
}
```

## 2. Call sheet (1st AD) — `callsheets/EP01_SC04.md`

```markdown
# EP01 SC04 — "The Call"
Brief: <director's words, verbatim>
Format: 9:16 · target 30s · mode: dailies

## Needs
- Characters: Rishi (bible ✓ front ✓ voice ✓), Caller (voice only — no bible needed)
- Departments: Voice Dir (split dialogue), DOP, Stunt&Safety (lint), Camera, QC, Editor, Sound, Mixer
- Not needed: Casting, Composer (no score under dialogue), Colorist (single setup)

## Dispatch order
1. voice-director → voices/caller/voice.md + dialogue parts
2. dop → EP01_SC04_shotlist.md
3. stunt-safety → lint shotlist
4. camera → dailies/EP01_SC04/
5. script-supervisor + mixer → continuity.md, qc
6. editor → cuts/EP01_v1
7. sound-designer → sfx stem ; mixer → mix ; post-supervisor → master

## Decision Log
- 17:05 AD: 2 chained clips (15s+15s), part 2 anchored on part 1 last frame.
- 17:21 Director: take A1 + B. "Tighter on the phone reveal."
```

## 3. Shot list (DOP) — `callsheets/EP01_SC04_shotlist.md`

Use the `shot-grammar` skill. One block per shot:

```markdown
### 4A · 15s · CHAIN none
Camera: tight MCU, handheld 35mm, slow push-in.
Direction: Rishi screen-left, phone to right ear.
Action: phone buzzes on desk (UNKNOWN NUMBER); he picks up, listens; confusion → unease.
Dialogue: CALLER part 1 (see voices/caller/voice.md)  — 38 words
Refs: characters/rishi/front.png
Staging: —
### 4B · 15s · CHAIN 4A
...
Style: dim bedroom, warm lamp + cold phone glow, shallow DOF, thriller.
Audio: room tone, encrypted-line hiss, no music.
```

## 4. Dailies — `dailies/EP01_SC04/`

```
4A_take1.mp4   4A_take1_contact.png   4A_take1_last.png
4B_take1.mp4   ...
qc.json        # from dailies-qc: per take {duration, speech_end, margin, flags[]}
continuity.md  # from script-supervisor
```

## 5. Cut sheet (Editor) — `cuts/EP01_v1.md`

| # | take | in | out | trim reason | overlay |
|---|------|----|-----|-------------|---------|

## 6. Control modes

| mode | AD stops after |
|---|---|
| directors-cut | every shot |
| dailies | the scene's dailies (default) |
| second-unit | the master |

## 7. Dispatch rules of thumb

- Casting/Voice only if the bible is missing or the brief changes a look/voice.
- Stunt & Safety always for thriller/action/children's content; otherwise on block.
- Composer only when the brief wants score, or at the Editor's request.
- Colorist when a scene has >1 lighting setup or dailies show mismatch.
- Line Producer on any 401/403/capacity error and at episode end.
