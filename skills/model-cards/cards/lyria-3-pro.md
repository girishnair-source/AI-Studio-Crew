# Model card — Lyria 3 Pro  ·  `lyria-3-pro-preview`

> ✅ verified · 📄 documented · ❓ unknown · ❌ known not to work

## Identity & access
| | |
|---|---|
| Endpoint | `aiplatform.googleapis.com` (prod) · Interactions API · same auth as camera-roll · project from `AGY_PROJECT` ✅ |
| Also listed | `lyria-3-clip-preview` (❓ untested — likely short clips) |

## Capabilities
| Capability | Status | Notes |
|---|---|---|
| Instrumental cue from text brief | ✅ 2026-10-16 | |
| Output length | ✅ **full track**, not the requested length: 59.5 s for a "20 s" brief; 119 s for a "two minute" brief | always `map` then `cut` |
| Section-timed briefs | ✅ roughly honoured (silence landed at 1:02 for a brief asking 1:00) | |
| Render time | ✅ 18–32 s | |
| Vocals / lyrics | 📄 supported | we only use instrumental |

## Known failures & workarounds
| Symptom | Cause | Workaround | Status |
|---|---|---|---|
| `400 prohibited_content` | artist/track names in the brief ("Trent Reznor", "Mica Levi") | describe the texture instead | ✅ |
| Wrong project in a wrapper CLI (project not found) | wrapper default | call the API directly with `AGY_PROJECT` (`lyria_cue.py`) | ✅ |

## Prompting that works
"Instrumental only, no vocals. <genre/mood>, <BPM>, <key>, about N seconds, in K sections. Section 1 (0:00-0:20) …" + palette words + "high dynamic range". Ask for the **one-beat total silence** explicitly — it's the most useful sync point.

## Observations log
<!-- appended by model_card.py learn -->
