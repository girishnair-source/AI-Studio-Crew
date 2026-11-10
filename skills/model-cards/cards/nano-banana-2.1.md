# Model card — Nano Banana 2.1  ·  `gemini-nano-banana-2.1` (Vertex AI / Gemini Enterprise Agent Platform)

> ✅ verified · 📄 documented · ❓ unknown · ❌ known not to work

## Identity & access
| | |
|---|---|
| Model id | `gemini-nano-banana-2.1` — listed in `global` and `us-central1` ✅ (2026-10-31) · [docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/nano-banana-2-1) |
| API | `generateContent` with `responseModalities: ["IMAGE"]`, `imageConfig: {aspectRatio, imageSize}`; conversational edits by sending the image back with an instruction |
| Access path in the studio | `casting_sheet.py` backend `vertex` (default) · `internal` (gLinux `generate` CLI) only as a fallback for internal testers |

## Capabilities (📄 from docs unless marked ✅)
| Capability | Status | Notes |
|---|---|---|
| Resolutions | ✅ 1K 9:16 → 768×1376, 15 s, 2.5k tokens (2026-11-10) · 📄 2K, 4K | use 2K for turnaround sheets so each tile survives cropping |
| Aspect ratios | 📄 1:1, 16:9, 9:16, 2:1, 3:1, 21:9, 1:4 … 8:1 (no edge-tiling at 2K/4K) | sheets at 16:9 or 2:1; identity portraits at 9:16 |
| Reference images | 📄 up to **14**; consistency for up to **4 human characters** and **10 objects** | pass the identity portrait + wardrobe + prop refs on every call (models have no memory) |
| Conversational / mask editing | 📄 "change X, keep everything else" | our signature-detail **edit pass** |
| Text rendering | 📄 crisp multi-line typography | still: no text on character sheets |
| Thinking levels | 📄 `minimal` / `medium` / `high` | `high` for multi-character layouts |
| Search grounding | 📄 real landmarks/brands | off for fiction |

## Capabilities (verified on the previous internal image path; expect the same or better)
| Capability | Status | Notes |
|---|---|---|
| Character turnaround + expression sheets in one image | ✅ (internal path, 2026-10-29) | Kesar sheet: 4 views + 5 expressions, consistent |
| Edit pass (`-media-uri`) "change X, keep everything else" | ✅ | added eyebrow notch + amber eyes across all views |
| Photoreal talking-head reference portraits | ✅ | influencer refs A/B |
| Aspect control | ✅ via prompt ("Landscape 16:9") | |
| Latency | ✅ internal path 3–25 s · Nano Banana 2.1 on Vertex: ❓ measure | |

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
