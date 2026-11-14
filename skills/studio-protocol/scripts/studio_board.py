#!/usr/bin/env python3
"""studio_board.py — Unified Single-Page Production Status Dashboard & Studio Hub.

Combines Pipeline Progress Bar, Stage Stepper, Scene Readiness Matrix, Cast Bible Status,
Director Action Inbox (Escalations), Script Breakdown, Screenplay, Storyboard, Video Dailies,
and Cuts/Masters into ONE HTML page (`production/studio_hub.html`).

  studio_board.py hub        --production production [--episode EP01] [--script script.txt] [--out production/studio_hub.html] [--embed]
  studio_board.py serve      --production production [--episode EP01] [--port 8765]   # live two-way UI -> director_notes.json
  studio_board.py script     --breakdown production/callsheets/EP01_breakdown.json [--out ...]
  studio_board.py screenplay --script script.txt [--shotlists ...] [--out ...]
  studio_board.py storyboard --shotlist production/callsheets/EP01_SC04.shotlist.json [--dailies ...] --out ...
"""
import argparse, base64, glob, html as H, http.server, json, os, re, sys, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import contracts  # noqa: E402
import provenance  # noqa: E402

SHARED_CSS = """
:root { --bg:#0b0d11; --panel:#141821; --panel2:#1b202c; --border:#283041; --text:#eef2f6; --muted:#94a3b8; --accent:#3b82f6; --amber:#f59e0b; --green:#22c55e; --red:#ef4444; --purple:#a855f7; }
* { box-sizing:border-box; }
body { font-family:'Inter',system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); margin:0; padding:20px 28px 48px; line-height:1.5; }
.topbar { position:sticky; top:10px; z-index:30; background:rgba(20,24,33,0.96); backdrop-filter:blur(12px); border:1px solid var(--border); border-radius:14px; padding:14px 18px; margin-bottom:20px; display:flex; flex-direction:column; gap:12px; box-shadow:0 10px 30px rgba(0,0,0,0.45); }
.top-row { display:flex; justify-content:space-between; align-items:center; gap:14px; flex-wrap:wrap; }
.title-grp h1 { font-size:18px; margin:0; font-weight:700; letter-spacing:-0.01em; display:flex; align-items:center; gap:8px; }
.title-grp .sub { font-size:12px; color:var(--muted); margin-top:2px; }
.tabs { display:flex; gap:5px; background:#090b0f; padding:4px; border-radius:10px; border:1px solid var(--border); flex-wrap:wrap; }
.tab-btn { background:transparent; color:var(--muted); border:0; padding:6px 12px; border-radius:7px; font-size:12px; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:5px; }
.tab-btn:hover { color:var(--text); }
.tab-btn.active { background:var(--accent); color:#fff; }
.top-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.status-pill { font-family:ui-monospace,monospace; font-size:12px; background:#090b0f; border:1px solid var(--border); padding:6px 12px; border-radius:8px; color:#cbd5e1; max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.save-btn { background:var(--accent); color:#fff; border:0; padding:7px 13px; border-radius:8px; font-size:12px; font-weight:700; cursor:pointer; }
.ghost-btn { background:var(--panel2); color:#cbd5e1; border:1px solid var(--border); padding:7px 11px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer; }

/* Master Progress Bar & Pipeline Stepper */
.prog-wrap { display:flex; align-items:center; gap:14px; }
.prog-track { flex:1; height:10px; background:#090b0f; border:1px solid var(--border); border-radius:999px; overflow:hidden; }
.prog-fill { height:100%; background:linear-gradient(90deg, #3b82f6, #22c55e); border-radius:999px; transition:width 0.3s ease; }
.prog-pct { font-size:13px; font-weight:700; color:#f8fafc; min-width:130px; text-align:right; }

.stepper { display:grid; grid-template-columns:repeat(6, minmax(130px, 1fr)); gap:10px; margin-bottom:22px; }
.step-card { background:var(--panel); border:1px solid var(--border); border-radius:11px; padding:12px 14px; display:flex; flex-direction:column; gap:4px; cursor:pointer; transition:transform 0.12s, border-color 0.12s; }
.step-card:hover { transform:translateY(-1px); border-color:#475569; }
.step-card.st-done { border-color:rgba(34,197,94,0.45); background:linear-gradient(180deg, rgba(34,197,94,0.08), var(--panel)); }
.step-card.st-active { border-color:rgba(59,130,246,0.65); background:linear-gradient(180deg, rgba(59,130,246,0.12), var(--panel)); }
.step-card.st-warn { border-color:rgba(245,158,11,0.65); background:linear-gradient(180deg, rgba(245,158,11,0.12), var(--panel)); }
.step-top { display:flex; justify-content:space-between; align-items:center; font-size:12px; font-weight:700; }
.step-sub { font-size:11px; color:var(--muted); }

/* Overview Matrix & Cards */
.sec-hdr { display:flex; justify-content:space-between; align-items:center; margin:22px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }
.sec-hdr h2 { margin:0; font-size:16px; display:flex; align-items:center; gap:8px; }
.alert-box { background:rgba(245,158,11,0.10); border:1px solid rgba(245,158,11,0.45); border-left:4px solid var(--amber); border-radius:10px; padding:14px 16px; margin-bottom:18px; }
.alert-box h3 { margin:0 0 8px; font-size:14px; color:#fcd34d; }
.matrix-table { width:100%; border-collapse:separate; border-spacing:0; background:var(--panel); border:1px solid var(--border); border-radius:12px; overflow:hidden; font-size:13px; margin-bottom:22px; }
.matrix-table th { text-align:left; padding:11px 14px; background:var(--panel2); color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:0.05em; border-bottom:1px solid var(--border); }
.matrix-table td { padding:12px 14px; border-bottom:1px solid #1e2432; vertical-align:middle; }
.matrix-table tr:last-child td { border-bottom:0; }
.mini-bar { width:110px; height:7px; background:#090b0f; border-radius:99px; overflow:hidden; display:inline-block; vertical-align:middle; margin-right:8px; border:1px solid var(--border); }
.mini-fill { height:100%; background:linear-gradient(90deg, #3b82f6, #22c55e); }
.cast-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:12px; margin-bottom:22px; }
.cast-card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:10px 12px; display:flex; align-items:center; gap:12px; }
.cast-avatar { width:48px; height:48px; border-radius:8px; background:#090b0f; border:1px solid var(--border); object-fit:cover; display:flex; align-items:center; justify-content:center; font-weight:700; color:var(--muted); flex-shrink:0; }

.badge { display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; letter-spacing:0.02em; }
.b-blue { background:rgba(59,130,246,0.16); color:#93c5fd; border:1px solid rgba(59,130,246,0.35); }
.b-amber { background:rgba(245,158,11,0.16); color:#fcd34d; border:1px solid rgba(245,158,11,0.35); }
.b-green { background:rgba(34,197,94,0.16); color:#86efac; border:1px solid rgba(34,197,94,0.35); }
.b-red { background:rgba(239,68,68,0.16); color:#fca5a5; border:1px solid rgba(239,68,68,0.35); }
.b-purple { background:rgba(168,85,247,0.16); color:#d8b4fe; border:1px solid rgba(168,85,247,0.35); }
.b-muted { background:#181d27; color:#94a3b8; border:1px solid #283041; }
.kpi-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:12px; margin-bottom:20px; }
.kpi { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:13px 15px; }
.kpi .k-val { font-size:21px; font-weight:700; }
.kpi .k-lbl { font-size:12px; color:var(--muted); }

/* Comment & Provenance Drawer */
.note-box { display:flex; gap:6px; align-items:center; margin-top:4px; }
.note-input { width:100%; background:#0b0d11; border:1px solid var(--border); color:var(--text); border-radius:6px; padding:6px 10px; font-size:12px; font-family:inherit; }
.note-input:focus { outline:none; border-color:var(--accent); }
details.prov { background:#0e1117; border:1px solid var(--border); border-radius:6px; padding:6px 10px; font-size:11px; color:var(--muted); }
details.prov summary { cursor:pointer; font-weight:600; color:#93c5fd; user-select:none; }
details.prov pre { white-space:pre-wrap; word-break:break-word; color:#cbd5e1; background:#090b0e; padding:8px; border-radius:5px; border:1px solid #1e2530; margin:6px 0 4px; font-size:11px; max-height:180px; overflow:auto; }
.ref-chip { display:inline-block; background:#161b24; border:1px solid #2b3445; border-radius:4px; padding:2px 6px; margin:2px 4px 2px 0; font-family:ui-monospace,monospace; font-size:10px; color:#cbd5e1; }

/* Script Breakdown */
.scene-list { display:grid; gap:14px; }
.scene-card { background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:18px 20px; display:grid; gap:10px; }
.scene-head { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
.scene-slug { font-size:15px; font-weight:700; font-family:ui-monospace,SFMono-Regular,monospace; color:#f8fafc; }
.purpose-box { display:grid; grid-template-columns:1fr 1fr; gap:12px; background:var(--panel2); border-radius:8px; padding:10px 14px; border-left:3px solid var(--amber); font-size:13px; }
.purpose-box strong { color:#fde68a; display:block; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:2px; }
.cast-row { display:flex; flex-wrap:wrap; gap:6px; }

/* Screenplay */
.sp-wrap { max-width:860px; margin:0 auto; background:#14171f; border:1px solid var(--border); border-radius:12px; padding:36px 52px; box-shadow:0 12px 36px rgba(0,0,0,0.45); font-family:'Courier Prime','Courier New',Courier,monospace; font-size:15px; line-height:1.55; }
.sp-slug { font-weight:700; text-transform:uppercase; color:#f8fafc; background:#1e2433; padding:6px 12px; border-left:4px solid var(--accent); margin:28px 0 14px; letter-spacing:0.04em; display:flex; justify-content:space-between; }
.sp-slug:first-child { margin-top:0; }
.sp-action { color:#e2e8f0; margin:10px 0; }
.sp-char { text-align:center; font-weight:700; color:#93c5fd; margin:18px auto 2px; width:60%; letter-spacing:0.06em; }
.sp-paren { text-align:center; color:var(--muted); font-style:italic; width:52%; margin:0 auto 4px; font-size:13px; }
.sp-dlg { width:68%; margin:0 auto 12px; color:#f8fafc; }
.sp-tag { font-family:system-ui,sans-serif; font-size:11px; background:rgba(245,158,11,0.18); color:#fcd34d; padding:1px 6px; border-radius:4px; margin:0 2px; vertical-align:middle; }
.sp-subtext { width:72%; margin:4px auto 12px; background:rgba(168,85,247,0.10); border-left:2px solid var(--purple); padding:6px 10px; font-family:system-ui,sans-serif; font-size:12px; color:#e9d5ff; border-radius:0 6px 6px 0; }

/* Storyboard & Dailies */
.sb-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:18px; }
.sb-card { background:var(--panel); border:2px solid var(--border); border-radius:12px; overflow:hidden; display:flex; flex-direction:column; transition:border-color 0.15s; }
.sb-card.tp { border-color:rgba(245,158,11,0.65); }
.sb-card.approved { border-color:var(--green); }
.sb-card.flagged { border-color:var(--red); }
.sb-hdr { padding:10px 14px; background:var(--panel2); display:flex; justify-content:space-between; align-items:center; gap:8px; border-bottom:1px solid var(--border); }
.sb-frame { position:relative; width:100%; background:#090b0e; display:flex; align-items:center; justify-content:center; overflow:hidden; }
.sb-frame.ar-9x16 { aspect-ratio:16/10; }
.sb-frame.ar-16x9 { aspect-ratio:16/9; }
.sb-frame img, .sb-frame video { width:100%; height:100%; object-fit:cover; }
.vid-player { width:100%; max-height:460px; background:#000; display:block; }
.strip-details { padding:6px 14px; font-size:11px; color:var(--muted); border-bottom:1px solid var(--border); }
.strip-details summary { cursor:pointer; }
.strip-details img { width:100%; border-radius:4px; margin-top:6px; }
.sb-placeholder { padding:20px; text-align:center; color:var(--muted); font-size:12px; border:1px dashed #334155; margin:14px; border-radius:8px; width:calc(100% - 28px); }
.sb-cam-overlay { position:absolute; bottom:8px; left:8px; right:8px; background:rgba(9,11,14,0.82); backdrop-filter:blur(4px); padding:4px 8px; border-radius:6px; font-size:11px; color:#cbd5e1; border:1px solid rgba(255,255,255,0.1); }
.sb-body { padding:12px 14px; display:grid; gap:8px; font-size:13px; flex:1; }
.sb-block { background:var(--panel2); padding:8px 10px; border-radius:6px; font-size:12px; color:#cbd5e1; }
.sb-dlg { background:#11151d; border-left:3px solid var(--accent); padding:8px 10px; border-radius:0 6px 6px 0; font-size:12px; }
.sb-actions { padding:10px 14px; border-top:1px solid var(--border); display:flex; gap:8px; }
.btn { border:1px solid var(--border); background:var(--panel2); color:var(--text); padding:6px 12px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; flex:1; }
.btn-ok:hover, .sb-card.approved .btn-ok { background:rgba(34,197,94,0.2); border-color:var(--green); color:#86efac; }
.btn-flag:hover, .sb-card.flagged .btn-flag { background:rgba(239,68,68,0.2); border-color:var(--red); color:#fca5a5; }
.pane-section-label { display:none; margin:28px 0 14px; padding:10px 14px; background:var(--panel2); border-left:4px solid var(--accent); border-radius:6px; font-size:15px; font-weight:700; }
body.all-in-one .tab-pane { display:block !important; margin-bottom:34px; }
body.all-in-one .pane-section-label { display:block; }
"""

