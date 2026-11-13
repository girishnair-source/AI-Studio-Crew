#!/usr/bin/env python3
"""provenance.py — asset lineage (exact prompt, model, reference hashes) + character cascade + UI director notes.

Every generated image (casting_sheet.py) and video (camera_roll.py) writes:
  1. <asset_path>.meta.json  (sidecar next to the file)
  2. <production>/reports/provenance.json  (indexed by relative asset path)

Commands:
  provenance.py inspect  --asset production/dailies/EP01_SC04/4A_take1.mp4
  provenance.py impact   --character rishi [--production production]
  provenance.py cascade  --character rishi [--production production] --out reroll_manifest.json
  provenance.py add-note --production production --target EP01_SC04/4B --comment "Tighter on eyes, colder light" [--status revise]
"""
import argparse, glob, hashlib, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def sha16(path):
    if not path or not os.path.exists(path) or os.path.isdir(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _infer_production_dir(asset_path, production_dir=None):
    if production_dir:
        return production_dir
    env_p = os.environ.get("AGY_PRODUCTION_DIR")
    if env_p:
        return env_p
    ap = os.path.abspath(asset_path)
    parts = ap.split(os.sep)
    for marker in ("dailies", "bible", "cuts", "masters", "music", "sfx"):
        if marker in parts:
            idx = parts.index(marker)
            if idx > 0:
                return os.sep.join(parts[:idx])
    return "production"


def record(
    asset_path,
    kind,
    prompt,
    model="",
    lane="",
    task="",
    params=None,
    refs=(),
    characters=(),
    scene="",
    shot_id="",
    interaction_id="",
    director_notes=(),
    production_dir=None,
):
    """Write <asset>.meta.json sidecar and update <production>/reports/provenance.json."""
    abs_asset = os.path.abspath(asset_path)
    prod = _infer_production_dir(abs_asset, production_dir)
    ref_entries = []
    for r in (refs or ()):
        if not r:
            continue
        ref_entries.append({"path": r, "sha256_16": sha16(r)})

    entry = {
        "schema": "Provenance/1",
        "asset": asset_path,
        "asset_sha256_16": sha16(abs_asset),
        "kind": kind,
        "recorded_at": time.strftime("%F %T"),
        "prompt": prompt,
        "model": model,
        "lane": lane,
        "task": task,
        "params": params or {},
        "refs": ref_entries,
        "characters": [c.lower() for c in (characters or ())],
        "scene": scene,
        "shot_id": shot_id,
        "interaction_id": interaction_id,
        "director_notes": list(director_notes or ()),
    }
    try:
        with open(abs_asset + ".meta.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    try:
        idx_path = os.path.join(prod, "reports", "provenance.json")
        os.makedirs(os.path.dirname(os.path.abspath(idx_path)), exist_ok=True)
        idx = {}
        if os.path.exists(idx_path):
            with open(idx_path, encoding="utf-8") as f:
                idx = json.load(f)
        rel_key = os.path.relpath(abs_asset, os.path.abspath(prod)) if abs_asset.startswith(os.path.abspath(prod)) else abs_asset
        entry["asset_rel"] = rel_key
        idx[rel_key] = entry
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return entry


def inspect_asset(asset_path, production_dir=None):
    sidecar = os.path.abspath(asset_path) + ".meta.json"
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as f:
            return json.load(f)
    prod = _infer_production_dir(asset_path, production_dir)
    idx_path = os.path.join(prod, "reports", "provenance.json")
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        rel_key = os.path.relpath(os.path.abspath(asset_path), os.path.abspath(prod))
        if rel_key in idx:
            return idx[rel_key]
    return None


# ── Director UI Notes ───────────────────────────────────────────────────────────────────────────────────
def notes_path(production_dir="production"):
    return os.path.join(production_dir, "callsheets", "director_notes.json")


def load_notes(production_dir="production"):
    p = notes_path(production_dir)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"notes": {}}


def save_note(production_dir, target, comment="", status=None):
    data = load_notes(production_dir)
    notes = data.setdefault("notes", {})
    cur = notes.get(target, {})
    if comment is not None:
        cur["comment"] = comment.strip()
    if status is not None:
        cur["status"] = status
    cur["updated_at"] = time.strftime("%F %T")
    notes[target] = cur
    p = notes_path(production_dir)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return cur


def save_notes_bulk(production_dir, bulk_dict):
    """Merge a dict of {target: {comment, status}} from the UI into director_notes.json."""
    for target, payload in (bulk_dict or {}).items():
        if isinstance(payload, str):
            save_note(production_dir, target, comment=payload)
        elif isinstance(payload, dict):
            save_note(production_dir, target, comment=payload.get("comment", ""), status=payload.get("status"))
    return load_notes(production_dir)


def notes_for_shot(production_dir, scene, shot_id):
    """Collect active comments targeting scene, scene/shot_id, or shot_id."""
    notes = load_notes(production_dir).get("notes", {})
    found = []
    for key in (scene, f"{scene}/{shot_id}", shot_id):
        if key and key in notes and notes[key].get("comment"):
            found.append(notes[key]["comment"])
    return found


# ── Character Impact & Cascade Re-Roll ──────────────────────────────────────────────────────────────────
def _shot_uses_character(shot, char_low):
    chars = [c.lower() for c in shot.get("characters", [])]
    speakers = [d.get("speaker", "").lower() for d in shot.get("dialogue", [])]
    refs = " ".join(shot.get("refs", [])).lower()
    return char_low in chars or char_low in speakers or f"characters/{char_low}/" in refs


def impact_by_character(production_dir, character):
    """Find every scene, shot, and generated asset involving `character`, flagging stale takes if bible changed."""
    char_low = character.lower()
    bible_front = os.path.join(production_dir, "bible", "characters", char_low, "front.png")
    bible_notes = os.path.join(production_dir, "bible", "characters", char_low, "notes.md")
    cur_front_sha = sha16(bible_front)

    affected_shots = []
    for sl_path in sorted(glob.glob(os.path.join(production_dir, "callsheets", "*.shotlist.json"))):
        with open(sl_path, encoding="utf-8") as f:
            sl = json.load(f)
        scene = sl.get("scene", "")
        for s in sl.get("shots", []):
            if _shot_uses_character(s, char_low):
                affected_shots.append({"scene": scene, "shot_id": s["id"], "shotlist": sl_path})

    idx_path = os.path.join(production_dir, "reports", "provenance.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    stale_assets, current_assets = [], []
    for rel, meta in idx.items():
        if meta.get("kind") != "video":
            continue
        uses_char = char_low in [c.lower() for c in meta.get("characters", [])] or any(
            f"characters/{char_low}/" in (r.get("path") or "").lower() for r in meta.get("refs", [])
        )
        if not uses_char:
            continue
        stale_reason = None
        for r in meta.get("refs", []):
            if r.get("path") and os.path.basename(r["path"]) == "front.png" and f"/{char_low}/" in r["path"].replace("\\", "/"):
                if cur_front_sha and r.get("sha256_16") != cur_front_sha:
                    stale_reason = f"front.png changed ({r.get('sha256_16')} -> {cur_front_sha})"
        item = {"asset": rel, "scene": meta.get("scene"), "shot_id": meta.get("shot_id")}
        if stale_reason:
            item["reason"] = stale_reason
            stale_assets.append(item)
        else:
            current_assets.append(item)

    return {
        "character": char_low,
        "bible_front": bible_front if os.path.exists(bible_front) else None,
        "bible_front_sha256_16": cur_front_sha,
        "bible_notes": bible_notes if os.path.exists(bible_notes) else None,
        "scenes": sorted({x["scene"] for x in affected_shots}),
        "affected_shots": affected_shots,
        "stale_takes": stale_assets,
        "up_to_date_takes": current_assets,
    }


def cascade_character(production_dir, character, out_manifest):
    """Recompile a camera_roll batch manifest for every shot across all scenes where `character` appears."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import contracts  # noqa: E402

    char_low = character.lower()
    bible_dir = os.path.join(production_dir, "bible")
    reroll = []
    for sl_path in sorted(glob.glob(os.path.join(production_dir, "callsheets", "*.shotlist.json"))):
        with open(sl_path, encoding="utf-8") as f:
            sl = json.load(f)
        scene = sl.get("scene", "")
        matching_ids = {s["id"] for s in sl.get("shots", []) if _shot_uses_character(s, char_low)}
        if not matching_ids:
            continue
        dailies_dir = os.path.join(production_dir, "dailies", scene)
        full_man = contracts.compile_manifest(sl, bible_dir, dailies_dir, scene, production_dir=production_dir)
        for m in full_man:
            if m["id"] in matching_ids:
                reroll.append(m)
    os.makedirs(os.path.dirname(os.path.abspath(out_manifest)), exist_ok=True)
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(reroll, f, indent=2, ensure_ascii=False)
    return reroll


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ins = sub.add_parser("inspect")
    ins.add_argument("--asset", required=True)
    ins.add_argument("--production")

    imp = sub.add_parser("impact")
    imp.add_argument("--character", required=True)
    imp.add_argument("--production", default=os.environ.get("AGY_PRODUCTION_DIR", "production"))

    cas = sub.add_parser("cascade")
    cas.add_argument("--character", required=True)
    cas.add_argument("--production", default=os.environ.get("AGY_PRODUCTION_DIR", "production"))
    cas.add_argument("--out", required=True)

    nt = sub.add_parser("add-note")
    nt.add_argument("--production", default=os.environ.get("AGY_PRODUCTION_DIR", "production"))
    nt.add_argument("--target", required=True, help="e.g. EP01_SC04 or EP01_SC04/4B")
    nt.add_argument("--comment", required=True)
    nt.add_argument("--status", choices=["approved", "revise"])

    a = ap.parse_args()
    if a.cmd == "inspect":
        res = inspect_asset(a.asset, production_dir=a.production)
        if not res:
            raise SystemExit(f"No provenance record found for {a.asset}")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif a.cmd == "impact":
        print(json.dumps(impact_by_character(a.production, a.character), indent=2, ensure_ascii=False))
    elif a.cmd == "cascade":
        m = cascade_character(a.production, a.character, a.out)
        print(json.dumps({"character": a.character, "shots_queued": len(m), "manifest": a.out}, indent=2))
    elif a.cmd == "add-note":
        cur = save_note(a.production, a.target, comment=a.comment, status=a.status)
        print(json.dumps({"target": a.target, **cur}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
