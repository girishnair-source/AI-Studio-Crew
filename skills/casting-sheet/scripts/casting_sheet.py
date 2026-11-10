#!/usr/bin/env python3
"""casting_sheet.py — character identity assets via the image generator.

  casting_sheet.py front  --name rishi --desc "..." --style "..." --out-dir production/bible/characters/rishi
  casting_sheet.py sheet  --name rishi --desc "..." --style "..." --out-dir ...        # turnaround + 5 expressions
  casting_sheet.py edit   --image sheet.png --instruction "add a small pale notch through the LEFT eyebrow in every view" --out sheet_v2.png
  casting_sheet.py pair   --a a.png --b b.png --out pair.jpg                              # side-by-side for the Director

Backend (CASTING_BACKEND): `vertex` (default) = Nano Banana 2.1 (`gemini-nano-banana-2.1`) via Vertex generateContent,
using the same auth/project as camera-roll; `internal` = Google-internal `generate` CLI (testers only).
Silent/empty outputs are soft refusals -> run safety-staging lint on --desc.
"""
import argparse, os, shutil, subprocess, sys, time

import base64, json, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "camera-roll", "scripts"))
BACKEND = os.environ.get("CASTING_BACKEND", "vertex")
NB_MODEL = os.environ.get("CASTING_MODEL", "gemini-nano-banana-2.1")
NB_LOCATION = os.environ.get("CASTING_LOCATION", "global")
GEN = "/google/bin/releases/gemini-agents-generate/generate"          # internal fallback only
MODEL_FAST = os.environ.get("CASTING_MODEL_FAST", "gempix-2-flash-lite-png")
MODEL_PRO = os.environ.get("CASTING_MODEL_PRO", "gempix-2")

def _vertex_image(prompt, out, aspect="1:1", size="1K", media=None, thinking="medium", tries=3):
    """Nano Banana 2.1 via Vertex generateContent. media: list of reference image paths (<=14). Returns out path."""
    from camera_roll import get_token, CONFIG
    proj = os.environ.get("AGY_PROJECT", CONFIG["lanes"][CONFIG["default_lane"]]["project"])
    url = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/{NB_LOCATION}/publishers/google/models/{NB_MODEL}:generateContent"
    parts = []
    for m in (media or []):
        mt = "image/png" if m.lower().endswith(".png") else "image/jpeg"
        parts.append({"inlineData": {"mimeType": mt, "data": base64.b64encode(open(m, "rb").read()).decode()}})
    parts.append({"text": prompt})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect, "imageSize": size}}}
    last = ""
    for i in range(tries):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as r: resp = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e.read().decode()[:300]
            if e.code in (429, 500, 503): time.sleep(6 + 8 * i); continue
            raise SystemExit(f"Nano Banana HTTP {e.code}: {last}")
        cand = (resp.get("candidates") or [{}])[0]
        imgs = [p_ for p_ in cand.get("content", {}).get("parts", []) if "inlineData" in p_]
        if imgs:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            open(out, "wb").write(base64.b64decode(imgs[0]["inlineData"]["data"])); return out
        last = f"no image; finishReason={cand.get('finishReason')} text={''.join(p_.get('text','') for p_ in cand.get('content',{}).get('parts',[]))[:200]}"
        if cand.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "IMAGE_SAFETY"): break
    raise SystemExit("no image produced (soft refusal or capacity): " + last + " — lint the description with safety-staging.")

FRONT_TMPL = ("{style}. Clean front-facing medium close-up identity portrait of {desc}. Neutral calm expression, eyes to camera, "
              "even soft lighting, plain softly blurred background, centred, head and shoulders fully in frame, consistent proportions. "
              "No text, no labels, no watermark.")
SHEET_TMPL = ("Landscape 16:9. {style}. Character design sheet of {desc}. Turnaround layout: front view, three-quarter view, side view "
              "and back view, standing, consistent proportions and even lighting, soft shadow under each figure. Below, a row of 5 expression "
              "close-ups: {expressions}. No text, no labels, no watermark.")
