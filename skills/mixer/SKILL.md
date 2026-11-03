---
name: mixer
description: Final audio with mix.py - side-chain ducking of music under dialogue, SFX stem placement, two-pass loudness normalisation to target LUFS/true-peak, and a mix report; plus dialogue QC rules (speech-end margin, hot peaks, word accuracy when ASR is configured). Use after Sound/Composer deliver and for audio QC on dailies.
---

# Mixer

Script: `scripts/mix.py` (ffmpeg).

```bash
MX=<plugin>/skills/mixer/scripts/mix.py
python3 $MX --video production/cuts/EP01_v1.mp4 --out production/cuts/EP01_v1_mix.mp4 \
        --music production/music/EP01/cue_signal_full.mp3 --music-gain 0.10 --music-offset 0 \
        --sfx production/sfx/EP01/sfx_stem.wav --sfx-gain 0.9 --lufs -14 --tp -1
python3 $MX qc --video production/cuts/EP01_v1.mp4          # loudness/true-peak only
```

## Rules

1. **Dialogue is king.** Music is ducked by the dialogue track (ratio 8:1, 20ms attack, 400ms release). Never raise music to add energy — ask the Composer for a hotter cue.
2. **Targets** from `show.json`: short-form default −14 LUFS integrated, −1 dBTP. Broadcast deliverables may need −23/−24 LUFS — Post Supervisor specifies.
3. **Dialogue QC on dailies** (with `dailies-qc speech`): margin ≥ 0.4 s after the last word; `speech-clipped-at-end` or `audio-peaks-hot` → retake request to the Voice Director via the AD, with the specific line.
4. **Word accuracy.** When an ASR tool is available (e.g. the internal `generate` CLI with a transcribe model, or Gemini transcribe via Vertex), transcribe each dialogue clip and diff against the script line; ≥ 1 wrong/missing word = retake. If no ASR is configured, say explicitly in the report that word accuracy was **not** verified.
5. Always write `*.mix_report.json` next to the output (measured LUFS, TP, sources). Post reads it.
