#!/usr/bin/env python3
"""casting_sheet.py — character identity assets via the image generator.

  casting_sheet.py front  --name rishi --desc "..." --style "..." --out-dir production/bible/characters/rishi
  casting_sheet.py sheet  --name rishi --desc "..." --style "..." --out-dir ...        # turnaround + 5 expressions
  casting_sheet.py edit   --image sheet.png --instruction "add a small pale notch through the LEFT eyebrow in every view" --out sheet_v2.png
  casting_sheet.py pair   --a a.png --b b.png --out pair.jpg                              # side-by-side for the Director

Backend: Google-internal `generate` CLI (gempix). On non-gLinux hosts set CASTING_BACKEND=vertex and
implement `_vertex_image()` for your project (Imagen / Nano Banana via Vertex), keeping the same CLI.
Silent empty outputs (exit 0, no file) are soft refusals -> run safety-staging lint on --desc.
"""
import argparse, os, shutil, subprocess, sys, time

GEN = "/google/bin/releases/gemini-agents-generate/generate"
MODEL_FAST = os.environ.get("CASTING_MODEL_FAST", "gempix-2-flash-lite-png")
MODEL_PRO = os.environ.get("CASTING_MODEL_PRO", "gempix-2")

FRONT_TMPL = ("{style}. Clean front-facing medium close-up identity portrait of {desc}. Neutral calm expression, eyes to camera, "
              "even soft lighting, plain softly blurred background, centred, head and shoulders fully in frame, consistent proportions. "
              "No text, no labels, no watermark.")
SHEET_TMPL = ("Landscape 16:9. {style}. Character design sheet of {desc}. Turnaround layout: front view, three-quarter view, side view "
              "and back view, standing, consistent proportions and even lighting, soft shadow under each figure. Below, a row of 5 expression "
              "close-ups: {expressions}. No text, no labels, no watermark.")
DEFAULT_EXPR = "neutral, happy, angry, worried, surprised"

def _gen(prompt, out, model, media=None, tries=4):
    if not os.path.exists(GEN):
        sys.exit("generate CLI not found; set CASTING_BACKEND=vertex and implement _vertex_image().")
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
            out = _gen(FRONT_TMPL.format(style=a.style, desc=a.desc), os.path.join(a.out_dir, "front.png"), a.model)
        else:
            out = _gen(SHEET_TMPL.format(style=a.style, desc=a.desc, expressions=a.expressions), os.path.join(a.out_dir, "sheet.png"), a.model)
        notes = os.path.join(a.out_dir, "notes.md")
        if not os.path.exists(notes):
            open(notes, "w").write(f"# {a.name}\n\n## Lock (quote verbatim in prompts)\n{a.desc}\n\n## Style\n{a.style}\n\n## Signature details\n- \n\n## Known model pitfalls\n- \n")
        print(out)
    elif a.cmd == "edit":
        print(_gen("Edit this image, keeping layout, style, colours and every pose exactly the same. Change only: " + a.instruction + ". No text.", a.out, a.model, media=a.image))
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
