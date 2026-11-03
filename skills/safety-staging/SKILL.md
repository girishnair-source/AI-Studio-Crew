---
name: safety-staging
description: Pre-flight lint of video/image prompts against the studio's known safety-filter triggers (ledge peril, scars, raised weapons, gore, named artists, real people, minors in danger) with staging rewrites that keep the dramatic beat; bisect procedure for unexplained blocks or silent empty outputs; how to add a solved case to the trigger table. Use before every camera roll on thriller/action/kids content and on any block.
---

# Safety Staging

Script: `scripts/prompt_lint.py` · Table: `triggers.json`

```bash
python3 <plugin>/skills/safety-staging/scripts/prompt_lint.py --file shot_4C.txt
python3 <plugin>/skills/safety-staging/scripts/prompt_lint.py --prompt "$P" --json
```

## Two failure modes, two symptoms

| Symptom | What you see | Meaning |
|---|---|---|
| **block** | `status: safety` / "Request blocked due to safety violations" / `prohibited_content` | input or *output* filter refused. Output-filter blocks happen after a full render (~70s) — the prompt was accepted but the result wasn't. |
| **silent** | `completed`, no video/image, exit 0, empty log | model answered with text only (soft refusal). Common on image models for injuries and name+negative-trait combos. |

## Procedure

1. Lint. Apply the suggested staging for each hit; keep the beat, change the staging.
2. If it still fails and the cause isn't obvious, **bisect**: roll 2–4 short variants in parallel (base / +suspect phrase A / +suspect phrase B / +both) at 5s or as images. Whichever variant dies names the trigger.
3. For signature details the image model refuses (scars, brands), generate the **clean sheet first**, then an **edit pass** ("add a small pale notch through the left eyebrow, keep everything else identical"). Edit passes accept more than base prompts.
4. Record the solved case: `prompt_lint.py --add '{...}'` with pattern, symptom, why, rewrite, before/after.
5. Never attempt to evade a filter with obfuscation, misspellings or encoding tricks. Staging ≠ evasion. If a beat cannot be staged legitimately, tell the AD; the Director decides.

## Staging moves that keep the drama

- Peril at height → subject *behind* the parapet, drop still in frame, debris goes over the edge.
- Threat → pursuit: charging, pointing, shouting, towering over; dust and speed carry the fear.
- Injury → consequence: dust, torn sleeve, bruise-coloured shadow, limping.
- Named inspiration → described texture ("cold minimal industrial pulse").
- Child in danger → age up or move the hazard out of frame; keep the reaction shot.
