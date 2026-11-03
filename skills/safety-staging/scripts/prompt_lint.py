#!/usr/bin/env python3
"""prompt_lint.py — check a prompt against the known safety-trigger table and suggest staging rewrites.

  prompt_lint.py --prompt "..."            # or --file prompt.txt
  prompt_lint.py --prompt "..." --json     # machine-readable
  prompt_lint.py --add '{"id":..,"pattern":..,"symptom":..,"why":..,"rewrite":..}'   # Stunt & Safety adds a solved case
Exit 0 = clean, 1 = hits found.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "..", "triggers.json")

def load():
    return json.load(open(TABLE))

def lint(text):
    hits = []
    for r in load()["rules"]:
        try:
            m = re.search(r["pattern"], text, flags=re.I | re.S)
        except re.error:
            continue
        if m:
            hits.append({"id": r["id"], "symptom": r["symptom"], "match": text[max(0, m.start()-30): m.end()+30].replace("\n", " "),
                         "why": r["why"], "rewrite": r["rewrite"], "example_after": r.get("example_after", "")})
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt"); ap.add_argument("--file"); ap.add_argument("--json", action="store_true"); ap.add_argument("--add")
    a = ap.parse_args()
    if a.add:
        t = load(); t["rules"].append(json.loads(a.add)); json.dump(t, open(TABLE, "w"), indent=2, ensure_ascii=False); print("added"); return
    text = a.prompt or (open(a.file).read() if a.file else sys.stdin.read())
    hits = lint(text)
    if a.json:
        print(json.dumps({"clean": not hits, "hits": hits}, ensure_ascii=False, indent=2))
    else:
        if not hits:
            print("clean — no known triggers"); return
        for h in hits:
            print(f"[{h['symptom'].upper():6s}] {h['id']}: …{h['match']}…\n    why: {h['why']}\n    stage it: {h['rewrite']}\n    e.g.: {h['example_after']}\n")
    sys.exit(1 if hits else 0)

if __name__ == "__main__":
    main()
