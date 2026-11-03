---
name: shot-grammar
description: The DOP's prompt grammar for fast-action and dialogue scenes - timestamped shot lists, one action beat per shot, camera placement + screen direction, consistent character naming, style and audio on separate trailing lines, and the words that break multi-shot generation. Use when writing or fixing any shot list / video prompt.
---

# Shot Grammar

The generator does its best work when a scene is written like a shot list, not
a paragraph. This grammar came out of fixing real failures (single long takes,
jumbled cuts, frozen cars, invented faces).

## The template

```
<Scene headline>, <total seconds>, <N> shots with hard cuts.

Shot 1 (0-4s): <camera placement + movement>. <who, named exactly as in the bible> <one action beat>, <screen direction>. <environment detail>.
Shot 2 (4-7s): Hard cut. <camera>. <action>.
Shot 3 (7-11s): Hard cut. ...
Shot 4 (11-15s): Hard cut. ...

Style: <lighting, lens, grain, grade — one line, same for the whole scene>.
Audio: <diegetic sounds, score yes/no, dialogue notes — one line>.
```

## Rules

1. **Declare count and duration up front** ("15 seconds, four shots with hard cuts").
2. **3–5 s per shot.** Under 3 s turns to mush; over 6 s becomes a long take.
3. **One action beat per shot** and one camera idea. "Rapid zooms, kinetic camera work, anamorphic flares" in one sentence = the model guesses.
4. **Camera is concrete:** "low tracking shot inches above the road, cars pass left to right", "chase-cam locked behind the rear bumper", "whip-pan right to…". Not "dynamic".
5. **Screen direction every time** (left→right, toward camera, away). It's what makes cuts read.
6. **Name characters identically in every shot**, quoting the bible's lock phrase ("the young man in the rust-orange overshirt, dark t-shirt, blue jeans, white sneakers"). Never "he" across shots.
7. **"Hard cut."** as the literal first words of shots 2+ is the strongest multi-shot cue.
8. **Style and Audio on separate trailing lines.** Don't mix lens adjectives into action sentences.
9. **Delete contradictions and no-ops:** "high shutter speed" vs "motion blur"; "8K"/"4K" (resolution is an API param); "rapid zooms" (reads as shake).
10. **Dialogue shots:** paste the voice lock verbatim, then `He says, in <language>: "..."` with `...` for pauses and `*word*` for emphasis. Specify *who is not seen* ("the caller is never shown").
11. **Chained shots** (> clip cap): Shot block starts with `VIDEO CONTINUATION of the reference image: same room, same lighting, same lens, same character…` and binds the previous part's last frame as the first reference.
12. **Vertical (9:16):** whip-pans and wide two-shots lose subjects; prefer hard cuts and ¾ singles. Say so to the Director once.

## Worked example (approved)

```
Cinematic high-intensity night car chase, 15 seconds, four shots with hard cuts.

Shot 1 (0-4s): Low-angle tracking shot mounted inches above wet asphalt. A matte-black muscle car and a midnight-blue supercar blast past the camera left to right through a rain-soaked downtown street at dusk. Tires throw sheets of spray; neon signs streak as reflections across the wet road.
Shot 2 (4-7s): Hard cut. Chase-cam from directly behind the muscle car's rear bumper, locked on the supercar ahead as both cars slide through a tight right-hand corner into a narrow alley. The supercar's rear quarter panel scrapes a concrete barrier, sending a shower of orange sparks.
Shot 3 (7-11s): Hard cut. Interior cockpit POV from the muscle car driver's seat. Hands wrench the wheel, wipers slap away rain, the supercar's tail lights swerve ahead.
Shot 4 (11-15s): Hard cut. Wide side-profile tracking shot from a parallel street as both cars rocket across a flooded intersection, water exploding outward; camera whip-pans to follow them into the distance.

Style: gritty cinematic lighting, natural motion blur, anamorphic flares from headlights and neon, photoreal vehicle weight, action-film grade.
Audio: roaring V8, turbo whistle, tires hissing on wet asphalt, metal scraping concrete, rain.
```
