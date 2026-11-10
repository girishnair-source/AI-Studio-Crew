---
name: camera-roll
description: Roll video clips (text/reference-to-video with dialogue) through the Vertex Interactions API using camera_roll.py - single CONFIG block for models/lanes, auth providers (env/stubby/gcloud), parallel batch rolls from a manifest, retry + lane fallback on capacity errors, typed safety-block reporting, last-frame extraction for chaining shots past the clip cap, and a ledger for the Line Producer. Use for every generation; never call the API ad hoc.
---

# Camera Roll

Script: `scripts/camera_roll.py` (python3, stdlib + ffmpeg).

## Quick reference

```bash
CR=<plugin>/skills/camera-roll/scripts/camera_roll.py
python3 $CR doctor                                     # auth + lanes reachability
python3 $CR roll --id 4A --prompt "$P" --duration 7s --aspect 9:16 --resolution 720p   # 7s came from duration.py, not a default \
        --image production/bible/characters/rishi/front.png --out production/dailies/EP01_SC04/4A_take1.mp4
python3 $CR batch --manifest shots.json --parallel 6   # all independent shots at once
python3 $CR last-frame --video 4A_take1.mp4 --out 4A_take1_last.png   # for CHAIN shots
```

Manifest entry: `{"id","prompt","duration","aspect","resolution","images":[],"audio":null,"out","lane":null}`.
Output: one JSON line per shot with `status` ∈ `ok | safety | capacity | auth | access | request | timeout | failed`.

## Rules the crew follows

1. **Config lives in one place.** Model IDs, hosts, projects, clip cap, lanes → `CONFIG` at the top of the script (env overrides: `AGY_LANE`, `AGY_FALLBACK_LANE`, `AGY_PROJECT`, `AGY_ACCESS_TOKEN`, `AGY_PRODUCTION_DIR`). Codenames get renamed at launch; nothing else may hardcode them.
2. **Duration is per shot, from the script.** `CONFIG.min/max_clip_seconds` (3–15 s on Omni 1.2 Flash) are the model's bounds; the number for each shot comes from `studio-protocol/scripts/duration.py` via the DOP's ShotList. `--duration` is required on every roll — there is no default. Beats longer than the bound are **chained**: roll part N, `last-frame`, bind it as the first `--image` for part N+1 and say "exact continuation of the reference image" in the prompt. (`extend` task exists but refuses speech — don't use it for dialogue.)
3. **Prompt compile order** (Camera agent): character lock paragraph(s) quoted from `bible/.../notes.md` → voice lock from `bible/voices/<name>/voice.md` → shot block (shot-grammar) → Style line → Audio line.
4. **Reference binding:** `front.png` for anyone speaking or facing camera. Back-view-only refs cause face drift (the model invents a face). Multiple images allowed; first is strongest.
5. **Status handling:**
   - `safety` → do not retry; hand the prompt + `detail` to `stunt-safety`.
   - `capacity` / `timeout` → the script already backed off and tried the fallback lane; if it still fails, Line Producer decides (wait / lane / lower res).
   - `auth` / `access` → Line Producer runs `doctor`. 401 = token; 403 = account/project (common on laptops where gcloud is logged into a non-corp account).
   - `request` → the prompt/params are wrong (unsupported duration/resolution/task); fix, don't retry.
6. **Drafts vs finals.** Drafts at `360p`/`720p` on the default lane; approved shots re-rolled at `resolution_final` from `show.json` only if the draft is approved (Line Producer policy).
7. Every roll appends to `production/reports/ledger.csv` automatically.

## Voice consistency

There is no voice-cloning / audio-identity input in production. Voice identity is carried **in text**: Casting's `bible/voices/<name>/fingerprint.md`, quoted verbatim at the top of every dialogue prompt, followed by the DOP's directed line (intention + audio tags). `--audio` exists only for audio-to-video (driving picture from a finished track); do not use it as a voice reference.

## Known model behaviours (keep updated)

- Will render legible on-screen text when asked explicitly ("large white monospaced text typed letter by letter: LIKE FOLLOW DIE"), but may *also* add its own captions on talking-head shots — Editor overlays text deterministically instead.
- Pronounces Hindi dialogue well; keep `...` for pauses, `*word*` for emphasis.
- Speech that fills the full clip risks clipping the last word — Voice Director keeps ≥ 0.4s margin; Mixer verifies.
- Silent empty results (status completed, no video) are treated as `failed` and retried once; if repeatable, it's a soft content refusal → `stunt-safety`.