DEFAULT_EXPR = "neutral, happy, angry, worried, surprised"

def _gen(prompt, out, model, media=None, tries=4, aspect="1:1", size="1K"):
    if BACKEND == "vertex" or not os.path.exists(GEN):
        return _vertex_image(prompt, out, aspect=aspect, size=size, media=[media] if media else None)
    out = os.path.abspath(out)
    for i in range(tries):
        cmd = [GEN, "-prod", f"-output={out}", "image", f"-model={model}"]
        if media: cmd.append(f"-media-uri={os.path.abspath(media)}")
        cmd.append(prompt)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
        err = (r.stdout + r.stderr)
        if "PREEMPTED" in err or "Overloaded" in err or "unavailable" in err:
            time.sleep(6 + 6 * i); continue
        if not err.strip():
            # silent refusal: one retry on the other model, then give up
            model = MODEL_PRO if model != MODEL_PRO else MODEL_FAST
            if i >= 1: break
            continue
        print(err[-600:], file=sys.stderr); break
    raise SystemExit("no image produced (soft refusal or capacity). Lint the description with safety-staging.")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("front", "sheet"):
        s = sub.add_parser(c); s.add_argument("--name", required=True); s.add_argument("--desc", required=True)
        s.add_argument("--style", default="photoreal, 35mm, natural light"); s.add_argument("--out-dir", required=True)
        s.add_argument("--model", default=MODEL_FAST); s.add_argument("--expressions", default=DEFAULT_EXPR)
    e = sub.add_parser("edit"); e.add_argument("--image", required=True); e.add_argument("--instruction", required=True); e.add_argument("--out", required=True); e.add_argument("--model", default=MODEL_FAST)
    v = sub.add_parser("voice"); v.add_argument("--name", required=True); v.add_argument("--out-dir", required=True)
    p = sub.add_parser("pair"); p.add_argument("--a", required=True); p.add_argument("--b", required=True); p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd in ("front", "sheet"):
        os.makedirs(a.out_dir, exist_ok=True)
        if a.cmd == "front":
            out = _gen(FRONT_TMPL.format(style=a.style, desc=a.desc), os.path.join(a.out_dir, "front.png"), a.model, aspect="3:4", size="1K")
        else:
            out = _gen(SHEET_TMPL.format(style=a.style, desc=a.desc, expressions=a.expressions), os.path.join(a.out_dir, "sheet.png"), a.model, aspect="16:9", size="2K")
        notes = os.path.join(a.out_dir, "notes.md")
        if not os.path.exists(notes):
            open(notes, "w").write(f"# {a.name}\n\n## Lock (quote verbatim in prompts)\n{a.desc}\n\n## Style\n{a.style}\n\n## Signature details\n- \n\n## Known model pitfalls\n- \n")
        print(out)
    elif a.cmd == "edit":
        print(_gen("Edit this image, keeping layout, style, colours and every pose exactly the same. Change only: " + a.instruction + ". No text.", a.out, a.model, media=a.image, aspect="16:9", size="2K"))
    elif a.cmd == "voice":
        os.makedirs(a.out_dir, exist_ok=True); fp = os.path.join(a.out_dir, "fingerprint.md")
        if not os.path.exists(fp):
            open(fp, "w").write(f"""# Voice fingerprint — {a.name.upper()} (lock; quote verbatim, never paraphrase)
Sex/age/language: 
Pitch band: 
Timbre: 
Pace (default) & habits: 
Anchor phrases: 
Not: 
""")
        print(fp)
    elif a.cmd == "pair":
        from PIL import Image
        A, B = Image.open(a.a), Image.open(a.b); h = 768
        A = A.resize((int(A.width * h / A.height), h)); B = B.resize((int(B.width * h / B.height), h))
        C = Image.new("RGB", (A.width + B.width + 12, h), (20, 20, 20)); C.paste(A, (0, 0)); C.paste(B, (A.width + 12, 0)); C.save(a.out, quality=88); print(a.out)

if __name__ == "__main__":
    main()