STATUS_ICON = {"done": "✅", "active": "🔄", "warn": "⚠️", "pending": "⏳"}


def _img_uri(path, out_html, embed=False):
    if not path or not os.path.exists(path):
        return ""
    if embed:
        mt = "image/png" if path.lower().endswith(".png") else "image/jpeg"
        with open(path, "rb") as f:
            return f"data:{mt};base64," + base64.b64encode(f.read()).decode()
    return os.path.relpath(os.path.abspath(path), os.path.dirname(os.path.abspath(out_html)))


def _media_uri(path, out_html, embed_video=False):
    if not path or not os.path.exists(path):
        return ""
    if embed_video:
        with open(path, "rb") as f:
            return "data:video/mp4;base64," + base64.b64encode(f.read()).decode()
    return os.path.relpath(os.path.abspath(path), os.path.dirname(os.path.abspath(out_html)))


def _style_inline_tags(line):
    escaped = H.escape(line)
    escaped = re.sub(r"\[([^\]]+)\]", r"<span class='sp-tag'>\1</span>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", escaped)
    return escaped


def _note_widget(target_key, existing_notes):
    cur = (existing_notes or {}).get(target_key, {})
    val = cur.get("comment", "")
    return (
        f"<div class='note-box'>"
        f"<input class='note-input' type='text' data-note-target='{H.escape(target_key)}' "
        f"value='{H.escape(val)}' placeholder='💬 Director note for {H.escape(target_key)} (auto-applied on next roll)...' "
        f"oninput=\"recordNote('{H.escape(target_key)}', this.value)\"/>"
        f"</div>"
    )


