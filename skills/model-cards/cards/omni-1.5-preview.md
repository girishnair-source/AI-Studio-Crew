# Model card — Omni 1.5 (preview)  ·  `macaron-cookie`

> **Status legend:** ✅ verified by us (date, evidence) · 📄 documented, not yet verified · ❓ unknown · ❌ known not to work
> Cards are living documents. Every roll teaches something; log it under **Observations** (`model_card.py learn …`) and promote it to a rule when it repeats.

## Identity & access
| | |
|---|---|
| Lane (camera_roll CONFIG) | `preview` |
| Model id | `macaron-cookie` (codename; GA name expected `gemini-omni-1.5-…` — do not hardcode outside CONFIG) |
| Endpoint | `staging-aiplatform.sandbox.googleapis.com` · project `genai-on-vertex-playground` · Interactions API |
| Access | Corp identity only. Laptop `gcloud` on a non-corp account → 403 ✅ (2026-10-19) |
| Last verified reachable | ✅ 2026-11-10 (`camera_roll.py doctor`) |

## Capabilities
| Capability | Status | Notes / evidence |
|---|---|---|
| Tasks | ✅ `text_to_video`, `image_to_video`, `reference_to_video`, `edit`, `extend`, `upscale` | API error message lists exactly these (2026-10-18) |
| Durations | ✅ `5s`, `10s`, `15s` | Hard cap **15 s** per clip |
| Resolutions | ✅ `360p`, `720p`, `1080p`, `4k` | 1080p ≈ 2× render time of 720p |
| Aspect | ✅ `16:9`, `9:16` | |
| Native audio | ✅ speech, SFX, ambience in one pass | Hindi + English code-mix pronounced well ✅ (hacker call, Arvind monologue) |
| Dialogue lip-sync | ✅ good on MCU/CU | |
| Multi-shot in one clip | ✅ with shot-list grammar ("Shot 1 (0-4s)… Hard cut.") | Car chase 4 shots/15 s; racetrack 4 shots |
| On-screen text | ✅ **renders exact text when asked explicitly** ("large white monospaced text typed letter by letter: LIKE FOLLOW DIE") | Hacker terminal plate 2026-10-16 — exact spelling, even a pixel skull |
| Reference images (identity) | ✅ up to 3 tested; first is strongest | Front-facing ref holds a face across 10 clips ✅; back-view-only ref → model invents a face ❌ |
| Chaining (> 15 s) | ✅ `reference_to_video` anchored on previous part's last frame + "exact continuation of the reference image" | Hacker call part 2 matched room/face ✅ |
| `extend` with speech | ❌ "The model is currently unable to process speech edits" (2026-10-18) | Use chaining instead |
| Audio input as voice reference | ❌ not available in production — identity via **voice fingerprint text** only | |
| Typical latency | ✅ 15 s/720p: 70–90 s; 5 s: ~35–45 s; 1080p: ~2× | |
| Usage tokens | ✅ `usage.total_tokens` ≈ 45–50 k per 15 s clip (video-dominated) | Captured into ledger/telemetry |

## Prompting that works (promote to shot-grammar when stable)
- Shot-list grammar: count + duration up front, 3–5 s per shot, one action beat, concrete camera + screen direction, `Hard cut.` as the first words of shots 2+, Style and Audio on separate trailing lines. ✅ fixed single-long-take and jumbled-cut failures.
- Dialogue: voice **fingerprint verbatim** first (identity), then an **intention line** + inline tags `[pause] [beat] [slower] [whisper] [smile] [cold]`, `*emphasis*`, `...`; ≤ 30 words per 15 s. Flat reads came from "say exactly these words, rate 105%" ❌.
- Pauses as `...`, emphasis as `*word*` are honoured in Hindi.
- Say who is **not** seen ("the caller is never shown") or the model may cut to them.
- Negative no-ops: "8K/4K" (resolution is an API param), "rapid zooms" (reads as shake), "high shutter speed" vs "motion blur" (contradiction).

## Known failures & workarounds (also in `safety-staging/triggers.json`)
| Symptom | Cause | Workaround | Status |
|---|---|---|---|
| Output-filter block after a full ~70 s render | person on a ledge/edge over a drop; raised weapon | stage behind a parapet / pointing instead of raised | ✅ |
| Model adds its own captions on talking-head shots | unprompted | overlay text deterministically in post; ignore/trim | ✅ |
| Last word clipped | speech fills the clip | ≤ 30 words/15 s; "finish speaking by N−1.5 s" (governor auto-fix) | ✅ |
| Face drift / borrowed features | no front-facing ref; multiple faces in frame | mandatory `front.png`; one speaking face per shot | ✅ |
| Monotone presenter read | transcript-style prompt | DOP intention + tags; `presenter` monotony profile flags it | ✅ |
| Empty `usage` + failed | transient backend | governor treats as capacity → retry | ✅ |
| `PREFILL_QUEUE_PREEMPTED` (sheddable) | capacity | backoff + fallback lane | ✅ |

## Open questions (❓ — next probes)
- Max reference images accepted (tested 3). · Does `edit` accept dialogue clips? · 4k render time and whether it changes motion quality. · Behaviour with 2 speaking characters in one shot.

## Observations log
<!-- appended by model_card.py learn; newest first; promote repeated items to the tables above -->

- 2026-11-10 📝 scene EP01_SC04: 2/3 shots locked, 7 rolls, 1 escalation type(s) · evidence `/usr/local/google/home/girishnair/.gemini/jetski/brain/285567a3-9453-40d5-8455-2dd26204fda2/scratch/crew_smoke/production/dailies/EP01_SC04/scene_summary.json`
- 2026-11-10 ❌ speech-clipped-at-end persisted after 3 takes (speech-clipped-at-end persisted after 3 take(s)) · shot `EP01_SC04/4B` · evidence `/usr/local/google/home/girishnair/.gemini/jetski/brain/285567a3-9453-40d5-8455-2dd26204fda2/scratch/crew_smoke/production/dailies/EP01_SC04/escalations/4B.json`