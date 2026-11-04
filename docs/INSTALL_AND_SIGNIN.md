# Installing Antigravity and signing in with your company account

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

## Before you start

- A machine running macOS, Windows or Linux where you're allowed to install apps.
- Your work account: either a Google account with Gemini Enterprise access, or
  your corporate SSO login **plus the "WIF Config" string from IT** (it looks
  like `locations/global/workforcePools/<your-pool>/providers/<your-provider>`).
- Network access to `antigravity.google`, `auth.cloud.google`, and — for SSO —
  your identity provider's sign-in domain.

---

## Step by step

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

## Check it worked

- Antigravity opens straight to the home workspace without asking you to sign
  in again.
- You can create a new project (or open a folder) from the left panel.
- Typing a simple question into **Ask anything** gets a reply.

---

## If sign-in fails

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

## Next: hire your crew

Once you're signed in, open a new chat and paste the one-line prompt from the
[README](README.md#1-hire-the-crew-10-minutes-once) — Antigravity will bring
the crew in and the 1st AD will introduce themselves.