def _prov_drawer(prompt_txt, model_lbl, refs, characters=(), stale_msg=""):
    chips = "".join(
        f"<span class='ref-chip'>{H.escape(os.path.basename(r['path']) if isinstance(r, dict) else os.path.basename(str(r)))}"
        + (f" #{H.escape(r['sha256_16'][:8])}" if isinstance(r, dict) and r.get("sha256_16") else "")
        + "</span>"
        for r in (refs or ())
    ) or "<span style='color:var(--muted)'>none</span>"
    chars_txt = ", ".join(characters) if characters else "—"
    stale_html = f" <span class='badge b-red'>⚠ {H.escape(stale_msg)}</span>" if stale_msg else ""
    return (
        f"<details class='prov'><summary>🔍 Exact Prompt & Resources{stale_html}</summary>"
        f"<div style='margin-top:6px'><strong>Model/Lane:</strong> {H.escape(model_lbl or 'compiled pre-roll')} · <strong>Characters:</strong> {H.escape(chars_txt)}</div>"
        f"<div style='margin-top:4px'><strong>Refs:</strong> {chips}</div>"
        f"<pre>{H.escape(prompt_txt or '')}</pre>"
        f"</details>"
    )


def compute_production_state(production_dir, episode, bd, cs_map, sls):
    """Compute intuitive 6-stage pipeline progress, per-scene readiness, cast bible status, and active escalations."""
    bible_chars_dir = os.path.join(production_dir, "bible", "characters")
    bible_voices_dir = os.path.join(production_dir, "bible", "voices")
    dailies_root = os.path.join(production_dir, "dailies")
    cuts = sorted(glob.glob(os.path.join(production_dir, "cuts", f"*{episode}*.mp4"))) or sorted(glob.glob(os.path.join(production_dir, "cuts", "*.mp4")))
    masters = sorted(glob.glob(os.path.join(production_dir, "masters", f"*{episode}*.mp4"))) or sorted(glob.glob(os.path.join(production_dir, "masters", "*.mp4")))

    # Discover all scene IDs across breakdown, callsheets, shotlists, and dailies
    scene_keys = []
    for s in bd.get("scenes", []):
        sc = s.get("scene", "")
        full = sc if sc.startswith(episode) else f"{episode}_{sc}"
        if full not in scene_keys:
            scene_keys.append((full, sc, s.get("heading", "")))
    for sl in sls:
        sc = sl.get("scene", "")
        if sc and not any(k[0] == sc or k[1] == sc for k in scene_keys):
            scene_keys.append((sc, sc, "ShotList Scene"))

    sl_by_scene = {}
    for sl in sls:
        sl_by_scene[sl.get("scene", "")] = sl

    # Characters from breakdown + shotlists + bible dir
    char_names = set()
    for s in bd.get("scenes", []):
        for c in (s.get("characters") or {}):
            char_names.add(c.lower())
    for sl in sls:
        for sh in sl.get("shots", []):
            for c in sh.get("characters", []):
                char_names.add(c.lower())
            for d in sh.get("dialogue", []):
                if d.get("speaker"):
                    char_names.add(d["speaker"].lower())
    if os.path.isdir(bible_chars_dir):
        for name in os.listdir(bible_chars_dir):
            if os.path.isdir(os.path.join(bible_chars_dir, name)):
                char_names.add(name.lower())

    cast_status = []
    for c in sorted(char_names):
        front = os.path.join(bible_chars_dir, c, "front.png")
        sheet = os.path.join(bible_chars_dir, c, "sheet.png")
        voice = os.path.join(bible_voices_dir, c, "fingerprint.md")
        cast_status.append({
            "name": c,
            "front": front if os.path.exists(front) else "",
            "has_look": os.path.exists(front) or os.path.exists(sheet),
            "has_voice": os.path.exists(voice),
        })

    scene_rows = []
    escalations = []
    total_shots, rolled_shots, clean_shots = 0, 0, 0
    for full_sc, short_sc, heading in scene_keys:
        has_cs = (full_sc in cs_map) or (short_sc in cs_map) or os.path.exists(os.path.join(production_dir, "callsheets", f"{full_sc}.md"))
        sl = sl_by_scene.get(full_sc) or sl_by_scene.get(short_sc)
        n_shots = len(sl.get("shots", [])) if sl else 0
        total_shots += n_shots

        sc_dl = os.path.join(dailies_root, full_sc)
        if not os.path.isdir(sc_dl) and os.path.isdir(os.path.join(dailies_root, short_sc)):
            sc_dl = os.path.join(dailies_root, short_sc)
        mp4s = glob.glob(os.path.join(sc_dl, "*.mp4")) if os.path.isdir(sc_dl) else []
        rolled_shot_ids = {re.sub(r"_take\d+\.mp4$", "", os.path.basename(p)) for p in mp4s}
        n_rolled = len(rolled_shot_ids)
        rolled_shots += n_rolled

        qc_p = os.path.join(sc_dl, "qc.json")
        qc = json.load(open(qc_p, encoding="utf-8")) if os.path.exists(qc_p) else {}
        flagged_takes = sum(1 for v in qc.values() if v.get("flags"))
        clean_take_shots = {re.sub(r"_take\d+\.mp4$", "", k) for k, v in qc.items() if not v.get("flags")}
        clean_shots += len(clean_take_shots)

        sc_escs = []
        for ep in sorted(glob.glob(os.path.join(sc_dl, "escalations", "*.json"))):
            try:
                eobj = json.load(open(ep, encoding="utf-8"))
                if not eobj.get("resolved"):
                    sc_escs.append(eobj)
                    escalations.append(eobj)
            except Exception:
                pass

        # Compute scene % across 4 milestones: CallSheet (20%) + ShotList (30%) + Rolls (30%) + QC/Lock (20%)
        pct = (20 if has_cs else 0) + (30 if sl else 0)
        if n_shots > 0:
            pct += int(30 * min(1.0, n_rolled / n_shots))
            pct += int(20 * min(1.0, len(clean_take_shots) / n_shots))
        elif mp4s:
            pct += 50

        scene_rows.append({
            "scene": full_sc,
            "heading": heading,
            "has_cs": has_cs,
            "has_sl": bool(sl),
            "n_shots": n_shots,
            "n_rolled": n_rolled,
            "n_takes": len(mp4s),
            "qc_done": bool(qc),
            "flagged_takes": flagged_takes,
            "escalations": len(sc_escs),
            "pct": min(100, pct),
        })

    # 6 Pipeline Stages
    has_script = bool(bd.get("scenes") or cs_map)
    st1 = ("done", f"{len(scene_rows)} scene(s)") if has_script else ("pending", "Awaiting script")

    if not cast_status:
        st2 = ("pending", "No cast yet")
    elif all(c["has_look"] for c in cast_status):
        st2 = ("done", f"{len(cast_status)}/{len(cast_status)} locked")
    elif any(c["has_look"] or c["has_voice"] for c in cast_status):
        st2 = ("active", f"{sum(1 for c in cast_status if c['has_look'])}/{len(cast_status)} cast")
    else:
        st2 = ("warn", f"{len(cast_status)} need refs")

    if sls and len(sls) >= max(1, len(bd.get("scenes", []))):
        st3 = ("done", f"{total_shots} shot(s) planned")
    elif sls:
        st3 = ("active", f"{len(sls)} scene(s) boarded")
    else:
        st3 = ("pending", "Not boarded yet")

    if escalations:
        st4 = ("warn", f"{len(escalations)} escalation(s)")
    elif total_shots > 0 and rolled_shots >= total_shots:
        st4 = ("done", f"{rolled_shots}/{total_shots} shots rolled")
    elif rolled_shots > 0:
        st4 = ("active", f"{rolled_shots}/{max(total_shots, rolled_shots)} rolled")
    else:
        st4 = ("pending", "Cameras idle")

    st5 = ("done", f"{len(cuts)} cut(s)") if cuts else ("pending", "No cut yet")
    st6 = ("done", f"{len(masters)} master(s)") if masters else ("pending", "Not delivered")

    stages = [
        {"id": "script", "num": 1, "name": "Script & Breakdown", "state": st1[0], "detail": st1[1], "tab": "script"},
        {"id": "bible", "num": 2, "name": "Cast & Voice Bible", "state": st2[0], "detail": st2[1], "tab": "overview"},
        {"id": "storyboard", "num": 3, "name": "Storyboard & Prompts", "state": st3[0], "detail": st3[1], "tab": "storyboard"},
        {"id": "dailies", "num": 4, "name": "Camera & Dailies QC", "state": st4[0], "detail": st4[1], "tab": "dailies"},
        {"id": "edit", "num": 5, "name": "Edit, Grade & Mix", "state": st5[0], "detail": st5[1], "tab": "cuts"},
        {"id": "master", "num": 6, "name": "Master Delivery", "state": st6[0], "detail": st6[1], "tab": "cuts"},
    ]
    weights = {"done": 1.0, "active": 0.5, "warn": 0.5, "pending": 0.0}
    overall_pct = int(round(100 * sum(weights[s["state"]] for s in stages) / len(stages)))
    return {
        "overall_pct": overall_pct,
        "stages": stages,
        "scene_rows": scene_rows,
        "cast_status": cast_status,
        "escalations": escalations,
        "cuts_count": len(cuts),
        "masters_count": len(masters),
    }


