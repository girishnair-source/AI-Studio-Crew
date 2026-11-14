#!/usr/bin/env python3
"""Create a new production folder with show.json."""
import argparse, json, os, re

TREE = ["bible/characters", "bible/voices", "bible/style", "callsheets", "dailies", "cuts",
        "sfx", "music", "masters", "reports", ".scratch"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="production")
    p.add_argument("--title", required=True)
    p.add_argument("--aspect", default="9:16", choices=["9:16", "16:9"])
    p.add_argument("--style", default="")
    p.add_argument("--mode", default="dailies", choices=["directors-cut", "dailies", "second-unit"])
    a = p.parse_args()
    for t in TREE:
        os.makedirs(os.path.join(a.dir, t), exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "", a.title.lower())[:12] or "show"
    show = {
        "title": a.title, "slug": slug, "aspect": a.aspect,
        "resolution_draft": "720p", "resolution_final": "1080p",
        "style": a.style, "control_mode": a.mode, "loudness_lufs": -14, "episodes": {},
    }
    path = os.path.join(a.dir, "show.json")
    if os.path.exists(path):
        print(f"exists: {path} (not overwritten)")
    else:
        json.dump(show, open(path, "w"), indent=2, ensure_ascii=False)
        print(f"created: {path}")
    with open(os.path.join(a.dir, "bible/style/look.md"), "a") as f:
        if os.path.getsize(f.name) == 0:
            f.write(f"# Look — {a.title}\n\nStyle line: {a.style}\n\n(Colorist/DOP: lock palette, lens feel, lighting here.)\n")
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import studio_board
        studio_board.refresh_hub(a.dir)
    except Exception:
        pass
    print(f"production ready at {a.dir}")

if __name__ == "__main__":
    main()
