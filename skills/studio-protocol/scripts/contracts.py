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
        for s in obj["shots"]:
            if s.get("chain_from") and s["chain_from"] not in ids: errs.append(f"$.shots[{s['id']}].chain_from: unknown shot {s['chain_from']}")
            for d in s.get("dialogue", []):
                words = len(re.sub(r"\[[^\]]*\]", "", d["line"]).split())
                if words > 2 * s["duration_s"]: errs.append(f"$.shots[{s['id']}]: {words} words for {s['duration_s']}s (max {2*s['duration_s']}; split the line)")
                if not re.search(r"\[[a-z ]+\]|\*[^*]+\*|\.\.\.", d["line"]): errs.append(f"$.shots[{s['id']}]: dialogue has no performance tags — DOP must direct the read")
    if t == "CallSheet" and not errs and obj["budget"]["max_auto_retakes"] > 2:
        errs.append("$.budget.max_auto_retakes: policy cap is 2")
    return errs

SKELETONS = {
 "CallSheet": {"schema": "CallSheet/1", "scene": "EP01_SC04", "title": "", "brief": "", "aspect": "9:16", "target_seconds": 30, "mode": "dailies",
               "characters": [{"name": "rishi", "look": True, "voice": True, "speaks": True}],
               "dispatch": [{"step": 1, "agent": "script-supervisor", "deliverable": "bible-check", "output": "production/dailies/EP01_SC04/bible_check.json"}],
               "budget": {"max_auto_retakes": 2, "max_rolls": 12}, "decisions": []},
 "ShotList": {"schema": "ShotList/1", "scene": "EP01_SC04", "aspect": "9:16", "resolution": "720p", "style": "", "audio": "",
              "shots": [{"id": "4A", "duration_s": 15, "chain_from": None, "camera": "", "direction": "", "action": "", "characters": ["rishi"], "refs": ["production/bible/characters/rishi/front.png"], "profile": "dialogue",
                         "dialogue": [{"speaker": "caller", "language": "hi", "intention": "", "line": "[slow] ... *word*"}]}]},
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

def compile_manifest(shotlist, bible, out_dir, scene):
    """ShotList -> camera_roll batch manifest. Quotes look lock + voice fingerprint verbatim; never paraphrases."""
    def read(p):
        return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""
    man = []
    for s in shotlist["shots"]:
        parts = []
        for c in s.get("characters", []):
            notes = read(os.path.join(bible, "characters", c, "notes.md"))
            m = re.search(r"## Lock.*?\n(.+?)(\n##|\Z)", notes, re.S)
            if m: parts.append(f"{c.upper()} (look lock): {m.group(1).strip()}")
        for d in s.get("dialogue", []):
            fp = read(os.path.join(bible, "voices", d["speaker"], "fingerprint.md"))
            if fp: parts.append(fp)
        shot_txt = f"Shot {s['id']} ({s['duration_s']}s): {s['camera']}. {s.get('direction','')} {s['action']}".strip()
        if s.get("staging"): shot_txt += f" Staging: {s['staging']}"
        for d in s.get("dialogue", []):
            seen = "" if d.get("on_screen", True) else " (the speaker is never seen)"
            shot_txt += f"\nIntention: {d['intention']}\n{d['speaker'].upper()} says{seen}, in {d.get('language','the script language')}: \"{d['line']}\""
        if s.get("chain_from"):
            shot_txt = "EXACT CONTINUATION of the reference image: same room, same light, same lens, same characters. " + shot_txt
        prompt = "\n\n".join(parts + [shot_txt, f"Style: {shotlist['style']}", f"Audio: {shotlist['audio']}"])
        refs = list(s.get("refs", []))
        if s.get("chain_from"):
            refs.insert(0, os.path.join(out_dir, f"{s['chain_from']}_take1_last.png"))
        man.append({"id": s["id"], "prompt": prompt, "duration": f"{s['duration_s']}s", "aspect": shotlist["aspect"], "resolution": shotlist.get("resolution", "720p"),
                    "images": refs, "out": os.path.join(out_dir, f"{s['id']}_take1.mp4"), "profile": s.get("profile", "dialogue"), "chain_from": s.get("chain_from")})
    return man

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--type", required=True, choices=TYPES); v.add_argument("--file")
    n = sub.add_parser("new"); n.add_argument("--type", required=True, choices=TYPES)
    s = sub.add_parser("summarize"); s.add_argument("--type", required=True, choices=TYPES); s.add_argument("--file")
    c = sub.add_parser("shotlist-to-manifest"); c.add_argument("--shotlist", required=True); c.add_argument("--bible", default="production/bible"); c.add_argument("--out", required=True); c.add_argument("--dailies-dir")
    a = ap.parse_args()
    if a.cmd == "new": print(json.dumps(SKELETONS[a.type], indent=2, ensure_ascii=False)); return
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
        print(f"manifest: {a.out} ({len(man)} shots) → dailies {dd}")

if __name__ == "__main__":
    main()
