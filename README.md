# AI Studio Crew

> **You direct. We're the crew.**

An Antigravity plugin that gives a director a complete AI film crew. You brief
the **1st AD**; the AD breaks it down, calls the right crew and tools, runs
dailies, and brings you the cut. You pick the take.

## The crew

| Agent | Owns |
|---|---|
| `first-ad` | Your single point of contact. Breakdown, call sheet, dispatch, dailies, escalation. **Main agent.** |
| `script-supervisor` | Continuity: the show bible, drift flags, last-frame chaining |
| `casting-director` | Character looks: identity portraits, turnarounds, expression sheets |
| `voice-director` | Voice casting/lock, dialogue splitting to clip limits, read audits |
| `dop` | Shot lists in a grammar the generator obeys |
| `camera` | Rolls clips in parallel, binds references, files dailies |
| `stunt-safety` | Stages beats so they pass safety filters without losing the drama |
| `editor` | Cuts, trims to speech, captions/titles as a post layer, EDL/OTIO |
| `colorist` | Grade and look consistency |
| `sound-designer` | SFX bank, whooshes, hits, stems |
| `composer` | Score cues (Lyria), sync maps |
| `mixer` | Ducking, loudness, dialogue QC |
| `line-producer` | Cost, lanes, retries, auth doctor, budget report |
| `post-supervisor` | Masters, captions, manifests, delivery |

## Quick start

1. Install: copy this folder to `~/.gemini/config/plugins/ai-studio-crew/` and restart Antigravity.
2. Select **1st AD** as the main agent (or just address it).
3. Say: *"Start a new production called 'Like Follow Die or Kill', vertical, gritty thriller. Cast the lead from these references."*
4. Then: *"Episode 1, scene 4 — Rishi gets the call. Under 30 seconds. Bring me dailies."*

## Where things live

```
production/
├── show.json              bible/{characters,voices,style}/
├── callsheets/            dailies/<scene>/ (takes, contact sheets, qc.json, continuity.md)
├── cuts/  sfx/  music/    masters/   reports/ (ledger.csv, budget)
```

## Configuration (one place)

`skills/camera-roll/scripts/camera_roll.py` → `CONFIG`: model IDs, hosts, projects, lanes, clip cap.
Env: `AGY_LANE`, `AGY_FALLBACK_LANE`, `AGY_PROJECT`, `AGY_ACCESS_TOKEN`, `AGY_PRODUCTION_DIR`.
Run `python3 skills/camera-roll/scripts/camera_roll.py doctor` to check auth and lanes.

## Requirements

python3, numpy, Pillow, ffmpeg/ffprobe. Image generation currently uses the Google-internal `generate` CLI (GemPix); see `casting-sheet` to swap the backend.

## Status

v0.1 — Sprint 1 scaffold: all 14 crew agents, 9 skills, 10 tools. Next: dailies board UI, ASR word-accuracy critic, Vertex image backend, pilot runs.
