#!/usr/bin/env python3
"""assemble.py — Editor's assembly from a cut sheet (JSON). v2: render cache (locality), transitions-as-sentences,
eased captions, punch-ins, J-cut audio lead.

  assemble.py --cut cut.json --out production/cuts/EP01_v2.mp4 [--otio] [--no-cache]

cut.json:
{
  "fps": 24, "width": 720, "height": 1280, "font": "...DejaVuSans-Bold.ttf",
  "clips": [
    {"src": "../dailies/EP01_SC04/4A_take1.mp4", "in": 0, "out": "speech",          # "speech" -> qc.json trim_to
     "transition": "cut",                                                             # cut | dissolve | fade_black  (meaning-gated)
     "transition_s": 0.5, "time_passed": false,
     "audio_lead_s": 0.0,                                                             # J-cut: this clip's audio starts early under the previous clip
     "punch_in": {"at": 3.2, "to": 1.12, "dur": 0.25},                               # eased zoom landing on the stressed word
     "fade_audio_out": 0.15,
     "overlays": [{"text": "0 cameras. 1 sentence.", "y": 1040, "size": 44, "from": 0.6, "to": 13.0, "ease": true}]},
    {"black": 0.5}
  ]
}
Transitions are sentences: `dissolve` only with `time_passed: true`; `fade_black` only on the last clip or with `ended: true`.
Otherwise it is downgraded to a cut and reported (format-craft/editor-craft).
Writes <out>, <out>.edl, <out>.otio (--otio) and <out>.changes.json (what was re-rendered vs reused).
"""
import argparse, hashlib, json, os, subprocess

def esc(s): return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())

def resolve_out(clip, base):
    if clip.get("out") == "speech":
        qc = os.path.join(os.path.dirname(os.path.join(base, clip["src"])), "qc.json")
        if os.path.exists(qc):
            r = json.load(open(qc)).get(os.path.basename(clip["src"]))
            if r and r.get("trim_to"): return float(r["trim_to"])
        return dur(os.path.join(base, clip["src"]))
    return float(clip.get("out") or dur(os.path.join(base, clip["src"])))

def gate_transition(i, c, n, warnings):
    t = c.get("transition", "cut")
    if t == "dissolve" and not c.get("time_passed"):
        warnings.append(f"clip {i}: dissolve without time_passed=true → cut (a dissolve says time passed)"); return "cut"
    if t == "fade_black" and not (c.get("ended") or i == n - 1):
        warnings.append(f"clip {i}: fade_black mid-piece without ended=true → cut (a fade to black says it ended)"); return "cut"
    return t

def smooth(t0, t1):
    """smoothstep(t) between t0..t1 as an ffmpeg expression (commas escaped for use inside drawtext options)."""
    u = f"((t-{t0:.4f})/({t1 - t0:.4f}))"
    return f"if(lt(t\\,{t0:.4f})\\,0\\,if(gt(t\\,{t1:.4f})\\,1\\,{u}*{u}*(3-2*{u})))"