def render_overview_section(state, out_html, embed=False):
    """Render Pipeline Stepper, Active Escalations, Scene Readiness Matrix, and Cast Bible strip."""
    # 1. 6-Stage Stepper
    step_cards = []
    for st in state["stages"]:
        ico = STATUS_ICON[st["state"]]
        step_cards.append(
            f"<div class='step-card st-{st['state']}' onclick=\"showTab('{st['tab']}', document.querySelector(`[data-tab='{st['tab']}']`))\"><div class='step-top'><span>{st['num']}. {H.escape(st['name'])}</span><span>{ico}</span></div>"
            f"<div class='step-sub'>{H.escape(st['detail'])}</div>"
            f"</div>"
        )
    stepper_html = f"<div class='stepper'>{''.join(step_cards)}</div>"

    # 2. Active Escalations Banner (if any)
    esc_html = ""
    if state["escalations"]:
        items = []
        for e in state["escalations"]:
            opts = " / ".join(f"<strong>{H.escape(o['key'])}</strong>: {H.escape(o['label'])}" for o in e.get("options", []))
            items.append(
                f"<div style='margin-bottom:8px'><strong>{H.escape(e.get('scene',''))} · Shot {H.escape(e.get('shot',''))}</strong> "
                f"<span class='badge b-red'>{H.escape(e.get('reason_code',''))}</span> — {H.escape(e.get('question',''))}<br>"
                f"<span style='font-size:12px;color:#cbd5e1'>Options: {opts}</span></div>"
            )
        esc_html = f"<div class='alert-box'><h3>⚠️ Needs Director Decision ({len(state['escalations'])})</h3>{''.join(items)}</div>"

    # 3. Scene-by-Scene Readiness Matrix
    rows_html = []
    for r in state["scene_rows"]:
        cs_ico = "✅ Ready" if r["has_cs"] else "⏳ Pending"
        sl_ico = f"✅ {r['n_shots']} shots" if r["has_sl"] else "⏳ Pending"
        if r["n_shots"] > 0 and r["n_rolled"] >= r["n_shots"]:
            cam_ico = f"✅ {r['n_rolled']}/{r['n_shots']} ({r['n_takes']} takes)"
        elif r["n_rolled"] > 0:
            cam_ico = f"🔄 {r['n_rolled']}/{max(r['n_shots'], r['n_rolled'])} ({r['n_takes']} takes)"
        else:
            cam_ico = "⏳ 0 rolled"

        if r["escalations"]:
            qc_badge = f"<span class='badge b-red'>⚠️ {r['escalations']} escalated</span>"
        elif r["qc_done"] and r["flagged_takes"] == 0 and r["n_takes"] > 0:
            qc_badge = "<span class='badge b-green'>✅ All clean</span>"
        elif r["qc_done"]:
            qc_badge = f"<span class='badge b-amber'>⚠️ {r['flagged_takes']} flagged</span>"
        else:
            qc_badge = "<span class='badge b-muted'>⏳ Not run</span>"

        rows_html.append(
            f"<tr>"
            f"<td><strong>{H.escape(r['scene'])}</strong><div style='font-size:11px;color:var(--muted)'>{H.escape(r['heading'])}</div></td>"
            f"<td>{cs_ico}</td>"
            f"<td>{sl_ico}</td>"
            f"<td>{cam_ico}</td>"
            f"<td>{qc_badge}</td>"
            f"<td><div class='mini-bar'><div class='mini-fill' style='width:{r['pct']}%'></div></div><strong>{r['pct']}%</strong></td>"
            f"</tr>"
        )
    matrix_html = (
        "<div class='sec-hdr'><h2>📊 Scene Production Tracker</h2></div>"
        "<table class='matrix-table'><thead><tr>"
        "<th>Scene</th><th>CallSheet</th><th>Storyboard</th><th>Camera Rolls</th><th>QC & Continuity</th><th>Progress</th>"
        "</tr></thead><tbody>"
        + ("".join(rows_html) or "<tr><td colspan='6' style='color:var(--muted)'>No scenes broken down yet.</td></tr>")
        + "</tbody></table>"
    )

    # 4. Cast & Voice Bible Readiness
    cast_cards = []
    for c in state["cast_status"]:
        uri = _img_uri(c["front"], out_html, embed=embed) if c["front"] else ""
        av = f"<img class='cast-avatar' src='{uri}'/>" if uri else f"<div class='cast-avatar'>{H.escape(c['name'][:2].upper())}</div>"
        look_b = "<span class='badge b-green'>✅ Look</span>" if c["has_look"] else "<span class='badge b-amber'>⏳ Look</span>"
        voice_b = "<span class='badge b-green'>🎙️ Voice</span>" if c["has_voice"] else "<span class='badge b-muted'>⏳ Voice</span>"
        cast_cards.append(
            f"<div class='cast-card'>{av}<div><div style='font-weight:700;text-transform:capitalize'>{H.escape(c['name'])}</div>"
            f"<div style='margin-top:4px;display:flex;gap:4px'>{look_b}{voice_b}</div></div></div>"
        )
    cast_html = (
        "<div class='sec-hdr'><h2>🎭 Cast & Voice Bible Status</h2></div>"
        + (f"<div class='cast-grid'>{''.join(cast_cards)}</div>" if cast_cards else "<div style='color:var(--muted);font-size:13px'>No characters registered yet.</div>")
    )
    return stepper_html + esc_html + matrix_html + cast_html


