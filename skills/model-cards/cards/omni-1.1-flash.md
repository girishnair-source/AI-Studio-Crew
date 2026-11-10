# Model card — Omni 1.1 Flash  ·  `gemini-omni-1.1-flash-preview`

> ✅ verified · 📄 documented, unverified · ❓ unknown · ❌ known not to work

## Identity & access
| | |
|---|---|
| Lane | `prod` (fallback lane for `preview`) |
| Model id | `gemini-omni-1.1-flash-preview` (also `gemini-omni-flash-preview`) |
| Endpoint | `aiplatform.googleapis.com` · Interactions API · project from `AGY_PROJECT` |
| Publisher listing | ✅ present in `global` and `us-central1` (2026-10-31) |
| Reachable | ✅ 2026-11-10 (`doctor`) |

## Capabilities
| Capability | Status | Notes |
|---|---|---|
| Interactions API `video_config.task` | ✅ accepted (probe "created!" 2026-10-31) | same request shape as Omni 1.2 Flash |
| Durations / resolutions | ❓ not probed — assume ≤ Omni 1.2 Flash; run the probe below before relying on 15 s | |
| Multimodal video-to-video, reference video/audio conditioning | 📄 per Conclave deck | **unverified** |
| Extend clips to 30 s | 📄 per deck | **unverified**; likely same speech-edit refusal as 1.5 |
| Upscale 360p/720p → 1080p/4K | 📄 per deck | unverified |
| Native speech quality vs 1.5 | ❓ | expect lower; keep as *draft* lane |

## Use in the studio
- **Fallback lane** on capacity errors and the **draft lane** for Autopilot first passes (360p) once durations are confirmed.
- Not for final masters until a side-by-side with 1.5 is logged here.

## Probe (fill the table above)
```bash
AGY_LANE=prod python3 skills/camera-roll/scripts/camera_roll.py roll --id probe --prompt "A red ball rolls left to right on a wooden table, soft daylight. Audio: faint room tone." --duration 15s --resolution 720p --aspect 16:9 --out .scratch/probe_omni11.mp4
```
Record: accepted durations, render time, usage tokens, whether speech is accepted, whether reference images bind.

## Observations log
<!-- appended by model_card.py learn -->
