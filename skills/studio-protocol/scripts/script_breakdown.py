#!/usr/bin/env python3
"""script_breakdown.py — split a full script into scenes and draft per-scene call sheets.

  script_breakdown.py --script script.txt --episode EP01 --dir production [--dry-run]

Accepts Fountain-style sluglines (INT./EXT.), "Scene N" / "SCENE N" headers, or markdown "## " headers.
Writes production/callsheets/EP01_SCxx.md drafts + production/callsheets/EP01_breakdown.json for the 1st AD.
Also extracts CHARACTER NAMES (ALL-CAPS cue lines) and dialogue word counts per scene so Voice Director can budget clips.
"""
import argparse, json, os, re

SLUG = re.compile(r'^\s*(?:(?:INT|EXT|INT\./EXT|I/E)\.?\s.+|(?:SCENE|Scene)\s+\d+.*|##\s+.+)$')
CUE = re.compile(r'^\s*([A-Z][A-Z0-9 .\'\-]{1,30})(\s*\(.*\))?\s*$')

def split_scenes(text):
    lines = text.splitlines(); scenes = []; cur = None
    for ln in lines:
        if SLUG.match(ln):
            if cur: scenes.append(cur)
            cur = {"heading": ln.strip().lstrip('#').strip(), "lines": []}
        elif cur is not None:
            cur["lines"].append(ln)
        else:
            cur = {"heading": "Scene 1", "lines": [ln]}
    if cur: scenes.append(cur)
    return scenes

def analyse(scene):
    chars, dialogue_words, speaker = {}, 0, None
    for ln in scene["lines"]:
        m = CUE.match(ln)
        if m and len(ln.strip()) < 35 and not ln.strip().endswith('.'):
            speaker = m.group(1).strip(); chars.setdefault(speaker, 0); continue
        if speaker and ln.strip():
            w = len(ln.split()); chars[speaker] += w; dialogue_words += w
        elif not ln.strip():
            speaker = None
    body = "\n".join(scene["lines"]).strip()
    est = max(5, round(dialogue_words / 2.6 + 6))  # speech + ~6s of visual beats
    return {"characters": chars, "dialogue_words": dialogue_words, "estimated_seconds": est, "estimated_clips": max(1, -(-est // 15)), "body": body}

TEMPLATE = """# {ep} {sc} — {heading}
Brief: (from script, see below)
Format: {aspect} · est. {est}s (~{clips} clips) · mode: {mode}

## Script
{body}

## Scene Purpose (plot / character / dynamic shift)
- Function:
- Summary:

## Turning Point (exact beat where power shifts or objective changes)
- Beat:

## Needs
- Characters: {chars}
- Departments: (1st AD fills in)

## Dispatch order
(1st AD fills in)

## Decision Log
"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--script", required=True); ap.add_argument("--episode", default="EP01"); ap.add_argument("--dir", default="production"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    show = json.load(open(os.path.join(a.dir, "show.json"))) if os.path.exists(os.path.join(a.dir, "show.json")) else {}
    scenes = split_scenes(open(a.script, encoding="utf-8").read())
    out = []
    for i, s in enumerate(scenes, 1):
        info = analyse(s); sc = f"SC{i:02d}"
        chars = ", ".join(f"{c} ({w} words)" for c, w in info["characters"].items()) or "—"
        out.append({"scene": sc, "heading": s["heading"], **{k: v for k, v in info.items() if k != "body"}})
        if not a.dry_run:
            os.makedirs(os.path.join(a.dir, "callsheets"), exist_ok=True)
            p = os.path.join(a.dir, "callsheets", f"{a.episode}_{sc}.md")
            if not os.path.exists(p):
                open(p, "w", encoding="utf-8").write(TEMPLATE.format(ep=a.episode, sc=sc, heading=s["heading"], aspect=show.get("aspect", "9:16"), est=info["estimated_seconds"], clips=info["estimated_clips"], mode=show.get("control_mode", "dailies"), body=info["body"], chars=chars))
    if not a.dry_run:
        bd_path = os.path.join(a.dir, "callsheets", f"{a.episode}_breakdown.json")
        json.dump({"episode": a.episode, "scenes": out, "total_estimated_seconds": sum(x["estimated_seconds"] for x in out)}, open(bd_path, "w"), indent=2, ensure_ascii=False)
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import studio_board
            studio_board.build_script_board(bd_path, out_html=os.path.join(a.dir, "callsheets", f"{a.episode}_script_board.html"))
            studio_board.build_screenplay_board(a.script, out_html=os.path.join(a.dir, "callsheets", f"{a.episode}_screenplay.html"))
        except Exception:
            pass
    for x in out: print(f"{x['scene']}  {x['heading'][:48]:48s} ~{x['estimated_seconds']:3d}s  clips={x['estimated_clips']}  cast={list(x['characters'])}")
    print(f"total ~{sum(x['estimated_seconds'] for x in out)}s across {len(out)} scenes")

if __name__ == "__main__":
    main()
