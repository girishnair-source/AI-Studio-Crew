# Model card — Veo 3.1 family  ·  `veo-3.1-generate-001` / `veo-3.1-fast-generate-001` / `veo-3.1-lite-generate-001`

> ✅ verified · 📄 documented, unverified · ❓ unknown · ❌ known not to work
> **This card is mostly 📄/❓.** We have not rolled Veo 3.1 from this studio yet. Do not let an agent treat the documented rows as facts until the probe fills them in.

## Identity & access
| | |
|---|---|
| Model ids | `veo-3.1-generate-001` (Quality), `veo-3.1-fast-generate-001` (Fast), `veo-3.1-lite-generate-001` (Lite) |
| Publisher listing | ✅ all three present in `us-central1` (2026-10-31 model list) |
| API | ❓ **Not confirmed on the Interactions API** — Veo has historically used `:predictLongRunning` on `aiplatform`. `camera_roll.py` needs a `veo` adapter before this lane can exist. |
| Lane | *(not yet in CONFIG)* |

## Capabilities (documented — verify)
| Capability | Status | Notes |
|---|---|---|
| Cinema-grade 1080p / 4K, realistic physics, dramatic lighting | 📄 (Conclave deck) | |
| Fast / Lite tiers for rapid storyboarding and high-volume episodic output | 📄 | candidate **draft lane** |
| Native audio | ❓ | confirm per tier |
| Max duration per clip | ❓ | |
| Reference images / identity | ❓ | expect image-to-video + reference images; count unknown |
| Extend / chaining | ❓ | |
| Aspect | ❓ expect 16:9 and 9:16 | |

## Where it should sit (hypothesis)
- **Veo 3.1 Fast/Lite** → storyboards, animatics, B-roll plates, draft passes (cheap, fast).
- **Veo 3.1 Quality** → hero non-dialogue shots where physics/lighting matter (chases, product beauty).
- **Omni** → anything with dialogue / lip-sync / on-screen text / tight identity.
Treat as hypothesis until side-by-sides are logged.

## Probe plan
1. Confirm API surface (`predictLongRunning` vs Interactions) → add adapter + `veo-fast` lane to CONFIG.
2. Roll the same 3 prompts (car chase, product beauty, talking head) on Veo Fast, Veo Quality, Omni 1.5; log render time, tokens/cost, QC flags, and a one-line verdict each.
3. Fill the table; move stable findings into `shot-grammar` and the Line Producer's lane policy.

## Observations log
<!-- appended by model_card.py learn -->
