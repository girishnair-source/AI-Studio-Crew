---
name: model-cards
description: Living knowledge per generative model (Omni 1.2 Flash, Omni 1.1 Flash, Veo 3.1 family, Nano Banana 2.1, Lyria 3 Pro) - access/lane, verified capabilities vs documented claims, prompting that works, known failures with workarounds, open probes, and an observations log that the governor and crew append to after every scene. Camera and the DOP read the card for the active lane before rolling; the Line Producer promotes repeated observations into rules. Use before choosing or prompting a model and after any surprise.
---

# Model Cards

`cards/<model>.md` — one per model family. `scripts/model_card.py` reads, appends and audits them.

## Why
Model behaviour is the thing we keep re-learning the hard way (silent refusals, the 15 s cap, `extend` refusing speech, codename-on-staging-only). A card turns each lesson into a row with a **status** so an agent can tell a fact from a hope:

- ✅ **verified** — we did it, with date and evidence
- 📄 **documented** — a deck or doc says so; not yet tried here
- ❓ **unknown** — a probe is listed
- ❌ **known not to work** — with the workaround

## Who reads what, when
| Who | When | What |
|---|---|---|
| **Camera** | before every roll | the card for `camera_roll` lane in use: caps, prompting rules, failure table (`model_card.py for-lane --lane preview`) |
| **DOP** | writing a shot list | capabilities (duration cap, multi-shot, on-screen text, refs) so the list is shootable |
| **Stunt & Safety** | on a block | failure table first, then `triggers.json` |
| **Line Producer** | choosing lanes; end of episode | latency/tokens rows; runs `stale` and schedules probes; **promotes** repeated observations into table rows |
| **Script Supervisor** | after a scene | `learn-from-governor` so flags and escalations land on the card |

## Feedback loop (how the cards get smarter)
```bash
MC=<plugin>/skills/model-cards/scripts/model_card.py
python3 $MC show --model omni-1.2-flash
python3 $MC learn --model omni-1.2-flash --kind works --text "2 speaking faces in one MCU held identity for 10s" --shot EP02_SC01/1B --evidence production/dailies/EP02_SC01/1B_take1_contact.png
python3 $MC learn-from-governor --scene production/dailies/EP01_SC04 --model omni-1.2-flash   # escalations + QC flags → Observations
python3 $MC stale                                                                               # cards with 📄/❓ rows or no verification in 30 days
```
Rules: observations are **appended, never edited**; promoting an observation into a capability/failure row is a deliberate edit by the Line Producer or Script Sup with the date; every ❌ needs a workaround or an open probe; every 📄 needs a probe command.

## Cards
| card | model ids | state |
|---|---|---|
| `omni-1.2-flash` | `gemini-omni-1.2-flash` (GA) | ✅ default lane; flexible 3–15 s verified |
| `omni-1.1-flash` | `gemini-omni-1.1-flash-preview` | reachable ✅, capabilities ❓ — probe listed |
| `veo-3.1` | `veo-3.1-{generate,fast-generate,lite-generate}-001` | 📄/❓ — API surface unconfirmed; adapter + probe plan listed |
| `nano-banana-2.1` | `gemini-nano-banana-2.1` | ✅ reachable on Vertex (2026-11-10); capabilities 📄 from docs; silent-refusal bisect ✅ |
| `lyria-3-pro` | `lyria-3-pro-preview` | ✅ |

When a model is renamed at GA, update the id in `camera_roll.py` CONFIG and the card header; the card's history stays.