def render_script_section(breakdown, callsheets=None, existing_notes=None):
    callsheets = callsheets or {}
    scenes = breakdown.get("scenes", [])
    total_s = breakdown.get("total_estimated_seconds") or sum(s.get("estimated_seconds", 0) for s in scenes)
    total_clips = sum(s.get("estimated_clips", 0) for s in scenes)
    all_cast = sorted({c for s in scenes for c in (s.get("characters") or {})})

    kpis = (
        f"<div class='kpi-row'>"
        f"<div class='kpi'><div class='k-val'>{H.escape(breakdown.get('episode', 'EP01'))}</div><div class='k-lbl'>Episode</div></div>"
        f"<div class='kpi'><div class='k-val'>{len(scenes)}</div><div class='k-lbl'>Scenes</div></div>"
        f"<div class='kpi'><div class='k-val'>~{total_s}s</div><div class='k-lbl'>Estimated Runtime</div></div>"
        f"<div class='kpi'><div class='k-val'>{total_clips}</div><div class='k-lbl'>Estimated Camera Clips</div></div>"
        f"<div class='kpi'><div class='k-val'>{len(all_cast)}</div><div class='k-lbl'>Speaking Cast ({H.escape(', '.join(all_cast) or '—')})</div></div>"
        f"</div>"
    )
    cards = []
    ep = breakdown.get("episode", "EP01")
    for s in scenes:
        sc_id = s.get("scene", "SC01")
        full_sc = f"{ep}_{sc_id}"
        cs = callsheets.get(sc_id) or callsheets.get(full_sc) or {}
        sp = cs.get("scene_purpose") or {}
        tp = cs.get("turning_point") or ""
        fn_label = (sp.get("function") or "dramatic_beat").replace("_", " ").upper()
        purpose_html = ""
        if sp.get("summary") or tp:
            purpose_html = (
                f"<div class='purpose-box'>"
                f"<div><strong>Core Purpose ({H.escape(fn_label)})</strong>{H.escape(sp.get('summary') or '—')}</div>"
                f"<div><strong>★ Turning Point</strong>{H.escape(tp or '—')}</div>"
                f"</div>"
            )
        cast_badges = "".join(
            f"<span class='badge b-blue'>{H.escape(c)} · {w}w</span>" for c, w in (s.get("characters") or {}).items()
        ) or "<span class='badge b-muted'>Silent / Visual</span>"
        brief_html = f"<div style='color:var(--muted);font-size:13px'>{H.escape(cs.get('brief',''))}</div>" if cs.get("brief") else ""
        cards.append(
            f"<div class='scene-card'>"
            f"<div class='scene-head'>"
            f"<div class='scene-slug'>📜 {H.escape(sc_id)} — {H.escape(s.get('heading',''))}</div>"
            f"<div><span class='badge b-amber'>~{s.get('estimated_seconds',0)}s</span> "
            f"<span class='badge b-purple'>{s.get('estimated_clips',1)} clip(s)</span> "
            f"<span class='badge b-green'>{H.escape(cs.get('mode','dailies'))}</span></div>"
            f"</div>"
            f"{brief_html}{purpose_html}"
            f"<div class='cast-row'>{cast_badges}</div>"
            f"{_note_widget(full_sc, existing_notes)}"
            f"</div>"
        )
    return kpis + f"<div class='scene-list'>{''.join(cards)}</div>"


def render_screenplay_section(script_text, shotlists=None):
    subtext_by_speaker = {}
    for sl in (shotlists or []):
        for sh in sl.get("shots", []):
            for d in sh.get("dialogue", []):
                key = d.get("speaker", "").upper()
                if d.get("intention") or d.get("objective") or d.get("subtext"):
                    subtext_by_speaker.setdefault(key, []).append(d)

    slug_re = re.compile(r"^\s*(?:(?:INT|EXT|INT\./EXT|I/E)\.?\s.+|(?:SCENE|Scene)\s+\d+.*|##\s+.+)$")
    cue_re = re.compile(r"^\s*([A-Z][A-Z0-9 .'\-]{1,30})(\s*\(.*\))?\s*$")

    out = ["<div class='sp-wrap'>"]
    sc_num = 0
    speaker = None
    spk_idx = {}
    for raw in script_text.splitlines():
        ln = raw.strip()
        if not ln:
            speaker = None
            continue
        if slug_re.match(raw):
            sc_num += 1
            clean = ln.lstrip("#").strip()
            out.append(f"<div class='sp-slug'><span>{sc_num}. {H.escape(clean)}</span><span>SC{sc_num:02d}</span></div>")
            speaker = None
        elif cue_re.match(raw) and len(ln) < 35 and not ln.endswith("."):
            m = cue_re.match(raw)
            speaker = m.group(1).strip()
            paren = (m.group(2) or "").strip()
            out.append(f"<div class='sp-char'>{H.escape(speaker)}</div>")
            if paren:
                out.append(f"<div class='sp-paren'>{H.escape(paren)}</div>")
        elif speaker and ln.startswith("(") and ln.endswith(")"):
            out.append(f"<div class='sp-paren'>{H.escape(ln)}</div>")
        elif speaker:
            out.append(f"<div class='sp-dlg'>{_style_inline_tags(ln)}</div>")
            notes = subtext_by_speaker.get(speaker.upper(), [])
            idx = spk_idx.get(speaker.upper(), 0)
            if idx < len(notes):
                n = notes[idx]
                spk_idx[speaker.upper()] = idx + 1
                bits = []
                if n.get("intention"):
                    bits.append(f"<strong>Intention:</strong> {H.escape(n['intention'])}")
                if n.get("objective"):
                    bits.append(f"<strong>Objective:</strong> {H.escape(n['objective'])}")
                if n.get("subtext"):
                    bits.append(f"<strong>Subtext:</strong> {H.escape(n['subtext'])}")
                if bits:
                    out.append(f"<div class='sp-subtext'>{' · '.join(bits)}</div>")
        else:
            out.append(f"<div class='sp-action'>{H.escape(ln)}</div>")
    out.append("</div>")
    return "\n".join(out)


