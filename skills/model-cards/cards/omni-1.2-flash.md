# Model card — Gemini Omni 1.2 Flash  ·  `gemini-omni-1.2-flash` (GA)

> **Status legend:** ✅ verified by us (date, evidence) · 📄 documented, not yet verified · ❓ unknown · ❌ known not to work
> Cards are living documents. Every roll teaches something; log it under **Observations** (`model_card.py learn …`) and promote it to a rule when it repeats.

## Identity & access
| | |
|---|---|
| Lane (camera_roll CONFIG) | `omni-1.2` (default) |
| Model id | `gemini-omni-1.2-flash` — GA on Vertex AI / Gemini API / AI Studio; `gemini-omni-1.1-flash` traffic is auto-routed here ([announcement](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-omni-1-2-flash/)) |
| Endpoint | `aiplatform.googleapis.com` · Interactions API · project from `AGY_PROJECT` ✅ 2026-11-10 |
| Access | Standard Vertex IAM. (403 on a laptop = `gcloud` signed into an account without access to the project.) |
| Last verified reachable | ✅ 2026-11-10 (`camera_roll.py doctor`) |

## Capabilities
| Capability | Status | Notes / evidence |
|---|---|---|
| Tasks | ✅ `text_to_video`, `image_to_video`, `reference_to_video`, `edit`, `extend`, `upscale` | API error message lists exactly these (2026-10-18) |
| Durations | ✅ **flexible 3–15 s** (any whole second; 3 s → 3.03 s output, 7 s accepted; 2026-11-10) | **Duration is chosen per shot from the script** (`duration.py`); 15 s is the model bound, not a default |
| Resolutions | ✅ `360p`, `720p`, `1080p`, `4k` | 1080p ≈ 2× render time of 720p |
| Aspect | ✅ `16:9`, `9:16` | |
| Native audio | ✅ speech, SFX, ambience in one pass | Hindi + English code-mix pronounced well ✅ (hacker call, Arvind monologue) |
| Dialogue lip-sync | ✅ good on MCU/CU | |
| Multi-shot in one clip | ✅ with shot-list grammar ("Shot 1 (0-4s)… Hard cut.") | Car chase 4 shots/15 s; racetrack 4 shots |
| On-screen text | ✅ **renders exact text when asked explicitly** ("large white monospaced text typed letter by letter: LIKE FOLLOW DIE") | Hacker terminal plate 2026-10-16 — exact spelling, even a pixel skull |
| Reference images (identity) | ✅ 3 tested, first strongest · 📄 up to **6** per request (GA notes) | Front-facing ref holds a face across 10 clips ✅; back-view-only ref → model invents a face ❌ |
| Chaining (> 15 s) | ✅ `reference_to_video` anchored on previous part's last frame + "exact continuation of the reference image" | Hacker call part 2 matched room/face ✅ |
| `extend` with speech | ❌ (observed on the pre-GA build 2026-10-18) — **re-probe on GA**; GA notes advertise conversational multi-turn editing | Chaining remains the safe path |
| Audio input as voice reference | ❌ not available in production — identity via **voice fingerprint text** only | |
| Typical latency | ✅ 3 s/360p: 16 s; 7 s/360p: 19 s; 15 s/720p: 70–90 s; 1080p ≈ 2× | |
| Usage tokens | ✅ 3 s/360p: 6.4 k · 7 s/360p: 14.3 k · 15 s/720p: ≈45–50 k (`output_tokens_by_modality.video`) | Captured into ledger/telemetry; price 📄 \$0.07/s at 720p |

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
| Capacity / preemption | sheddable QoS on shared projects | backoff + fallback lane `omni-1.1` | ✅ |

## Open questions (❓ — next probes)
- Verify 6 reference images bind (📄). · Re-probe `edit`/`extend` with speech on GA (multi-turn editing is advertised). · Confirm 360p→1080p/4K `upscale` round-trip. · 4k render time and whether it changes motion quality. · Behaviour with 2 speaking characters in one shot.

## Observations log
<!-- appended by model_card.py learn; newest first; promote repeated items to the tables above -->


