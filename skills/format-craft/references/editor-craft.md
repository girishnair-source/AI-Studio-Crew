<!-- Adapted from invideoio/skills (Apache-2.0): invideo-timeline/{SKILL.md,references/keyframes.md,audio.md,color-and-effects.md}, invideo-media/references/voice-music.md, invideo-pipeline/references/collaborate.md. Editor-API specifics removed; craft kept; re-addressed to the AI Studio Crew's Editor, Colorist, Mixer, Sound and Composer. -->

# Editor craft (cuts, motion, sound, grade, notes)

## The locality test
Move one reveal, keep everything else. Every edit touches only what it must; if a small change moved anything else, the edit was wrong. In this studio that means: a v2 cut sheet changes only the clips it names, and `assemble.py` re-renders only those (render cache). Before you send a change, say what should change; after, look at that moment and its neighbours.

## Transitions are sentences
Cut by default. Anything else says something: a **dissolve** says time passed, a **fade to black** says it ended, a **match cut** says these two are connected. A stylised transition works only as a repeated motif built into the shot (a whip, an object wipe, a match on action), never a pack between unrelated clips. If a cut would do, cut. Often the best transition is sound arriving early (J-cut).

## Motion
- **Easing.** Ease out on entrances, ease in on exits, exits shorter. Linear only for crawls and tickers. Functional moves take 3–12 frames. The most frequent animation is the quietest; only the one title that earns it gets to be slow.
- **Overlap.** Elements of one group start a few frames apart so they move as one gesture, not a queue.
- **Settle.** Every move lands and rests. Nothing drifts under words being read.
- **Scale.** A push-in is slow, eased, and ends on the thing it points at. A punch-in lands on the word that matters, never mid-sentence.
- **Speed.** A ramp exists to show one frame: slow into the impact, release just after; land it on a sound hit. If everything ramps, nothing does.

## Sound
- **Mix.** Voice first and steady; everything else around it. Place effects *between* lines rather than ducking hard. Keep dynamics — platforms turn loud mixes down, so a crushed mix only sounds flatter. Judge it on a phone speaker.
- **Voice chain** (gentle, in order): EQ (high-pass ~80 Hz, presence) → de-esser → light compressor. Treat the layer, not each clip.
- **Ducking.** Side-chain the music to the voice; slow release so music swells back between lines instead of pumping.
- **Loudness.** ~1 dB peak headroom: limiter at −1 dBTP. ~−14 LUFS integrated for social/streaming; −24 LKFS (US) / −23 LUFS (EU) for broadcast.
- **Music in/out.** Start music at a *turn*, not the top of a scene, and on a decision, not a slow fade. Under a voice, fade up so the *middle* of the fade lands on the first word. Pull music out just before the line that matters. After a big line let music play alone 4–7 s with a change in it. Never end cold under speech. In comedy, music after the punchline.
- **Music choice.** Know why it's there; if you can't say, leave it out. Under a voice: texture and pulse, no lyrics, no busy melody. On a sad scene, music a little less sad than the picture. Bring a theme back at the end rather than a new track.
- **Effects.** Few and specific. One chosen detail beats six layers of ambience. No library clichés: a beep on every keypress, a whoosh on every cut. Silence is room tone, never dead air, and it lands *after* a sound.
- **Dubbing.** Adapt, don't translate. Performance over perfect lips; sync matters most on close-ups and on p/b/m. Match the room.

## Grade
Name the feeling in three words before touching anything. Then: **balance → match → one look over the whole piece → shape.** Contrast before colour: most colour problems are contrast. Grade **one hero shot per scene and match every shot to it**, not to its neighbour: black point, white point, face brightness first, then balance; judge it playing across the cut. Faces are the anchor — viewers forgive a wall changing, never a face. A LUT goes on after balancing, under full strength, never stacked. Teal-and-orange and faded matte blacks are reflexes, not choices. Grain is felt, not seen. Check on a phone at mid brightness; crushed shadows vanish there.

## Notes and disagreement
- A note names a real problem; the fix it suggests is a guess. "It feels slow" usually means confusing, or a weak setup earlier — ask where it *started* to feel slow. A precise note ("trim the air here") you just do.
- When a note seems wrong, do it properly first, then put your alternative beside it as a separate version and let the Director watch both. Argue for the viewer ("viewers lose the thread here"), not for your cut. Push once, then let go. When you were wrong, say so.
- Handoffs: leave the next department a short note — what you did, why, what is open, where to look. The why matters more than the what.
- Never overwrite the version someone gave notes on. Every cut is `_vN`; alternatives are their own version.

## Before you say done
Look and listen like the viewer will: first and last frames (a flash, a cut-off fade, a stray frame of the next clip); every cut point and the frames either side; every word clear on a phone speaker, nothing clipped, no music swallowing a line; every name, number and URL on screen read once more, letter by letter.
