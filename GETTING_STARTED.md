# AI Studio Crew : Let's hire your crew

> **You direct. We're the crew.**

You now have a film crew that lives inside Antigravity. You don't operate any
of them. You talk to **one person i.e. the 1st AD**, the way you would on a real
set. The AD breaks down what you want, calls the right people, runs dailies,
and brings you the cut. You pick the take.

---

## 0. Install Antigravity and sign in (10 minutes, once per machine)

*A plain-English setup guide. Ten minutes, once per machine.*

Antigravity is the studio your AI crew lives in. Before the crew can work, you
need two things: the Antigravity app on your computer, and a sign-in that
connects it to your organisation's Gemini Enterprise licence.

There are two ways to sign in. Pick the one your IT team has set up:

- **Google account** — you sign in with a Google Workspace / Google Cloud
  account. Easiest; most studios.
- **Company SSO (single sign-on)** — you sign in with your corporate identity
  (Microsoft Entra ID / Okta / etc.). Your IT team will have given you a short
  configuration string for this. Larger enterprises.

---

### Before you start

- A machine running macOS, Windows or Linux where you're allowed to install apps.
- Your work account: either a Google account with Gemini Enterprise access, or
  your corporate SSO login **plus the "WIF Config" string from IT** (it looks
  like `locations/global/workforcePools/<your-pool>/providers/<your-provider>`).
- Network access to `antigravity.google`, `auth.cloud.google`, and — for SSO —
  your identity provider's sign-in domain.

---

### Step by step

1. **Download and install.** Go to [antigravity.google/download](https://antigravity.google/download),
   pick the installer for your device, install, and open the app. You'll see
   the welcome / sign-in screen.

2. **Choose how you sign in.**
   - *Google account:* select **Sign in with Google**, choose your work
     account, and skip to step 6.
   - *Company SSO:* select **Use business account**, then continue below.

3. **Enter your company's SSO configuration.** From the dropdown choose
   **Use advanced SSO config**. In the **WIF Config** field paste the string IT
   gave you — exactly, character for character, no spaces at the ends. Select
   **Sign in with SSO**.

4. **Sign in in the browser.** A browser window opens on the Google Cloud
   sign-in page. Choose your corporate account and sign in with your usual
   company credentials (and your usual second factor, if you have one).

5. **Approve the connection.** You'll see a **Continue to Antigravity
   Enterprise** screen. Check that the account and workforce pool shown are
   yours, and select **Continue**. The browser confirms
   **You have successfully authenticated**; when it asks **Open Antigravity?**,
   say yes.

6. **Pick your licence.** Back in the app, the **Select your licence** screen
   shows the Gemini Enterprise licence assigned to you (with your
   organisation's project and location). Confirm it matches what IT told you
   and select **Next**. If **no licence appears, stop here** and contact IT —
   your account hasn't been granted access yet.

7. **Accept the terms.** Review **Terms of Service & Data Use** and select
   **Finish**.

8. **You're in.** Antigravity opens to its home workspace. You can create a
   project or open a folder from the left panel, and there's an **Ask anything**
   box with a model selector.

---

### Check it worked

- Antigravity opens straight to the home workspace without asking you to sign
  in again.
- You can create a new project (or open a folder) from the left panel.
- Typing a simple question into **Ask anything** gets a reply.

---

### If sign-in fails

| Symptom | Likely cause | What to do |
|---|---|---|
| SSO page errors immediately | WIF Config mistyped | Re-paste it exactly as IT provided; no trailing spaces or line breaks |
| "No licence" at the licence step | Your account hasn't been assigned a Gemini Enterprise licence | Contact IT; don't proceed until a licence shows |
| Browser signs in, app doesn't open | Pop-up/"Open app" prompt was dismissed | Click **Open Antigravity** in the browser, or restart the app and sign in again |
| Works at the office, not at home | Network blocks one of the required domains | Ask IT to allow `antigravity.google`, `auth.cloud.google`, and your SSO domain |

> **Keep your configuration private.** The WIF Config string and licence/project
> details are specific to your organisation. Don't paste them into public places
> or reuse them elsewhere.

---

---

## 1. Hire the crew (10 minutes, once)

Think of this as the crew moving into the studio. All you need is Antigravity - Google's home grow tool that allows anyone to build in the agent-first era. Antigravity will help you to bring the crew in.

1. **Download & Install Antigravity** : https://antigravity.google/ 
   and sign in with your Google Cloud account.
2. **Open a new chat and paste this:**

   > Bring in my film crew. Clone **https://github.com/girishnair-source/AI-Studio-Crew.git**
   > into my Antigravity plugins folder as `ai-studio-crew`, enable the plugin,
   > set `AGY_PROJECT` to my Google Cloud project `<your-project-id>`, run its tech
   > check, and tell me when the 1st AD is ready to take a brief.

   Antigravity clones the repo, switches the plugin on, runs the studio's
   `doctor` (are the cameras reachable? am I signed in?) and reports back in
   plain words. If it asks you to restart, restart.
3. **Pick the 1st AD as your main agent** in the agent picker. From now on,
   every conversation starts with the AD.

That's it. You never install or configure the individual crew members. You may have to restart anti-gravity for the plugin to activate

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
| **Script Sup + Mixer** | Look at every take for continuity drift and clipped dialogue. Retakes are automatic but **capped at two per shot**; after that you get a short multiple-choice question instead of more rolls |

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

## 5a. Autopilot — hand over the whole script

You don't have to work scene by scene. Give the AD the entire script and say:

> *"Here's Episode 1. Run it on autopilot and bring me the master."*

The AD breaks the script into scenes, does pre-production once (casting,
voices), shoots every scene in order, picks the takes itself, cuts, scores,
mixes and delivers the episode — with a log of every decision it made and why.
It will only stop to ask you if a beat can't be staged within the studio's
rules, a line won't fit without changing your script, the budget cap is hit,
or a reference is missing.

**Tip:** try it on a 2–3 scene script first. A ~90-second episode takes
roughly 30–60 minutes unattended. Prefer to approve things yourself? Say
*"director's cut"* (every shot) or *"dailies"* (every scene).

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

## 6a. Guardrails you can rely on

- **No runaway retakes.** At most two automatic retakes per shot. On the third failure the crew stops and asks you a two-to-four-option question ("split the line / accept and trim / cut the clause?").
- **No chatter.** Crew talk to each other in short structured notes, not paragraphs — so the budget goes into pictures, not conversation.
- **Everything is traced.** Every hop is timed and token-counted; the Line Producer's episode report shows **tokens per usable second** of finished video, by department.

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

---
