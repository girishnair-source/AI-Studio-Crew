#!/usr/bin/env python3
"""model_card.py — living knowledge per model: what works, what doesn't, verified vs documented.

  model_card.py list
  model_card.py show --model omni-1.5-preview                       # print the card (agents read before rolling)
  model_card.py learn --model omni-1.5-preview --kind works|fails|note --text "..." [--evidence path] [--shot EP01_SC04/4A]
  model_card.py learn-from-governor --scene production/dailies/EP01_SC04 --model omni-1.5-preview   # auto-log escalations + flags
  model_card.py for-lane --lane preview                              # resolve camera_roll lane -> card
  model_card.py stale                                                # cards with 📄/❓ rows or no verification in 30 days

Observations are appended (newest first) under '## Observations log'. The Line Producer / Script Sup promote repeated
observations into the tables (that step is human/agent judgement, deliberately not automated).
"""
import argparse, datetime, glob, json, os, sys, re

def _rel(path):
    """Evidence paths are stored relative to the production folder (or cwd); never absolute machine paths."""
    if not path: return path
    for base in (os.environ.get("AGY_PRODUCTION_DIR"), "production", os.getcwd()):
        if base and os.path.abspath(path).startswith(os.path.abspath(base) + os.sep):
            return os.path.relpath(path, os.path.dirname(os.path.abspath(base)) if base != os.getcwd() else base)
    return os.path.basename(path)

HERE = os.path.dirname(os.path.abspath(__file__)); CARDS = os.path.join(HERE, "..", "cards")
LANE_TO_CARD = {"omni-1.2": "omni-1.2-flash", "omni-1.1": "omni-1.1-flash", "preview": "omni-1.2-flash", "veo-fast": "veo-3.1", "veo-quality": "veo-3.1", "veo-lite": "veo-3.1",
                "image": "nano-banana-2.1", "music": "lyria-3-pro"}
MODEL_TO_CARD = {"gemini-omni-1.2-flash": "omni-1.2-flash", "gemini-omni-1.1-flash-preview": "omni-1.1-flash", "gemini-omni-flash-preview": "omni-1.1-flash", "gemini-nano-banana-2.1": "nano-banana-2.1",
                 "veo-3.1-generate-001": "veo-3.1", "veo-3.1-fast-generate-001": "veo-3.1", "veo-3.1-lite-generate-001": "veo-3.1",
                 "gempix-2": "nano-banana-2.1", "gempix-2-flash-lite-png": "nano-banana-2.1", "lyria-3-pro-preview": "lyria-3-pro"}

def path(model): return os.path.join(CARDS, f"{model}.md")

def learn(model, kind, text, evidence=None, shot=None):
    p = path(model)
    if not os.path.exists(p): sys.exit(f"no card {model}; create cards/{model}.md first")
    s = open(p, encoding="utf-8").read()
    marker = "## Observations log"
    if marker not in s: s += f"\n\n{marker}\n"
    tag = {"works": "✅", "fails": "❌", "note": "📝"}.get(kind, "📝")
    evidence = _rel(evidence)
    line = f"- {datetime.date.today()} {tag} {text.strip()}" + (f" · shot `{shot}`" if shot else "") + (f" · evidence `{evidence}`" if evidence else "")
    head, tail = s.split(marker, 1)
    # insert after the marker and any HTML comment line
    lines = tail.split("\n"); i = 1
    while i < len(lines) and (lines[i].strip().startswith("<!--") or lines[i].strip() == ""): i += 1
    lines.insert(i, line)
    open(p, "w", encoding="utf-8").write(head + marker + "\n".join(lines)); return line

def learn_from_governor(scene_dir, model):
    n = 0
    for e in glob.glob(os.path.join(scene_dir, "escalations", "*.json")):
        esc = json.load(open(e)); n += 1
        learn(model, "fails", f"{esc['reason_code']} persisted after {esc['takes_tried']} takes ({esc.get('reason','')[:80]})", evidence=e, shot=f"{esc['scene']}/{esc['shot']}")
    qc = os.path.join(scene_dir, "qc.json")
    if os.path.exists(qc):
        for take, r in json.load(open(qc)).items():
            for f in r.get("flags", []):
                learn(model, "note", f"QC flag `{f}` (margin={r.get('margin')}, f0_std={r.get('f0_std_semitones')})", shot=take); n += 1
    ss = os.path.join(scene_dir, "scene_summary.json")
    if os.path.exists(ss):
        s = json.load(open(ss)); learn(model, "works" if not s["escalations"] else "note", f"scene {s['scene']}: {s['one_line']}", evidence=ss); n += 1
    return n

def stale(days=30):
    out = []
    for p in sorted(glob.glob(os.path.join(CARDS, "*.md"))):
        s = open(p, encoding="utf-8").read(); name = os.path.basename(p)[:-3]
        body = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith(">"))  # ignore the legend blockquote
        doc = body.count("📄"); unk = body.count("❓")
        dates = [datetime.date.fromisoformat(d) for d in re.findall(r"\b(20\d\d-\d\d-\d\d)\b", s)]
        last = max(dates) if dates else None
        age = (datetime.date.today() - last).days if last else None
        if doc or unk or age is None or age > days: out.append({"card": name, "documented_unverified": doc, "unknown": unk, "last_verified": str(last), "days": age})
    return out

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    s = sub.add_parser("show"); s.add_argument("--model", required=True)
    l = sub.add_parser("learn"); l.add_argument("--model", required=True); l.add_argument("--kind", default="note", choices=["works", "fails", "note"]); l.add_argument("--text", required=True); l.add_argument("--evidence"); l.add_argument("--shot")
    g = sub.add_parser("learn-from-governor"); g.add_argument("--scene", required=True); g.add_argument("--model", required=True)
    f = sub.add_parser("for-lane"); f.add_argument("--lane"); f.add_argument("--model-id")
    sub.add_parser("stale")
    a = ap.parse_args()
    if a.cmd == "list":
        for p in sorted(glob.glob(os.path.join(CARDS, "*.md"))): print(os.path.basename(p)[:-3])
    elif a.cmd == "show": print(open(path(a.model), encoding="utf-8").read())
    elif a.cmd == "learn": print(learn(a.model, a.kind, a.text, a.evidence, a.shot))
    elif a.cmd == "learn-from-governor": print(f"logged {learn_from_governor(a.scene, a.model)} observation(s) to {a.model}")
    elif a.cmd == "for-lane":
        card = LANE_TO_CARD.get(a.lane) or MODEL_TO_CARD.get(a.model_id)
        print(path(card) if card else "no card mapped")
    else:
        for r in stale(): print(json.dumps(r))

if __name__ == "__main__":
    main()
