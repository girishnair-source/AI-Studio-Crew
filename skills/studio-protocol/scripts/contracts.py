#!/usr/bin/env python3
"""contracts.py — typed contracts between crew members (CallSheet, ShotList, CrewReport, Escalation, SceneSummary).

Agents exchange these JSON payloads instead of prose. Every payload is validated against
skills/studio-protocol/schemas/<Name>.schema.json. Dependency-free (subset JSON-Schema validator).

  contracts.py validate --type ShotList --file production/callsheets/EP01_SC04_shotlist.json
  contracts.py validate --type CallSheet < callsheet.json
  contracts.py new --type CallSheet            # print a minimal skeleton to fill
  contracts.py summarize --type CrewReport --file report.json   # 1-line summary for the chat (URI, not payload)
  contracts.py shotlist-to-manifest --shotlist ... --bible production/bible --out shots.json  # compile camera manifest
Exit 0 valid, 1 invalid (errors on stderr as JSON lines).
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "..", "schemas")
TYPES = ["CallSheet", "ShotList", "CrewReport", "Escalation", "SceneSummary"]

def load_schema(t):
    return json.load(open(os.path.join(SCHEMA_DIR, f"{t}.schema.json")))

def _type_ok(v, t):
    return {"string": isinstance(v, str), "integer": isinstance(v, int) and not isinstance(v, bool), "number": isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": isinstance(v, bool), "object": isinstance(v, dict), "array": isinstance(v, list), "null": v is None}[t]

def validate(obj, schema, path="$", errs=None):
    errs = [] if errs is None else errs
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in {schema['enum']}"); return errs
    t = schema.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]
        if not any(_type_ok(obj, x) for x in ts):
            errs.append(f"{path}: expected {ts}, got {type(obj).__name__}"); return errs
    if isinstance(obj, str):
        if "maxLength" in schema and len(obj) > schema["maxLength"]: errs.append(f"{path}: length {len(obj)} > {schema['maxLength']} (keep it terse)")
        if "pattern" in schema and not re.search(schema["pattern"], obj): errs.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]: errs.append(f"{path}: {obj} < {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]: errs.append(f"{path}: {obj} > {schema['maximum']}")
    if isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]: errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(obj) > schema["maxItems"]: errs.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, it in enumerate(obj): validate(it, schema["items"], f"{path}[{i}]", errs)
    if isinstance(obj, dict):
        for r in schema.get("required", []):
            if r not in obj: errs.append(f"{path}: missing required '{r}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in props: errs.append(f"{path}: unexpected field '{k}'")
        for k, v in obj.items():
            if k in props: validate(v, props[k], f"{path}.{k}", errs)
    return errs

def check(obj, t):
    errs = validate(obj, load_schema(t))
    # cross-field rules
    if t == "ShotList" and not errs:
        ids = [s["id"] for s in obj["shots"]]
        if len(ids) != len(set(ids)): errs.append("$.shots: duplicate ids")
        try:
            sys.path.insert(0, HERE); import duration as dur_mod
        except Exception: dur_mod = None
        for s in obj["shots"]:
            if s.get("chain_from") and s["chain_from"] not in ids: errs.append(f"$.shots[{s['id']}].chain_from: unknown shot {s['chain_from']}")
            lines = [d["line"] for d in s.get("dialogue", [])]
            for d in s.get("dialogue", []):
                if not (d.get("intention") or "").strip(): errs.append(f"$.shots[{s['id']}]: dialogue has empty intention — DOP must direct the subtext/objective")
                if not re.search(r"\[[a-z ]+\]|\*[^*]+\*|\.\.\.", d["line"]): errs.append(f"$.shots[{s['id']}]: dialogue has no performance tags — DOP must direct the read")
            if dur_mod:
                est = dur_mod.estimate(lines, s.get("action", ""), s.get("profile", "dialogue"))
                if not est["fits"]: errs.append(f"$.shots[{s['id']}]: speech needs {est['speech_s']}s > cap — split the line (duration.py plan)")
                elif s["duration_s"] < est["duration_s"]: errs.append(f"$.shots[{s['id']}]: duration_s {s['duration_s']} < {est['duration_s']} needed by the script (speech {est['speech_s']}s + head/tail) — set from duration.py, do not guess")
    if t == "CallSheet" and not errs and obj["budget"]["max_auto_retakes"] > 2:
        errs.append("$.budget.max_auto_retakes: policy cap is 2")
    if t == "ShotList" and not errs:
        fmt = obj.get("format")
        first = obj["shots"][0]
        opener = (first.get("action", "") + " " + " ".join(d["line"] for d in first.get("dialogue", []))).lower()
        if fmt in ("shorts", "talking-head", "micro-drama", "ads", "commercial") and re.search(r"\b(hi|hello|hey|welcome|namaste|namaskar|today we|in this video|my name is)\b", opener):
            errs.append("$.shots[0]: opens on a greeting/run-up — format-craft: open on the strongest line or image")
        if fmt in ("shorts", "talking-head", "ads") and re.search(r"\blogo\b", first.get("action", "").lower()):
            errs.append("$.shots[0]: opens on a logo — format-craft: never a logo first (intro-logo is its own format)")
        for s in obj["shots"]:
            for cap in s.get("captions", []):
                dur = max(0.1, cap["to"] - cap["from"]); cps = len(cap["text"]) / dur
                if cps > 20: errs.append(f"$.shots[{s['id']}].captions: {cps:.0f} chars/sec > 20 (format-craft/captions: ceiling, shorten or hold longer)")
                if len(cap["text"].split("\n")) > 2: errs.append(f"$.shots[{s['id']}].captions: more than 2 lines")
    return errs

SKELETONS = {
 "CallSheet": {"schema": "CallSheet/1", "scene": "EP01_SC04", "title": "", "format": "micro-drama", "brief": "", "aspect": "9:16", "target_seconds": 30, "mode": "dailies",
               "scene_purpose": {"function": "dynamic_shift", "summary": ""}, "turning_point": "",
               "characters": [{"name": "rishi", "look": True, "voice": True, "speaks": True}],
               "dispatch": [{"step": 1, "agent": "script-supervisor", "deliverable": "bible-check", "output": "production/dailies/EP01_SC04/bible_check.json"}],
               "budget": {"max_auto_retakes": 2, "max_rolls": 12}, "decisions": []},
 "ShotList": {"schema": "ShotList/1", "scene": "EP01_SC04", "format": "micro-drama", "aspect": "9:16", "resolution": "720p", "style": "", "audio": "",
              "shots": [{"id": "4A", "duration_s": 6, "chain_from": None, "is_turning_point": False, "camera": "", "direction": "", "action": "", "characters": ["rishi"], "refs": ["production/bible/characters/rishi/front.png"], "profile": "dialogue",
                         "dialogue": [{"speaker": "caller", "language": "hi", "intention": "", "objective": "", "subtext": "", "line": "[slow] ... *word*"}]}]},
 "CrewReport": {"schema": "CrewReport/1", "agent": "camera", "scene": "EP01_SC04", "status": "ok", "artifacts": [], "notes": [], "requests": []},
 "Escalation": {"schema": "Escalation/1", "scene": "EP01_SC04", "shot": "4A", "takes_tried": 3, "auto_retakes_used": 2, "reason_code": "speech-clipped-at-end", "reason": "",
                "evidence": [], "options": [{"key": "A", "label": "Split the line across two shots"}, {"key": "B", "label": "Accept take 2 with a trim"}], "recommended": "A", "question": "", "resolved": None},
 "SceneSummary": {"schema": "SceneSummary/1", "scene": "EP01_SC04", "locked_takes": [], "rolls": 0, "retakes": 0, "retake_causes": {}, "escalations": [], "usable_seconds": 0, "one_line": ""},
}

def summarize(obj, t):
    if t == "CrewReport":
        n = [f"{x['ref']}: {x['note']}" for x in obj["notes"][:3]]
        return f"[{obj['agent']} · {obj['scene']}] {obj['status']} · {len(obj['artifacts'])} artifact(s)" + (" · " + " | ".join(n) if n else "")
    if t == "Escalation":
        return f"[ESCALATE · {obj['scene']}/{obj['shot']}] {obj['reason_code']} after {obj['takes_tried']} takes → " + " / ".join(f"{o['key']}) {o['label']}" for o in obj["options"]) + f" (rec: {obj['recommended']})"
    if t == "SceneSummary":
        return f"[LOCKED · {obj['scene']}] {len(obj['locked_takes'])} shots · {obj['rolls']} rolls · {obj['retakes']} retakes · {obj['one_line']}"
    if t == "ShotList":
        return f"[ShotList · {obj['scene']}] {len(obj['shots'])} shots · " + ", ".join(f"{s['id']}:{s['duration_s']}s" for s in obj["shots"])
    if t == "CallSheet":
        return f"[CallSheet · {obj['scene']}] {obj['target_seconds']}s · {len(obj['dispatch'])} steps · mode {obj['mode']}"
    return json.dumps(obj)[:200]

def compile_manifest(shotlist, bible, out_dir, scene, production_dir=None):
    """ShotList -> camera_roll batch manifest. Quotes look lock + voice fingerprint verbatim + applies UI Director notes."""
    def read(p):
        return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""
    prod = production_dir or os.path.dirname(os.path.abspath(bible.rstrip("/")))
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import provenance  # noqa: E402
    except Exception:
        provenance = None
    man = []
    for s in shotlist["shots"]:
        parts = []
        chars = list(s.get("characters", []))
        for d in s.get("dialogue", []):
            sp = d.get("speaker", "")
            if sp and sp.lower() not in [c.lower() for c in chars]:
                chars.append(sp.lower())
        for c in s.get("characters", []):
            notes = read(os.path.join(bible, "characters", c, "notes.md"))
            m = re.search(r"## Lock.*?\n(.+?)(\n##|\Z)", notes, re.S)
            if m: parts.append(f"{c.upper()} (look lock): {m.group(1).strip()}")
        for d in s.get("dialogue", []):
            fp = read(os.path.join(bible, "voices", d["speaker"], "fingerprint.md"))
            if fp: parts.append(fp)
        shot_txt = f"Shot {s['id']} ({s['duration_s']}s): {s['camera']}. {s.get('direction','')} {s['action']}".strip()
        if s.get("staging"): shot_txt += f" Staging: {s['staging']}"
        if s.get("is_turning_point"): shot_txt += " Beat: turning point of the scene — land the power shift and reaction clearly."
        eb = s.get("emotional_blocking") or {}
        if eb.get("power_dynamic"): shot_txt += f" Spatial power: {eb['power_dynamic']}."
        if eb.get("movement_motivation"): shot_txt += f" Motivation: {eb['movement_motivation']}."
        if eb.get("stillness_accent"): shot_txt += " Stillness: hold dead still to accent the emotional beat; minimal camera motion."
        for d in s.get("dialogue", []):
            seen = "" if d.get("on_screen", True) else " (the speaker is never seen)"
            obj_txt = f"\nObjective: {d['objective']}" if d.get("objective") else ""
            sub_txt = f"\nSubtext: {d['subtext']}" if d.get("subtext") else ""
            shot_txt += f"\nIntention: {d['intention']}{obj_txt}{sub_txt}\n{d['speaker'].upper()} says{seen}, in {d.get('language','the script language')}: \"{d['line']}\""
        if s.get("chain_from"):
            shot_txt = "EXACT CONTINUATION of the reference image: same room, same light, same lens, same characters. " + shot_txt
        d_notes = provenance.notes_for_shot(prod, scene, s["id"]) if provenance else []
        prompt_blocks = parts + [shot_txt, f"Style: {shotlist['style']}", f"Audio: {shotlist['audio']}"]
        if d_notes:
            prompt_blocks.append("Director notes (apply strictly): " + " | ".join(d_notes))
        prompt = "\n\n".join(prompt_blocks)
        refs = list(s.get("refs", []))
        if s.get("chain_from"):
            refs.insert(0, os.path.join(out_dir, f"{s['chain_from']}_take1_last.png"))
        man.append({"id": s["id"], "scene": scene, "characters": chars, "director_notes": d_notes, "prompt": prompt,
                    "duration": f"{s['duration_s']}s", "aspect": shotlist["aspect"], "resolution": shotlist.get("resolution", "720p"),
                    "images": refs, "out": os.path.join(out_dir, f"{s['id']}_take1.mp4"), "profile": s.get("profile", "dialogue"),
                    "chain_from": s.get("chain_from"), "stillness_accent": bool(eb.get("stillness_accent"))})
    return man

def compile_cut(shotlist, summary, out_cut_path):
    """ShotList + SceneSummary -> cut.json for assemble.py."""
    aspect = shotlist.get("aspect", "9:16")
    W, H = (1080, 1920) if aspect == "9:16" else ((1080, 1080) if aspect == "1:1" else (1920, 1080))
    by_shot = {t["shot"]: t for t in summary.get("locked_takes", [])}
    out_dir = os.path.dirname(os.path.abspath(out_cut_path))
    clips = []
    for s in shotlist["shots"]:
        t = by_shot.get(s["id"])
        if not t:
            continue
        src_rel = os.path.relpath(os.path.abspath(t["take"]), out_dir)
        clip = {"src": src_rel, "in": 0, "out": "speech" if t.get("trim_to") else s["duration_s"], "transition": s.get("transition", "cut")}
        if s.get("captions"):
            clip["captions"] = s["captions"]
        clips.append(clip)
    return {"fps": 24, "width": W, "height": H, "clips": clips}

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--type", required=True, choices=TYPES); v.add_argument("--file")
    n = sub.add_parser("new"); n.add_argument("--type", required=True, choices=TYPES)
    s = sub.add_parser("summarize"); s.add_argument("--type", required=True, choices=TYPES); s.add_argument("--file")
    c = sub.add_parser("shotlist-to-manifest"); c.add_argument("--shotlist", required=True); c.add_argument("--bible", default="production/bible"); c.add_argument("--out", required=True); c.add_argument("--dailies-dir")
    sc = sub.add_parser("shotlist-to-cut"); sc.add_argument("--shotlist", required=True); sc.add_argument("--summary", required=True); sc.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "new": print(json.dumps(SKELETONS[a.type], indent=2, ensure_ascii=False)); return
    if a.cmd == "shotlist-to-cut":
        sl = json.load(open(a.shotlist)); summ = json.load(open(a.summary))
        errs = check(sl, "ShotList")
        if errs:
            for e in errs: print(json.dumps({"error": e}), file=sys.stderr)
            sys.exit(1)
        cut = compile_cut(sl, summ, a.out)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(cut, open(a.out, "w"), indent=2, ensure_ascii=False)
        print(f"cut: {a.out} ({len(cut['clips'])} clips)"); return
    obj = json.load(open(a.file)) if getattr(a, "file", None) else (json.load(open(a.shotlist)) if a.cmd == "shotlist-to-manifest" else json.load(sys.stdin))
    t = a.type if a.cmd != "shotlist-to-manifest" else "ShotList"
    errs = check(obj, t)
    if errs:
        for e in errs: print(json.dumps({"error": e}), file=sys.stderr)
        sys.exit(1)
    if a.cmd == "validate": print(f"valid {t}: {summarize(obj, t)}")
    elif a.cmd == "summarize": print(summarize(obj, t))
    else:
        dd = a.dailies_dir or os.path.join(os.path.dirname(a.bible.rstrip('/')), "dailies", obj["scene"])
        man = compile_manifest(obj, a.bible, dd, obj["scene"]); json.dump(man, open(a.out, "w"), indent=1, ensure_ascii=False)
        try:
            sys.path.insert(0, HERE); import studio_board
            sb_out = os.path.splitext(a.shotlist)[0] + "_storyboard.html"
            studio_board.build_storyboard_board([a.shotlist], sb_out, dailies_root=dd)
            studio_board.refresh_hub(os.path.dirname(os.path.abspath(a.bible.rstrip('/'))))
        except Exception:
            pass
        print(f"manifest: {a.out} ({len(man)} shots) → dailies {dd}")

if __name__ == "__main__":
    main()
