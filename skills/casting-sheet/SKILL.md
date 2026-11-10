---
name: casting-sheet
description: Create and lock character identity - the look (front-facing identity portrait, turnaround + expressions, wardrobe, signature details via edit pass) and the VOICE FINGERPRINT (a precise identity-only voice description quoted verbatim in every dialogue prompt so the voice does not drift between clips) - using casting_sheet.py. Use whenever a character has no bible entry, needs a look/voice change, or drifts across takes.
---

# Casting Sheet

Script: `scripts/casting_sheet.py` — **Nano Banana 2.1** (`gemini-nano-banana-2.1`) on Vertex by default (same auth/project as camera-roll; `CASTING_LOCATION=global`). Sheets render at 16:9 / 2K, identity portraits at 3:4 / 1K; up to 14 reference images per call. `CASTING_BACKEND=internal` uses the Google-internal CLI (testers only).

```bash
CS=<plugin>/skills/casting-sheet/scripts/casting_sheet.py
python3 $CS front --name rishi --desc "$DESC" --style "$STYLE" --out-dir production/bible/characters/rishi
python3 $CS sheet --name rishi --desc "$DESC" --style "$STYLE" --out-dir production/bible/characters/rishi \
        --expressions "arrogant and bored, furious and roaring, suspicious, confused staring downward, enraged"
python3 $CS edit  --image .../sheet.png --instruction "add a small pale notch through the LEFT eyebrow, visible in every view; amber eyes" --out .../sheet.png
python3 $CS pair  --a optionA/front.png --b optionB/front.png --out .scratch/pair.jpg   # show the Director two options
```

## Rules

1. **`front.png` is mandatory** for anyone who speaks or faces camera. Back-view-only references make the video model invent a face (and borrow features from other characters in frame).
2. **Lock paragraph.** `notes.md` → *Lock* is the exact sentence Camera pastes into every prompt. Write it like a costume breakdown: "Indian man early thirties, short neat black hair, trimmed beard, clear-frame glasses, charcoal crew-neck t-shirt". Update it if the look changes; never let two versions float.
3. **Signature details go in the edit pass**, not the base prompt (scars, brands, injuries trip the image filter and return *nothing*, silently). Clean sheet first, then `edit`.
4. **Style string** comes from `bible/style/look.md`; for illustrated shows include medium words ("chalky brush, soft glow, no outlines, not 3D").
5. Two options for a new lead, side by side (`pair`); one option for a wardrobe change.
6. Record pitfalls you hit in `notes.md › Known model pitfalls` so Camera and Script Sup inherit them.

## Voice fingerprint (anti-drift)

There is no voice fingerprint in production — identity has to live in words, and the same words must be used every time. Scaffold with:

```bash
python3 $CS voice --name rishi --out-dir production/bible/voices/rishi
```

Then fill `fingerprint.md`. Identity **only** — no emotion, pace or scene direction (the DOP adds those per line):

```markdown
# Voice fingerprint — RISHI (lock; quote verbatim, never paraphrase)
Male, early 20s, Indian English with Hindi as first language; mixes English nouns into Hindi naturally.
Pitch: low-mid baritone, sits around A2–C3; drops at sentence ends.
Timbre: warm and slightly husky, forward resonance, light breathiness on quiet lines.
Pace (default): medium; clips his word-endings; audible intake of breath before long lines.
Habits: soft retroflex 'r', slight sibilance on 's', swallows "hai" at the end of questions.
Anchor phrases: "Kaun ho tum?" — flat, guarded, no rise · "Theek hai." — quick, resigned.
Not: not an announcer voice, no vocal fry, not nasal, no British vowels.
```

Rules:
1. **One fingerprint per character, versioned.** If Script Sup flags drift, tighten it (add a habit, a pitch band, an anchor phrase) — never let Camera or the DOP rewrite it.
2. Casting writes the fingerprint from the brief and, if a reference performance exists, by *listening and describing* it — the description is what ships, not the audio.
3. The fingerprint always precedes the directed dialogue in the prompt. Direction varies per line; the fingerprint never does.