def render_storyboard_section(shotlists, out_html, dailies_root=None, bible_dir=None, production_dir=None, existing_notes=None, embed=False):
    sections = []
    prod = production_dir or (os.path.dirname(os.path.abspath(dailies_root.rstrip("/"))) if dailies_root else "production")
    bible = bible_dir or os.path.join(prod, "bible")
    for sl in shotlists:
        scene = sl.get("scene", "SCENE")
        sc_dailies = (
            dailies_root
            if (dailies_root and os.path.basename(dailies_root.rstrip("/")) == scene)
            else os.path.join(dailies_root or os.path.join(prod, "dailies"), scene)
        )
        compiled_by_id = {m["id"]: m for m in contracts.compile_manifest(sl, bible, sc_dailies, scene, production_dir=prod)}
        ar_cls = "ar-9x16" if sl.get("aspect", "9:16") == "9:16" else "ar-16x9"
        cards = []
        for s in sl.get("shots", []):
            sid = s["id"]
            target_key = f"{scene}/{sid}"
            cur_note = (existing_notes or {}).get(target_key, {})
            init_cls = " approved" if cur_note.get("status") == "approved" else (" flagged" if cur_note.get("status") == "revise" else "")
            tp = s.get("is_turning_point")
            eb = s.get("emotional_blocking") or {}
            still = eb.get("stillness_accent")

            img_path = ""
            for cand in (os.path.join(sc_dailies, f"{sid}_take1_last.png"), os.path.join(sc_dailies, f"{sid}_take1_contact.png")):
                if os.path.exists(cand):
                    img_path = cand
                    break
            if not img_path and s.get("refs"):
                for r in s["refs"]:
                    if os.path.exists(r):
                        img_path = r
                        break
            uri = _img_uri(img_path, out_html, embed=embed)

            vid_candidates = sorted(glob.glob(os.path.join(sc_dailies, f"{sid}_take*.mp4")))
            vid_uri = _media_uri(vid_candidates[-1], out_html) if vid_candidates else ""
            status_ico = "🎥" if vid_candidates else "📝"

            rolled_meta = provenance.inspect_asset(vid_candidates[-1], production_dir=prod) if vid_candidates else None
            comp = compiled_by_id.get(sid, {})
            prompt_txt = (rolled_meta or {}).get("prompt") or comp.get("prompt", "")
            model_lbl = f"{rolled_meta['model']} ({rolled_meta['lane']})" if rolled_meta and rolled_meta.get("model") else f"Planned ({sl.get('resolution','720p')})"
            refs_list = (rolled_meta or {}).get("refs") or [{"path": p, "sha256_16": provenance.sha16(p)} for p in comp.get("images", [])]
            stale_msg = ""
            if rolled_meta:
                for r in rolled_meta.get("refs", []):
                    cur_h = provenance.sha16(r.get("path"))
                    if cur_h and r.get("sha256_16") and cur_h != r["sha256_16"]:
                        stale_msg = f"{os.path.basename(r['path'])} updated — reroll needed"

            badges = [f"<span class='badge b-blue'>{s['duration_s']}s</span>"]
            if vid_candidates:
                badges.append(f"<span class='badge b-green'>✅ {len(vid_candidates)} take(s)</span>")
            if s.get("chain_from"):
                badges.append(f"<span class='badge b-purple'>⛓ {H.escape(s['chain_from'])}</span>")
            if tp:
                badges.append("<span class='badge b-amber'>★ Turning Point</span>")
            if still:
                badges.append("<span class='badge b-green'>⏸ Stillness</span>")

            eb_lines = []
            if eb.get("power_dynamic"):
                eb_lines.append(f"<strong>Space/Power:</strong> {H.escape(eb['power_dynamic'])}")
            if eb.get("movement_motivation"):
                eb_lines.append(f"<strong>Motivation:</strong> {H.escape(eb['movement_motivation'])}")
            eb_html = f"<div class='sb-block'>{'<br>'.join(eb_lines)}</div>" if eb_lines else ""

            dlg_html = ""
            for d in s.get("dialogue", []):
                meta = " · ".join(x for x in (d.get("intention"), f"Obj: {d['objective']}" if d.get("objective") else "", f"Subtext: {d['subtext']}" if d.get("subtext") else "") if x)
                dlg_html += (
                    f"<div class='sb-dlg'><strong>{H.escape(d['speaker'].upper())}</strong> "
                    f"<span style='color:var(--muted)'>({H.escape(meta)})</span><br>"
                    f"{_style_inline_tags(d['line'])}</div>"
                )

            poster_attr = f" poster='{uri}'" if uri else ""
            if vid_uri:
                frame_inner = f"<video controls playsinline preload='metadata'{poster_attr} src='{vid_uri}'></video>"
                cam_overlay = ""
            elif uri:
                frame_inner = f"<img src='{uri}' alt='Shot {H.escape(sid)}'/>"
                cam_overlay = f"<div class='sb-cam-overlay'>🎥 {H.escape(s.get('camera',''))}</div>"
            else:
                frame_inner = f"<div class='sb-placeholder'><strong>{H.escape(sl.get('aspect','9:16'))} Frame</strong><br>{H.escape(s.get('camera',''))}</div>"
                cam_overlay = f"<div class='sb-cam-overlay'>🎥 {H.escape(s.get('camera',''))}</div>"
            cards.append(
                f"<div class='sb-card{' tp' if tp else ''}{init_cls}' data-shot='{H.escape(target_key)}'>"
                f"<div class='sb-hdr'><strong>{status_ico} Shot {H.escape(sid)}</strong><div>{' '.join(badges)}</div></div>"
                f"<div class='sb-frame {ar_cls}'>{frame_inner}{cam_overlay}</div>"
                f"<div class='sb-body'>"
                f"<div style='font-size:11px;color:var(--muted)'>🎥 {H.escape(s.get('camera',''))}</div>"
                f"<div>{H.escape(s.get('action',''))}</div>{eb_html}{dlg_html}"
                f"{_prov_drawer(prompt_txt, model_lbl, refs_list, comp.get('characters', ()), stale_msg=stale_msg)}"
                f"{_note_widget(target_key, existing_notes)}"
                f"</div>"
                f"<div class='sb-actions'>"
                f"<button class='btn btn-ok' onclick=\"sbVote('{H.escape(target_key)}','approved',this)\">✓ Approve</button>"
                f"<button class='btn btn-flag' onclick=\"sbVote('{H.escape(target_key)}','revise',this)\">⚑ Revise</button>"
                f"</div></div>"
            )
        sections.append(
            f"<div style='margin-bottom:28px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px'>"
            f"<h2 style='margin:0;font-size:16px'>{H.escape(scene)} · {H.escape(sl.get('aspect','9:16'))} · {len(sl.get('shots',[]))} shots</h2>"
            f"<span style='font-size:12px;color:var(--muted)'>Style: {H.escape(sl.get('style',''))}</span></div>"
            f"<div class='sb-grid'>{''.join(cards)}</div></div>"
        )
    if not sections:
        return "<div class='scene-card' style='color:var(--muted)'>⏳ No ShotLists authored yet. Once DOP writes `.shotlist.json`, storyboard panels appear here.</div>"
    return "".join(sections)


def render_dailies_section(production_dir, episode, out_html, existing_notes=None, embed=False, embed_video=False):
    dailies_root = os.path.join(production_dir, "dailies")
    scene_dirs = sorted(glob.glob(os.path.join(dailies_root, f"{episode}*")))
    if not scene_dirs and os.path.isdir(dailies_root):
        scene_dirs = sorted(d for d in glob.glob(os.path.join(dailies_root, "*")) if os.path.isdir(d))
    sections = []
    for sdir in scene_dirs:
        sc_name = os.path.basename(sdir)
        qc_p = os.path.join(sdir, "qc.json")
        qc = json.load(open(qc_p, encoding="utf-8")) if os.path.exists(qc_p) else {}
        mp4s = sorted(glob.glob(os.path.join(sdir, "*.mp4")))
        if not mp4s:
            continue
        cards = []
        for vp in mp4s:
            vname = os.path.basename(vp)
            sid = re.sub(r"_take\d+\.mp4$", "", vname)
            target_key = f"{sc_name}/{sid}"
            info = qc.get(vname, {})
            cur_note = (existing_notes or {}).get(target_key, {})
            init_cls = " approved" if cur_note.get("status") == "approved" else (" flagged" if cur_note.get("status") == "revise" else "")
            cpath = info.get("contact") or os.path.join(sdir, os.path.splitext(vname)[0] + "_contact.png")
            poster_uri = _img_uri(cpath, out_html, embed=embed)
            vid_uri = _media_uri(vp, out_html, embed_video=embed_video)
            poster_attr = f" poster='{poster_uri}'" if poster_uri else ""

            flags = info.get("flags") or []
            badges = [f"<span class='badge b-red'>⚠️ {H.escape(fl)}</span>" for fl in flags] or ["<span class='badge b-green'>✅ CLEAN</span>"]
            if info.get("duration"):
                badges.insert(0, f"<span class='badge b-blue'>{info['duration']}s</span>")

            meta_bits = []
            if info.get("margin") is not None:
                meta_bits.append(f"margin={info['margin']}s")
            if info.get("f0_std_semitones") is not None:
                meta_bits.append(f"f0={info['f0_std_semitones']}")
            if info.get("asr", {}).get("wer") is not None:
                meta_bits.append(f"WER={info['asr']['wer']}")

            pm = provenance.inspect_asset(vp, production_dir=production_dir) or {}
            strip_html = (
                f"<details class='strip-details'><summary>🎞 5-Frame Continuity Strip</summary><img src='{poster_uri}' alt='{H.escape(vname)}'/></details>"
                if poster_uri
                else ""
            )
            cards.append(
                f"<div class='sb-card{init_cls}' data-shot='{H.escape(target_key)}'>"
                f"<div class='sb-hdr'><strong>▶ {H.escape(vname)}</strong><div>{' '.join(badges)}</div></div>"
                f"<video class='vid-player' controls playsinline preload='metadata'{poster_attr} src='{vid_uri}'></video>"
                f"{strip_html}"
                f"<div class='sb-body'>"
                + (f"<div style='font-size:12px;color:var(--muted)'>{H.escape(' · '.join(meta_bits))}</div>" if meta_bits else "")
                + (f"<div class='sb-dlg'>\"{H.escape(info.get('asr',{}).get('transcript',''))}\"</div>" if info.get("asr", {}).get("transcript") else "")
                + (_prov_drawer(pm.get("prompt", ""), f"{pm.get('model','')} ({pm.get('lane','')})", pm.get("refs", ()), pm.get("characters", ())) if pm else "")
                + f"{_note_widget(target_key, existing_notes)}"
                f"</div>"
                f"<div class='sb-actions'>"
                f"<button class='btn btn-ok' onclick=\"sbVote('{H.escape(target_key)}','approved',this)\">✓ Approve Take</button>"
                f"<button class='btn btn-flag' onclick=\"sbVote('{H.escape(target_key)}','revise',this)\">⚑ Retake</button>"
                f"</div></div>"
            )
        sections.append(
            f"<div style='margin-bottom:28px'><h2 style='margin:0 0 12px;font-size:16px'>🎬 {H.escape(sc_name)} · {len(mp4s)} take(s)</h2>"
            f"<div class='sb-grid'>{''.join(cards)}</div></div>"
        )
    if not sections:
        return "<div class='scene-card' style='color:var(--muted)'>⏳ No video takes rolled in <code>production/dailies/</code> yet. Once Camera rolls, playable takes appear here automatically.</div>"
    return "".join(sections)


