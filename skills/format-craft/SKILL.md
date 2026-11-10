---
name: format-craft
description: Editorial craft rules per video format - how a short, commercial, explainer, micro-drama, news bulletin, talking-head, launch, product video, interview cut, intro/logo, captions etc. is actually made well (hook, selection, cuts, captions, sound, frame, ending, per-type focus). The 1st AD picks ONE format per CallSheet; the DOP, Editor, Mixer, Sound, Casting and Script Sup each read that format's reference before working. Adapted from invideoio/skills (Apache-2.0) plus studio-native formats.
---

# Format Craft

The crew's tools make clips. These references make them *good*. Each file is 2–3 KB of hard-won editorial rules for one format, structured the same way: **Start from a brief → What makes it work → Craft (hook, selection, cuts, captions, sound, frame, ending) → By type → Rules**.

## How the crew uses it

1. **1st AD** sets `format` in the `CallSheet/1` (schema enum below) at breakdown. If the brief doesn't say, ask once; default by platform (9:16 short-form → `shorts`; episodic → `micro-drama`; anchor-led → `news-bulletin`; one presenter → `talking-head`).
2. **Every dispatched crew member reads `references/<format>.md` first** and applies its section:
   - **DOP** → Hook, Frame, Pace/Cuts, Voice/Dialogue direction, By type.
   - **Editor** → Selection, Cuts, Captions, Ending; plus `captions.md` whenever captions are on.
   - **Mixer / Sound / Composer** → Sound.
   - **Casting / Script Sup** → Character / consistency rules.
   - **Post** → `ad-platform-specs.md` for deliverables; `check-your-video.md` before delivery.
   - **Line Producer** → `cost-rule.md` (price first, say it, cap it, once only, report it).
3. **Validators encode the few rules that can be checked** (`contracts.py`): shorts/talking-head/micro-drama first shot must not open on a greeting or a logo; dialogue word budget; captions ≤ 20 chars/sec when provided.

## Formats

| `format` | reference | native to |
|---|---|---|
| `shorts` | `references/shorts.md` | invideo |
| `micro-drama` | `references/micro-drama.md` | **studio** |
| `news-bulletin` | `references/news-bulletin.md` | **studio** |
| `talking-head` | `references/talking-head.md` | **studio** |
| `commercial` | `references/commercial.md` | invideo |
| `ads` | `references/ads.md` | invideo |
| `explainer` | `references/explainer.md` | invideo |
| `launch-video` | `references/launch-video.md` | invideo |
| `product-video` | `references/product-video.md` | invideo |
| `short-film` | `references/short-film.md` | invideo |
| `interview-cut` | `references/interview-cut.md` | invideo |
| `review-cut` | `references/review-cut.md` | invideo |
| `personal-video` | `references/personal-video.md` | invideo |
| `invitations` | `references/invitations.md` | invideo |
| `intro-logo` | `references/intro-logo.md` | invideo |
| `text-animation` | `references/text-animation.md` | invideo |
| `occasion-slideshow` | `references/occasion-slideshow.md` | invideo |

Cross-cutting: `captions.md`, `check-your-video.md`, `cost-rule.md`, `ad-platform-specs.md`.

## Ten rules that apply to every format (lifted from the references because we kept breaking them)

1. Open on the strongest line or image. Never a greeting, a logo, or the run-up.
2. A whoosh on every cut is hiding weak cuts.
3. Music low enough to hear every consonant, and out at the emotional peak.
4. Never put the narration's sentence on screen; the screen shows the thing, 2–3 words at most.
5. Fix character drift with a better reference, never more adjectives.
6. The read that believes the words beats the polished one. Flat is a retake.
7. Cut to the speed of comprehension, not faster. Keep the pause before an admission.
8. Each cutdown length is a new film, never the long one on fast-forward.
9. When the payoff lands, it's over. CTA goes before the payoff.
10. Read every name, number and URL on screen once more, letter by letter.

## Attribution
`references/*.md` marked "Adapted from invideoio/skills" are derived from https://github.com/invideoio/skills (Apache License 2.0; see `LICENSE-invideo-skills.txt`), re-addressed to this crew with invideo tool commands removed. `micro-drama.md`, `news-bulletin.md`, `talking-head.md` are original.
