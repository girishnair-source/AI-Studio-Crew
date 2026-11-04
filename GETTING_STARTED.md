# AI Studio Crew — Getting Started (for Directors)

> **You direct. We're the crew.**

You now have a film crew that lives inside Antigravity. You don't operate any
of them. You talk to **one person — the 1st AD** — the way you would on a real
set. The AD breaks down what you want, calls the right people, runs dailies,
and brings you the cut. You pick the take.

---

## 1. Hire the crew (10 minutes, once)

Think of this as the crew moving into the studio. You don't install anything
by hand — you ask Antigravity to bring the crew in.

1. **Install Antigravity** and sign in with your Google Cloud account.
2. **Open a new chat and paste this:**

   > Bring in my film crew. Clone **https://github.com/girishnair-source/AI-Studio-Crew.git**
   > into my Antigravity plugins folder as `ai-studio-crew`, enable the plugin,
   > run its tech check, and tell me when the 1st AD is ready to take a brief.

   Antigravity clones the repo, switches the plugin on, runs the studio's
   `doctor` (are the cameras reachable? am I signed in?) and reports back in
   plain words. If it asks you to restart, restart.
3. **Pick the 1st AD as your main agent** in the agent picker. From now on,
   every conversation starts with the AD.

That's it. You never install or configure the individual crew members.

---

## 2. Start a show

Tell the AD what you're making, like a producer would:

> "Start a new production called *Like, Follow, Die or Kill*. Vertical, for
> phones. Gritty thriller, 35mm look. Here are references for the lead."
> *(drop in a few images)*

The AD will create the production folder and send **Casting** to work. Within a
few minutes you get back **two options** for your lead as side-by-side casting
sheets — a front portrait, a turnaround, five expressions. You say "option A,
but keep the glasses." Casting locks it. That look is now in the show's
**bible**, and every department reads the bible.

If anyone speaks in your show, the **Voice Director** will audition a voice
for them the first time they have a line and ask you to approve it. After
that, the voice is locked.

---

## 3. Shoot a scene

This is the whole product. You brief in your own words:

> "Episode 1, scene 4 — Rishi gets the call. Dark bedroom, late night. The
> caller is never seen. Keep it under 30 seconds. Dialogue is in the script
> I pasted. Bring me dailies."

What happens behind the door (you don't have to watch):

| Who | What they do |
|---|---|
| **1st AD** | Writes the call sheet, decides who's needed |
| **Script Supervisor** | Checks the bible — is Rishi's look locked? Front-facing reference ready? |
| **Voice Director** | Splits the dialogue to fit the camera's clip length, marks the pauses |
| **DOP** | Writes the shot list — camera, movement, how many shots, where the cuts are. Will tell you if something won't read in vertical |
| **Stunt & Safety** | Checks every shot against the studio's rules and quietly restages anything that would get refused (e.g. "on the ledge" becomes "at the parapet, drop in frame") |
| **Camera** | Rolls all the shots in parallel |
| **Script Sup + Mixer** | Look at every take for continuity drift and clipped dialogue; send retakes back to Camera themselves |

Then the AD comes back to you with **dailies**: a contact sheet per take (a
strip of frames you can see in chat), a one-line note per take, and a question:

> "Dailies ready. 4A: two takes — A2 has the better reaction but the shirt
> drifted darker, Script Sup flagged it, I re-shot it as A3. 4B: one take,
> clean. Recommend A3 + B. Pick a take?"

You answer like a director: *"A3 and B. Tighter on the phone reveal."*

---

## 4. Finish the scene

Once you've picked takes:

- **Editor** cuts it, trims to the dialogue, adds any on-screen text you asked
  for (titles, lower-thirds) and gives you a v1.
- **Sound** lays in whooshes, hits, room tone. **Composer** writes a cue if
  you asked for score (and never puts music under dialogue unless you say so).
- **Colorist** matches the shots. **Mixer** balances dialogue, music, effects
  and makes it loud enough for phones but not louder.
- **Post** delivers the master file(s), captions, and a timeline you can open
  in Resolve or Premiere if you want to keep cutting by hand.

You get: the cut, the master, and a short delivery note. Every version is
kept; nothing is overwritten.

---

## 5. How to talk to the crew

- **Talk to the AD** in normal language. Scene, mood, length, what matters.
- **You can call anyone by name** when you want to: *"Get me the colorist — the
  bedroom's too warm."* They answer you directly and tell the AD afterwards.
- **Choose how much you want to approve** by telling the AD once:
  - *"Director's cut"* — show me every shot before you move on.
  - *"Dailies"* (default) — shoot the whole scene, then show me.
  - *"Second unit"* — just bring me the finished scene.
- **The crew has opinions.** The DOP will push back on a whip-pan in vertical;
  the Mixer will refuse to fade over a clipped word and ask for a retake.
  You always get the final say — say "do it anyway" and they do.
- **You'll only be interrupted for creative or money questions.** Which take,
  what tone, over budget. Anything technical — a refused shot, a slow server,
  a sign-in problem — the crew handles and tells you afterwards.

---

## 6. Things that will happen (and what they mean)

| You see | It means | What to do |
|---|---|---|
| "Stunt & Safety restaged shot 3" | The original staging would have been refused by the studio's content rules. The beat is kept, the staging changed. | Nothing, unless you dislike the new staging — say so. |
| "Camera is queued — the lot is busy" | The video service is overloaded right now. The Line Producer has switched lanes or is retrying. | Wait, or ask for drafts at lower quality. |
| "Two takes, both with a clipped last word" | The line was slightly too long for one clip. | The Voice Director will shorten or split it; approve the new split. |
| "Please sign in to your Google account" | Your session expired. | Do the sign-in the AD describes; say "go again". |
| "Face drifted between takes" | A character was shot without a front-facing reference. | Let Casting make the front portrait (one minute), then re-shoot. |

---

## 7. Where your work is

Everything for a show is in one folder called `production/`:

```
bible/        your cast, voices and look — the show's memory
callsheets/   what the AD planned, and the decision log
dailies/      every take, with contact sheets and notes
cuts/         every version of every cut (+ timelines for Resolve/Premiere)
music/ sfx/   cues and effects
masters/      finished files
reports/      what it cost, what was re-shot and why
```

Copy that folder and you have copied the show — cast, voices, look and all.
Next episode, the crew already knows your characters.

---

## 8. Your first ten minutes — a script

1. "1st AD, run a tech check."
2. "Start a new production called **[title]**, vertical, **[mood]**. Here's my lead." *(images)*
3. Pick a casting option.
4. "Episode 1, scene 1 — **[one paragraph of what happens]**. Under **[N]** seconds. Bring me dailies."
5. Pick takes.
6. "Finish it. Deliver a master for phones."

Welcome to the lot.