def render_cuts_section(production_dir, episode, out_html, embed_video=False):
    vids = []
    for label, sub in (("Cut", "cuts"), ("Master", "masters")):
        d = os.path.join(production_dir, sub)
        for p in sorted(glob.glob(os.path.join(d, "*.mp4"))):
            if episode.lower() in os.path.basename(p).lower() or not glob.glob(os.path.join(d, f"*{episode}*.mp4")):
                vids.append((label, p))
    if not vids:
        return "<div class='scene-card' style='color:var(--muted)'>⏳ No assembled cuts or masters in <code>production/cuts/</code> or <code>production/masters/</code> yet.</div>"
    cards = []
    for label, vp in vids:
        vname = os.path.basename(vp)
        vid_uri = _media_uri(vp, out_html, embed_video=embed_video)
        sz_mb = round(os.path.getsize(vp) / (1024 * 1024), 2)
        ico = "🏆" if label == "Master" else "✂️"
        cards.append(
            f"<div class='sb-card'>"
            f"<div class='sb-hdr'><strong>{ico} {H.escape(vname)}</strong><div><span class='badge b-purple'>{label}</span> <span class='badge b-blue'>{sz_mb} MB</span></div></div>"
            f"<video class='vid-player' controls playsinline preload='metadata' src='{vid_uri}'></video>"
            f"</div>"
        )
    return f"<div class='sb-grid'>{''.join(cards)}</div>"


def _wrap_page(title, subtitle, body_html, tabs_html="", progress_pct=None, status_default="Add notes or votes — auto-applied on next roll", initial_notes=None):
    init_json = json.dumps(initial_notes or {})
    prog_html = ""
    if progress_pct is not None:
        prog_html = (
            f"<div class='prog-wrap'>"
            f"<div class='prog-track'><div class='prog-fill' style='width:{progress_pct}%'></div></div>"
            f"<div class='prog-pct'>{progress_pct}% Complete</div>"
            f"</div>"
        )
    all_btn = "<button class='ghost-btn' id='allInOneBtn' onclick='toggleAllInOne()'>↕ Show All on One Page</button>" if tabs_html else ""
    js = f"""
document.addEventListener('play', function(e) {{
  document.querySelectorAll('video').forEach(function(v) {{ if (v !== e.target) v.pause(); }});
}}, true);
const directorNotes = {init_json};
function recordNote(target, comment) {{
  directorNotes[target] = directorNotes[target] || {{}};
  directorNotes[target].comment = comment;
  refreshPill();
}}
function sbVote(target, status, btn) {{
  directorNotes[target] = directorNotes[target] || {{}};
  directorNotes[target].status = status;
  const card = btn.closest('.sb-card');
  card.classList.remove('approved', 'flagged');
  card.classList.add(status === 'approved' ? 'approved' : 'flagged');
  refreshPill();
  persistNotes(true);
}}
function refreshPill() {{
  const entries = Object.entries(directorNotes).filter(([,v]) => (v.comment && v.comment.trim()) || v.status);
  document.getElementById('statusPill').textContent = entries.length
    ? entries.length + ' Director note(s) staged'
    : 'Ready for Director review';
}}
async function persistNotes(silent) {{
  const pill = document.getElementById('statusPill');
  try {{
    if (location.protocol.startsWith('http')) {{
      const r = await fetch('/api/notes', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{notes: directorNotes}})}});
      if (r.ok) {{ pill.textContent = '✅ Saved to director_notes.json'; return; }}
    }}
  }} catch (e) {{}}
  if (silent) return;
  const blob = new Blob([JSON.stringify({{notes: directorNotes}}, null, 2)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'director_notes.json';
  a.click();
  pill.textContent = 'Downloaded director_notes.json (place in production/callsheets/)';
}}
function showTab(id, btn) {{
  document.body.classList.remove('all-in-one');
  const ab = document.getElementById('allInOneBtn');
  if (ab) ab.textContent = '↕ Show All on One Page';
  document.querySelectorAll('video').forEach(v => v.pause());
  document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
  const pane = document.getElementById('pane-' + id);
  if (pane) pane.style.display = 'block';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
}}
function toggleAllInOne() {{
  const on = document.body.classList.toggle('all-in-one');
  const ab = document.getElementById('allInOneBtn');
  if (ab) ab.textContent = on ? '🗂 Tabbed View' : '↕ Show All on One Page';
}}
"""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>{H.escape(title)}</title>"
        f"<style>{SHARED_CSS}</style></head><body>"
        f"<div class='topbar'><div class='top-row'><div class='title-grp'><h1>🎬 {H.escape(title)}</h1><div class='sub'>{H.escape(subtitle)}</div></div>"
        f"{tabs_html}<div class='top-right'>{all_btn}<div class='status-pill' id='statusPill'>{H.escape(status_default)}</div>"
        f"<button class='save-btn' onclick='persistNotes(false)'>💾 Save Notes</button></div></div>{prog_html}</div>"
        f"{body_html}<script>{js}</script></body></html>"
    )


def build_script_board(breakdown_path, out_html=None, callsheets_dir=None):
    with open(breakdown_path, encoding="utf-8") as f:
        bd = json.load(f)
    cs_dir = callsheets_dir or os.path.dirname(os.path.abspath(breakdown_path))
    prod_dir = os.path.dirname(os.path.abspath(cs_dir.rstrip("/")))
    notes = provenance.load_notes(prod_dir).get("notes", {})
    cs_map = {}
    for p in glob.glob(os.path.join(cs_dir, "*.callsheet.json")):
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
            cs_map[c.get("scene", "")] = c
    out_html = out_html or os.path.splitext(breakdown_path)[0] + "_board.html"
    html = _wrap_page(f"Script Breakdown — {bd.get('episode','EP01')}", breakdown_path, render_script_section(bd, cs_map, notes), initial_notes=notes)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    return out_html


def build_screenplay_board(script_path, out_html=None, shotlist_paths=None):
    with open(script_path, encoding="utf-8") as f:
        txt = f.read()
    sls = []
    for p in (shotlist_paths or []):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                sls.append(json.load(f))
    out_html = out_html or os.path.splitext(script_path)[0] + "_screenplay.html"
    html = _wrap_page("Screenplay & Subtext Notes", os.path.basename(script_path), render_screenplay_section(txt, sls))
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    return out_html


def build_storyboard_board(shotlist_paths, out_html, dailies_root=None, production_dir=None, embed=False):
    sls = []
    for p in shotlist_paths:
        with open(p, encoding="utf-8") as f:
            sls.append(json.load(f))
    prod = production_dir or os.path.dirname(os.path.dirname(os.path.abspath(shotlist_paths[0])))
    notes = provenance.load_notes(prod).get("notes", {})
    title = f"Storyboard — {sls[0].get('scene','')}" if len(sls) == 1 else f"Storyboard ({len(sls)} scenes)"
    html = _wrap_page(
        title,
        "Add comments or Approve/Revise — comments compile directly into camera prompts",
        render_storyboard_section(sls, out_html, dailies_root=dailies_root, production_dir=prod, existing_notes=notes, embed=embed),
        initial_notes=notes,
    )
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    return out_html


