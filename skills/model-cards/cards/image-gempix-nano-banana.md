# Model card — Image: GemPix / Nano Banana  ·  `gempix-2` (Pro) · `gempix-2-flash-lite-png` (Flash-lite) · `gempix-1`

> ✅ verified · 📄 documented · ❓ unknown · ❌ known not to work

## Identity & access
| | |
|---|---|
| Access path | Google-internal `generate` CLI (`/google/bin/releases/gemini-agents-generate/generate -prod -output=… image -model=…`). External: swap backend in `casting_sheet.py` (`CASTING_BACKEND=vertex`, Nano Banana on Vertex). |
| `-output` | ✅ must be an **absolute path**; relative paths silently produce nothing (2026-10-29) |

## Capabilities
| Capability | Status | Notes |
|---|---|---|
| Character turnaround + expression sheets in one image | ✅ gempix-2-flash-lite | Kesar sheet: 4 views + 5 expressions, consistent |
| Edit pass (`-media-uri`) "change X, keep everything else" | ✅ | added eyebrow notch + amber eyes across all views |
| Photoreal talking-head reference portraits | ✅ | influencer refs A/B |
| Aspect control | ✅ via prompt ("Landscape 16:9") | |
| Latency | ✅ flash-lite 3–6 s; pro 15–25 s; pro frequently `PREFILL_QUEUE_PREEMPTED` (sheddable) → retry or fall to flash-lite | |

## Known failures & workarounds
| Symptom | Cause | Workaround | Status |
|---|---|---|---|
| **Silent no-image** (exit 0, empty log) | "scar over his eyebrow"; "named X, a greedy/arrogant …" | "small pale notch through the left eyebrow"; drop name + negative trait from image prompt; add signature details via **edit pass** | ✅ bisected 2026-10-29 |
| Eye colour drifts in one expression tile | — | one-line edit pass | ✅ |
| Preemption | capacity | retry loop, alternate model | ✅ |

## Prompting that works
- Style block first (medium words: "chalky brush, soft glow, no outlines, not 3D"), then subject, then layout ("Turnaround: front, ¾, side, back. Below, five expression close-ups: …"), then "No text, no labels, no watermark."
- Phrase positively; ban text explicitly or surfaces get invented text.
- Clean sheet first, then edit for signature details (scars, brands, injuries).

## Observations log
<!-- appended by model_card.py learn -->
