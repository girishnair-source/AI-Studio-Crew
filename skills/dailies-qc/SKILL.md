---
name: dailies-qc
description: Inspect generated clips without loading video into the chat - contact sheets (view with read_file), speech-envelope analysis (speech end, end margin, clipped-last-word and hot-peak flags), last-frame extraction for chaining, and a whole-scene qc.json. Use after every camera roll and before any cut.
---

# Dailies QC

Script: `scripts/dailies_qc.py` (ffmpeg/ffprobe).

```bash
QC=<plugin>/skills/dailies-qc/scripts/dailies_qc.py
python3 $QC scene   --dir production/dailies/EP01_SC04          # everything: contacts, last frames, qc.json
python3 $QC contact --video 4A_take1.mp4 --frames 5              # then read_file the PNG to *look*
python3 $QC speech  --video 4A_take1.mp4                         # {"speech_end": 14.6, "margin": 0.4, "flags": [...]}
python3 $QC last    --video 4A_take1.mp4                         # 4A_take1_last.png for CHAIN shots
```

## What each crew member looks for

- **Script Supervisor** — contact sheets vs bible: wardrobe, glasses, hair, props, screen direction, background set, light direction. Face drift between takes.
- **Voice Director / Mixer** — `margin` ≥ 0.4s (else the last word is probably clipped → retake, not fade); `speech-starts-at-zero` (needs a handle); `audio-peaks-hot`.
- **DOP** — framing and motion read as designed; vertical crops; whip-pans that lost the subject.
- **Editor** — uses `trim_to` as the default out-point per take.

## Rules

- Never `read_file` an `.mp4`. Contact sheets and envelopes are the eyes and ears.
- QC is **measurement, not transcription**. Word accuracy needs an ASR pass (Mixer skill, when configured) or a human ear — say so in reports.
- Write findings to `dailies/<scene>/continuity.md` (Script Sup) and keep `qc.json` machine-readable for the Editor.