def build_hub(production_dir, episode="EP01", script_path=None, out_html=None, embed=False, embed_video=False):
    cs_dir = os.path.join(production_dir, "callsheets")
    dailies_root = os.path.join(production_dir, "dailies")
    out_html = out_html or os.path.join(production_dir, "studio_hub.html")
    notes = provenance.load_notes(production_dir).get("notes", {})

    # Auto-detect episode if EP01_breakdown.json doesn't exist yet
    bd_candidates = sorted(glob.glob(os.path.join(cs_dir, "*_breakdown.json")))
    if not os.path.exists(os.path.join(cs_dir, f"{episode}_breakdown.json")) and bd_candidates:
        episode = os.path.basename(bd_candidates[0]).split("_breakdown.json")[0]

    bd_path = os.path.join(cs_dir, f"{episode}_breakdown.json")
    bd = json.load(open(bd_path, encoding="utf-8")) if os.path.exists(bd_path) else {"episode": episode, "scenes": []}
    cs_map = {}
    for p in sorted(glob.glob(os.path.join(cs_dir, "*.callsheet.json"))):
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
            cs_map[c.get("scene", "")] = c
    sls = []
    for p in sorted(glob.glob(os.path.join(cs_dir, "*.shotlist.json"))):
        with open(p, encoding="utf-8") as f:
            sls.append(json.load(f))

    if script_path and os.path.exists(script_path):
        with open(script_path, encoding="utf-8") as f:
            sp_txt = f.read()
    else:
        chunks = []
        for p in sorted(glob.glob(os.path.join(cs_dir, f"{episode}_SC*.md"))):
            with open(p, encoding="utf-8") as f:
                chunks.append(f.read())
        sp_txt = "\n\n".join(chunks) or "No script loaded yet."

    state = compute_production_state(production_dir, episode, bd, cs_map, sls)
    st_by_id = {s["id"]: STATUS_ICON[s["state"]] for s in state["stages"]}

    tabs = (
        "<div class='tabs'>"
        f"<button class='tab-btn active' data-tab='overview' onclick=\"showTab('overview',this)\">📊 Overview</button>"
        f"<button class='tab-btn' data-tab='script' onclick=\"showTab('script',this)\">{st_by_id['script']} 1. Script</button>"
        f"<button class='tab-btn' data-tab='screenplay' onclick=\"showTab('screenplay',this)\">📝 2. Screenplay</button>"
        f"<button class='tab-btn' data-tab='storyboard' onclick=\"showTab('storyboard',this)\">{st_by_id['storyboard']} 3. Storyboard</button>"
        f"<button class='tab-btn' data-tab='dailies' onclick=\"showTab('dailies',this)\">{st_by_id['dailies']} 4. Dailies (Video)</button>"
        f"<button class='tab-btn' data-tab='cuts' onclick=\"showTab('cuts',this)\">{st_by_id['master']} 5. Cuts & Masters</button>"
        "</div>"
    )
    body = (
        f"<div id='pane-overview' class='tab-pane'><div class='pane-section-label'>📊 Production Overview & Status</div>{render_overview_section(state, out_html, embed=embed)}</div>"
        f"<div id='pane-script' class='tab-pane' style='display:none'><div class='pane-section-label'>📜 1. Script Breakdown</div>{render_script_section(bd, cs_map, notes)}</div>"
        f"<div id='pane-screenplay' class='tab-pane' style='display:none'><div class='pane-section-label'>📝 2. Screenplay & Subtext</div>{render_screenplay_section(sp_txt, sls)}</div>"
        f"<div id='pane-storyboard' class='tab-pane' style='display:none'><div class='pane-section-label'>🎬 3. Storyboard & Prompts</div>{render_storyboard_section(sls, out_html, dailies_root=dailies_root, production_dir=production_dir, existing_notes=notes, embed=embed)}</div>"
        f"<div id='pane-dailies' class='tab-pane' style='display:none'><div class='pane-section-label'>🎥 4. Dailies Screening Room</div>{render_dailies_section(production_dir, episode, out_html, existing_notes=notes, embed=embed, embed_video=embed_video)}</div>"
        f"<div id='pane-cuts' class='tab-pane' style='display:none'><div class='pane-section-label'>🏆 5. Cuts & Delivered Masters</div>{render_cuts_section(production_dir, episode, out_html, embed_video=embed_video)}</div>"
    )
    show_json = os.path.join(production_dir, "show.json")
    show_title = json.load(open(show_json, encoding="utf-8")).get("title", "AI Studio Crew") if os.path.exists(show_json) else "AI Studio Crew"
    subtitle = f"{episode} · Updated {time.strftime('%F %H:%M:%S')} · Single-page Studio Command Center"
    html = _wrap_page(f"{show_title} — Studio Hub", subtitle, body, tabs_html=tabs, progress_pct=state["overall_pct"], initial_notes=notes)
    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    # Also maintain EPxx_studio_hub.html alias if writing default studio_hub.html
    ep_alias = os.path.join(production_dir, f"{episode}_studio_hub.html")
    if os.path.abspath(out_html) != os.path.abspath(ep_alias) and os.path.dirname(os.path.abspath(out_html)) == os.path.abspath(production_dir):
        with open(ep_alias, "w", encoding="utf-8") as f:
            f.write(html)
    return out_html


def refresh_hub(production_dir="production", episode="EP01", script_path=None):
    """Best-effort helper called by pipeline scripts so production/studio_hub.html stays live after every step."""
    try:
        if os.path.isdir(production_dir):
            return build_hub(production_dir, episode=episode, script_path=script_path)
    except Exception:
        pass
    return None


def serve_hub(production_dir, episode="EP01", script_path=None, port=8765):
    prod_abs = os.path.abspath(production_dir)
    hub_path = build_hub(prod_abs, episode=episode, script_path=script_path)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=prod_abs, **kwargs)

        def do_GET(self):
            if self.path in ("/", "/index.html", "/studio_hub.html"):
                build_hub(prod_abs, episode=episode, script_path=script_path, out_html=hub_path)
                self.path = "/" + os.path.relpath(hub_path, prod_abs)
            return super().do_GET()

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path == "/api/notes":
                ln = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(ln).decode("utf-8") or "{}")
                saved = provenance.save_notes_bulk(prod_abs, payload.get("notes", {}))
                out = json.dumps({"status": "ok", "count": len(saved.get("notes", {}))}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            self.send_error(404)

        def log_message(self, fmt, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Studio Hub live at http://127.0.0.1:{port} (saving notes to {provenance.notes_path(prod_abs)})")
    srv.serve_forever()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sc = sub.add_parser("script")
    p_sc.add_argument("--breakdown", required=True)
    p_sc.add_argument("--callsheets-dir")
    p_sc.add_argument("--out")

    p_sp = sub.add_parser("screenplay")
    p_sp.add_argument("--script", required=True)
    p_sp.add_argument("--shotlists", nargs="*", default=[])
    p_sp.add_argument("--out")

    p_sb = sub.add_parser("storyboard")
    p_sb.add_argument("--shotlist", nargs="+", required=True)
    p_sb.add_argument("--dailies")
    p_sb.add_argument("--out", required=True)
    p_sb.add_argument("--embed", action="store_true")

    p_hb = sub.add_parser("hub")
    p_hb.add_argument("--production", default="production")
    p_hb.add_argument("--episode", default="EP01")
    p_hb.add_argument("--script")
    p_hb.add_argument("--out")
    p_hb.add_argument("--embed", action="store_true")
    p_hb.add_argument("--embed-video", action="store_true")

    p_sv = sub.add_parser("serve")
    p_sv.add_argument("--production", default="production")
    p_sv.add_argument("--episode", default="EP01")
    p_sv.add_argument("--script")
    p_sv.add_argument("--port", type=int, default=8765)

    a = ap.parse_args()
    if a.cmd == "script":
        print(build_script_board(a.breakdown, out_html=a.out, callsheets_dir=a.callsheets_dir))
    elif a.cmd == "screenplay":
        print(build_screenplay_board(a.script, out_html=a.out, shotlist_paths=a.shotlists))
    elif a.cmd == "storyboard":
        print(build_storyboard_board(a.shotlist, a.out, dailies_root=a.dailies, embed=a.embed))
    elif a.cmd == "hub":
        print(build_hub(a.production, episode=a.episode, script_path=a.script, out_html=a.out, embed=a.embed, embed_video=a.embed_video))
    elif a.cmd == "serve":
        serve_hub(a.production, episode=a.episode, script_path=a.script, port=a.port)


if __name__ == "__main__":
    main()