def build_part(c, base, fps, W, H, font, ln, tin, src, out):
    vf = [f"fps={fps}", f"scale={W}:{H}:force_original_aspect_ratio=decrease", f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
    pi = c.get("punch_in")
    if pi:
        at, to, d = float(pi["at"]), float(pi.get("to", 1.1)), float(pi.get("dur", 0.25))
        f0, f1 = int(at * fps), int((at + d) * fps)
        u = f"((on-{f0})/{max(1, f1 - f0)})"
        zexpr = f"if(lt(on\,{f0})\,1\,if(gt(on\,{f1})\,{to}\,1+({to}-1)*{u}*{u}*(3-2*{u})))"
        vf.append(f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}")
    vf.append("format=yuv420p")
    for o in c.get("overlays", []):
        f0, f1 = float(o.get("from", 0)), float(o.get("to", ln)); size = o.get("size", 44); y = o.get("y", 1040)
        if o.get("ease", True):
            ein, eout = 8 / fps, 5 / fps
            alpha = f"if(lt(t\\,{f0+ein:.4f})\\,{smooth(f0, f0+ein)}\\,if(lt(t\\,{f1-eout:.4f})\\,1\\,1-({smooth(f1-eout, f1)})))"
            yexpr = f"{y}+6*(1-({smooth(f0, f0+ein)}))"
            vf.append(f"drawtext=fontfile={font}:text='{esc(o['text'])}':fontsize={size}:fontcolor={o.get('color','white')}:alpha='{alpha}':borderw=3:bordercolor=black@0.85:"
                      f"box=1:boxcolor=black@0.35:boxborderw=14:x=(w-text_w)/2:y='{yexpr}':enable='between(t,{f0},{f1})'")
        else:
            vf.append(f"drawtext=fontfile={font}:text='{esc(o['text'])}':fontsize={size}:fontcolor={o.get('color','white')}:borderw=3:bordercolor=black@0.85:box=1:boxcolor=black@0.35:boxborderw=14:x=(w-text_w)/2:y={y}:enable='between(t,{f0},{f1})'")
    af = ["aformat=sample_rates=48000:channel_layouts=stereo"]
    if c.get("fade_audio_in"): af.append(f"afade=t=in:st=0:d={c['fade_audio_in']}")
    if c.get("fade_audio_out"): af.append(f"afade=t=out:st={max(0, ln - c['fade_audio_out']):.3f}:d={c['fade_audio_out']}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(tin), "-i", src, "-t", f"{ln:.3f}", "-vf", ",".join(vf), "-af", ",".join(af),
                    "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out], check=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cut", required=True); ap.add_argument("--out", required=True); ap.add_argument("--otio", action="store_true"); ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    cut = json.load(open(a.cut)); base = os.path.dirname(os.path.abspath(a.cut))
    fps, W, H = cut.get("fps", 24), cut.get("width", 720), cut.get("height", 1280)
    font = cut.get("font", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    cache = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".cache"); os.makedirs(cache, exist_ok=True)
    parts, edl, warnings, changes, t_acc = [], [], [], [], 0.0
    n = len(cut["clips"])
    for i, c in enumerate(cut["clips"]):
        if "black" in c:
            key = hashlib.sha1(json.dumps({"black": c["black"], "W": W, "H": H, "fps": fps}, sort_keys=True).encode()).hexdigest()[:16]
            p = os.path.join(cache, f"black_{key}.mp4")
            if a.no_cache or not os.path.exists(p):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(c["black"]), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p], check=True); changes.append(f"black@{i}")
            parts.append({"path": p, "transition": gate_transition(i, c, n, warnings), "tr_s": float(c.get("transition_s", 0.5)), "len": float(c["black"]), "lead": 0.0}); t_acc += float(c["black"]); continue
        src = os.path.join(base, c["src"]); tin = float(c.get("in", 0)); tout = resolve_out(c, base); ln = tout - tin
        tr = gate_transition(i, c, n, warnings)
        spec = {k: v for k, v in c.items() if k not in ("transition", "transition_s", "time_passed", "ended", "audio_lead_s")}
        spec.update(W=W, H=H, fps=fps, font=font, tin=tin, tout=tout, srcmtime=os.path.getmtime(src))
        key = hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]
        p = os.path.join(cache, f"part_{key}.mp4")
        if a.no_cache or not os.path.exists(p):
            build_part(c, base, fps, W, H, font, ln, tin, src, p); changes.append(c["src"])
        parts.append({"path": p, "transition": tr, "tr_s": float(c.get("transition_s", 0.5)), "len": ln, "lead": float(c.get("audio_lead_s", 0))})
        edl.append({"n": len(edl) + 1, "src": c["src"], "src_in": tin, "src_out": tout, "rec_in": t_acc, "rec_out": t_acc + ln, "transition": tr}); t_acc += ln
    # Sequential merge: fold parts left-to-right. Each step merges the running timeline with the next part
    # (plain concat, J-cut concat with audio lead, or xfade/acrossfade). Keeps every ffmpeg graph small and timing-safe.
    run_path = parts[0]["path"]; total = parts[0]["len"]
    for k in range(1, len(parts)):
        p = parts[k]; tr = p["transition"]; nxt = os.path.join(cache, f"run_{k}_{hashlib.sha1((run_path + p['path'] + tr).encode()).hexdigest()[:10]}.mp4")
        if not os.path.exists(nxt) or a.no_cache:
            if tr in ("dissolve", "fade_black"):
                d = max(0.1, min(p["tr_s"], total / 2, p["len"] / 2))
                fcs = (f"[0:v][1:v]xfade=transition={'fade' if tr=='dissolve' else 'fadeblack'}:duration={d:.3f}:offset={total - d:.3f}[v];"
                       f"[0:a][1:a]acrossfade=d={d:.3f}:c1=tri:c2=tri[a]")
            else:
                lead = max(0.0, min(p["lead"], total / 2))
                if lead > 0:
                    ms = int((total - lead) * 1000)
                    fcs = (f"[0:v][1:v]concat=n=2:v=1:a=0[v];[1:a]adelay={ms}|{ms}[na];"
                           f"[0:a]apad=whole_dur={total + p['len'] - lead:.3f}[pa];[pa][na]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,atrim=0:{total + p['len']:.3f}[a]")
                else:
                    fcs = "[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a][1:a]concat=n=2:v=0:a=1[a]"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-i", p["path"], "-filter_complex", fcs, "-map", "[v]", "-map", "[a]",
                            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", nxt], check=True)
        total += p["len"] - (max(0.1, min(p["tr_s"], total / 2, p["len"] / 2)) if tr in ("dissolve", "fade_black") else 0.0)
        run_path = nxt
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-c", "copy", "-movflags", "+faststart", a.out], check=True)
    def tc(s): f = int(round((s % 1) * fps)); s = int(s); return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}:{f:02d}"
    with open(a.out + ".edl", "w") as f:
        f.write(f"TITLE: {os.path.basename(a.out)}\nFCM: NON-DROP FRAME\n\n")
        for e in edl: f.write(f"{e['n']:03d}  AX       AA/V  {'D' if e['transition']!='cut' else 'C'}        {tc(e['src_in'])} {tc(e['src_out'])} {tc(e['rec_in'])} {tc(e['rec_out'])}\n* FROM CLIP NAME: {os.path.basename(e['src'])}\n\n")
    if a.otio:
        otio = {"OTIO_SCHEMA": "Timeline.1", "name": os.path.basename(a.out), "tracks": {"OTIO_SCHEMA": "Stack.1", "children": [{"OTIO_SCHEMA": "Track.1", "kind": "Video", "children": [
            {"OTIO_SCHEMA": "Clip.1", "name": os.path.basename(e["src"]), "source_range": {"OTIO_SCHEMA": "TimeRange.1", "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": e["src_in"] * fps},
             "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": (e["src_out"] - e["src_in"]) * fps}}, "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": os.path.abspath(os.path.join(base, e["src"]))}} for e in edl]}]}}
        json.dump(otio, open(a.out + ".otio", "w"), indent=1)
    json.dump({"re_rendered": changes, "reused": len(parts) - len(changes), "warnings": warnings}, open(a.out + ".changes.json", "w"), indent=1)
    print(json.dumps({"out": a.out, "duration": round(total, 2), "clips": len(edl), "re_rendered": len(changes), "reused": len(parts) - len(changes), "warnings": warnings}))

if __name__ == "__main__":
    main()
