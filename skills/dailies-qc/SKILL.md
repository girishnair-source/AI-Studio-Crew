---
name: dailies-qc
description: Inspect generated clips without loading video into the chat - contact sheets (view with read_file), speech-envelope analysis (speech end, end margin, clipped-last-word and hot-peak flags), last-frame extraction for chaining, and a whole-scene qc.json. Use after every camera roll and before any cut.
---

# Dailies QC

Script: `scripts/dailies_qc.py` (ffmpeg/ffprobe).

```bash
QC=<plugin>/skills/dailies-qc/scripts/dailies_qc.py
python3 $QC scene   --dir production/dailies/EP01_SC04 [--manifest shots.json] # contacts, last frames, audio + ASR + visual QC -> qc.json
python3 $QC full    --video 4A_take1.mp4 --expected "..." --ref front.png      # full audio + ASR + visual continuity check
python3 $QC asr     --video 4A_take1.mp4 --expected "..."                      # ASR word-accuracy critic (WER, missing/extra words)
python3 $QC visual  --video 4A_take1.mp4 --ref front.png --action "..."        # visual continuity, face drift, captions, artifacts
python3 $QC contact --video 4A_take1.mp4 --frames 5                            # then read_file the PNG to *look*
python3 $QC speech  --video 4A_take1.mp4 --profile presenter                   # {"speech_end": 14.6, "margin": 0.4, "f0_std_semitones": 3.4, "monotone": true, ...}
python3 $QC last    --video 4A_take1.mp4                                       # 4A_take1_last.png for CHAIN shots
```

## What each crew member looks for

- **Script Supervisor** — contact sheets vs bible: wardrobe, glasses, hair, props, screen direction, background set, light direction. Face drift between takes.
- **Dialogue Coach / Mixer** — `margin` ≥ 0.4s (else the last word is probably clipped → retake, not fade); `speech-starts-at-zero`; `audio-peaks-hot`; **`monotone-read`** → the DOP's performance tags were too weak or ignored; retake with stronger intention and fewer words, never a faster rate.

## Monotony metric (`--profile`)

Pitch is estimated per 10 ms (autocorrelation, 70–400 Hz); `f0_std_semitones` is word-level pitch movement, `contour_std_semitones` is phrase-level intonation (per-second medians). Thresholds depend on the role — a presenter must move more than a cold villain:

| profile | min f0 std | min contour std | use for |
|---|---|---|---|
| `presenter` | 4.5 | 3.0 | hosts, explainers, influencer pieces, anchors |
| `narration` | 3.5 | 2.2 | VO, documentary |
| `dialogue` (default) | 3.0 | 1.8 | scene dialogue |
| `cold` | 2.0 | 1.0 | deliberately flat reads (villain on the phone, AI voice) |

Calibration from our own dailies: influencer presenter clips 3.4–3.9 st (flagged under `presenter` — matches viewer feedback "monotonous"), hacker call 5.6–6.1 st, Hindi narrator 3.0 st. Treat the flag as a prompt to listen, not a verdict.
- **DOP** — framing and motion read as designed; vertical crops; whip-pans that lost the subject.
- **Editor** — uses `trim_to` as the default out-point per take.

## Rules

- Never `read_file` an `.mp4`. Contact sheets and envelopes are the eyes and ears.
- `asr` and `visual` use Gemini Flash (`AGY_QC_MODEL`, default `gemini-2.5-flash`) via Vertex; pass `--no-llm` (or `--no-llm-qc` to `retake_governor.py`) for offline audio/ffmpeg-only QC.
- Write findings to `dailies/<scene>/continuity.md` (Script Sup) and keep `qc.json` machine-readable for the Editor.
