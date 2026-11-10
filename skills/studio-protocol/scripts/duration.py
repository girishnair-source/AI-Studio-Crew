#!/usr/bin/env python3
"""duration.py — decide clip durations from the script, never from a hard-coded number.

  duration.py estimate --line "..." [--rate 1.0] [--profile dialogue|presenter|narration|cold] [--beats N] [--cap 15] [--min 3]
  duration.py plan --shotlist callsheets/EP01_SC04.shotlist.json [--write]   # fill/validate duration_s per shot; split lines that don't fit

Model (tunable in CONFIG):
  speech_seconds = words / wps(profile) * (1/rate) + pauses*pause_s + tags*tag_s
  visual_seconds = beats * beat_s                       # non-dialogue action beats (one per 'action' sentence)
  duration       = ceil(max(speech + head + tail, visual + head + tail))  bounded to [min_s, cap_s]
If speech alone needs more than cap - head - tail, the line must be SPLIT (returned as parts at natural pauses), not rushed.
"""
import argparse, json, math, re, sys, os

CONFIG = {
    "wps": {"dialogue": 2.4, "presenter": 2.6, "narration": 2.2, "cold": 2.0},   # words per second at rate 1.0 (Hindi/English mix measured ~2.4–2.6)
    "pause_s": 0.45,      # each '...'
    "tag_s": 0.25,        # each [pause]/[beat]; other tags 0
    "beat_s": 3.5,        # seconds per visual action beat (sentence in 'action') when no dialogue
    "head_s": 0.5,        # silence before first word
    "tail_s": 0.9,        # hold after last word (>= dailies-qc margin 0.4 + reaction)
    "min_s": 3, "cap_s": 15, "step_s": 1,
}
PAUSE_TAGS = ("[pause]", "[beat]", "[breath]")

def words_of(line):
    clean = re.sub(r"\[[^\]]*\]", " ", line)           # drop tags
    clean = clean.replace("...", " ").replace("*", "")
    return [w for w in re.split(r"\s+", clean.strip()) if w and not re.fullmatch(r"[^\w\u0900-\u097F]+", w)]

def speech_seconds(line, profile="dialogue", rate=1.0):
    n = len(words_of(line)); wps = CONFIG["wps"].get(profile, 2.4) * rate
    pauses = line.count("..."); tags = sum(line.lower().count(t) for t in PAUSE_TAGS)
    return n / wps + pauses * CONFIG["pause_s"] + tags * CONFIG["tag_s"], n

def estimate(lines=(), action="", profile="dialogue", rate=1.0, beats=None, cap=None, min_s=None):
    cap = cap or CONFIG["cap_s"]; min_s = min_s or CONFIG["min_s"]
    sp = sum(speech_seconds(l, profile, rate)[0] for l in lines)
    if beats is None:
        beats = max(1, len([s for s in re.split(r"[.!?]+", action) if s.strip()])) if action else 0
    vis = beats * CONFIG["beat_s"]
    need = max(sp, vis if not lines else 0) + CONFIG["head_s"] + CONFIG["tail_s"]
    if lines and vis > sp: need = max(need, min(vis, cap) )  # dialogue scenes still need their visual beats but speech dominates
    d = int(math.ceil(need / CONFIG["step_s"]) * CONFIG["step_s"])
    fits = sp + CONFIG["head_s"] + CONFIG["tail_s"] <= cap
    return {"speech_s": round(sp, 2), "visual_s": round(vis, 2), "need_s": round(need, 2), "duration_s": max(min_s, min(cap, d)), "fits": fits, "words": sum(len(words_of(l)) for l in lines)}

def split_line(line, profile="dialogue", rate=1.0, cap=None):
    """Split a long line at natural pauses ('...', sentence ends, [pause]) into parts that each fit in one clip."""
    cap = cap or CONFIG["cap_s"]; budget = cap - CONFIG["head_s"] - CONFIG["tail_s"]
    units = re.split(r"(?<=[।.!?])\s+|(?<=\.\.\.)\s+|(?<=\[pause\])\s+|(?<=\[beat\])\s+", line.strip())
    parts, cur = [], ""
    for u in units:
        cand = (cur + " " + u).strip()
        if cur and speech_seconds(cand, profile, rate)[0] > budget:
            parts.append(cur); cur = u
        else:
            cur = cand
    if cur: parts.append(cur)
    return parts

def plan(shotlist, write=False):
    out = []; changed = False; new_shots = []
    for s in shotlist["shots"]:
        prof = s.get("profile", "dialogue"); lines = [d["line"] for d in s.get("dialogue", [])]
        est = estimate(lines, s.get("action", ""), prof, cap=CONFIG["cap_s"])
        if est["fits"]:
            if s.get("duration_s") != est["duration_s"]:
                out.append(f"{s['id']}: duration {s.get('duration_s')} → {est['duration_s']}s (speech {est['speech_s']}s, {est['words']} words)"); s["duration_s"] = est["duration_s"]; changed = True
            new_shots.append(s)
        else:
            # split the (single) dialogue line into chained parts
            d = s["dialogue"][0]; parts = split_line(d["line"], prof)
            out.append(f"{s['id']}: {est['words']} words need {est['speech_s']}s > cap → split into {len(parts)} chained shots")
            prev = s.get("chain_from")
            for i, ptxt in enumerate(parts):
                ns = dict(s); ns["id"] = f"{s['id']}{chr(97+i)}" if len(parts) > 1 else s["id"]; ns["chain_from"] = prev
                ns["dialogue"] = [dict(d, line=ptxt)]; ns["duration_s"] = estimate([ptxt], "", prof)["duration_s"]
                new_shots.append(ns); prev = ns["id"]; changed = True
    shotlist["shots"] = new_shots
    return out, changed

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("estimate"); e.add_argument("--line", action="append", default=[]); e.add_argument("--action", default=""); e.add_argument("--profile", default="dialogue"); e.add_argument("--rate", type=float, default=1.0); e.add_argument("--beats", type=int); e.add_argument("--cap", type=int); e.add_argument("--min", type=int)
    p = sub.add_parser("plan"); p.add_argument("--shotlist", required=True); p.add_argument("--write", action="store_true"); p.add_argument("--cap", type=int)
    a = ap.parse_args()
    if a.cap: CONFIG["cap_s"] = a.cap
    if a.cmd == "estimate":
        r = estimate(a.line, a.action, a.profile, a.rate, a.beats, a.cap, a.min)
        if not r["fits"]: r["split"] = split_line(" ".join(a.line), a.profile, a.rate, a.cap)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        sl = json.load(open(a.shotlist)); notes, changed = plan(sl)
        for n in notes: print(n)
        if a.write and changed: json.dump(sl, open(a.shotlist, "w"), indent=2, ensure_ascii=False); print("written")
        elif not notes: print("all durations already fit the script")

if __name__ == "__main__":
    main()
