---
name: casting-sheet
description: Create and lock character identity assets - mandatory front-facing identity portrait, full turnaround + expression sheet, wardrobe variants, and signature details added via an image edit pass - using casting_sheet.py. Use whenever a character has no bible entry or needs a look change.
---

# Casting Sheet

Script: `scripts/casting_sheet.py` (uses the internal `generate` CLI / GemPix; swap backend via `CASTING_BACKEND`).

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
