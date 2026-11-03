#!/usr/bin/env python3
"""assemble.py — Editor's assembly from a cut sheet (JSON).

  assemble.py --cut cut.json --out production/cuts/EP01_v1.mp4 [--otio]

cut.json:
{
  "fps": 24, "width": 720, "height": 1280,
  "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
  "clips": [
    {"src": "dailies/EP01_SC04/4A_take1.mp4", "in": 0, "out": 13.4,          # out may be "speech" -> use qc.json trim_to
     "fade_audio_out": 0.15,
     "overlays": [{"text": "0 cameras. 1 sentence.", "y": 1040, "size": 44, "from": 0.6, "to": 13.0}]},
    {"src": "...", "in": 0, "out": "speech"},
    {"black": 0.5}
  ]
}
Writes <out>, <out>.edl and (with --otio) <out>.otio (minimal OTIO JSON, importable by Resolve).
"""
import argparse, json, os, subprocess, sys

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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cut", required=True); ap.add_argument("--out", required=True); ap.add_argument("--otio", action="store_true")
    a = ap.parse_args()
    cut = json.load(open(a.cut)); base = os.path.dirname(os.path.abspath(a.cut))
    fps, W, H = cut.get("fps", 24), cut.get("width", 720), cut.get("height", 1280)
    font = cut.get("font", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    scratch = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".scratch"); os.makedirs(scratch, exist_ok=True)
    parts, edl, t_acc = [], [], 0.0
    for i, c in enumerate(cut["clips"]):
        p = os.path.join(scratch, f"part_{i:02d}.mp4")
        if "black" in c:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                            "-t", str(c["black"]), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p], check=True)
            parts.append(p); t_acc += float(c["black"]); continue
        src = os.path.join(base, c["src"]); tin = float(c.get("in", 0)); tout = resolve_out(c, base); ln = tout - tin
        vf = [f"fps={fps}", f"scale={W}:{H}:force_original_aspect_ratio=decrease", f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2", "format=yuv420p"]
        for o in c.get("overlays", []):
            vf.append(f"drawtext=fontfile={font}:text='{esc(o['text'])}':fontsize={o.get('size',44)}:fontcolor={o.get('color','white')}:borderw=3:bordercolor=black@0.85:"
                      f"box=1:boxcolor=black@0.35:boxborderw=14:x=(w-text_w)/2:y={o.get('y',1040)}:enable='between(t,{o.get('from',0)},{o.get('to',ln)})'")
        af = []
        if c.get("fade_audio_in"): af.append(f"afade=t=in:st=0:d={c['fade_audio_in']}")
        if c.get("fade_audio_out"): af.append(f"afade=t=out:st={max(0, ln - c['fade_audio_out']):.3f}:d={c['fade_audio_out']}")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(tin), "-i", src, "-t", f"{ln:.3f}", "-vf", ",".join(vf)]
        if af: cmd += ["-af", ",".join(af)]
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", p]
        subprocess.run(cmd, check=True); parts.append(p)
        edl.append({"n": len(edl) + 1, "src": c["src"], "src_in": tin, "src_out": tout, "rec_in": t_acc, "rec_out": t_acc + ln}); t_acc += ln
    lst = os.path.join(scratch, "concat.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
    # EDL (CMX3600-ish)
    def tc(s): f = int(round((s % 1) * fps)); s = int(s); return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}:{f:02d}"
    with open(a.out + ".edl", "w") as f:
        f.write(f"TITLE: {os.path.basename(a.out)}\nFCM: NON-DROP FRAME\n\n")
        for e in edl:
            f.write(f"{e['n']:03d}  AX       AA/V  C        {tc(e['src_in'])} {tc(e['src_out'])} {tc(e['rec_in'])} {tc(e['rec_out'])}\n* FROM CLIP NAME: {os.path.basename(e['src'])}\n\n")
    if a.otio:
        otio = {"OTIO_SCHEMA": "Timeline.1", "name": os.path.basename(a.out), "tracks": {"OTIO_SCHEMA": "Stack.1", "children": [{"OTIO_SCHEMA": "Track.1", "kind": "Video", "children": [
            {"OTIO_SCHEMA": "Clip.1", "name": os.path.basename(e["src"]),
             "source_range": {"OTIO_SCHEMA": "TimeRange.1", "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": e["src_in"] * fps},
                              "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": (e["src_out"] - e["src_in"]) * fps}},
             "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": os.path.abspath(os.path.join(base, e["src"]))}} for e in edl]}]}}
        json.dump(otio, open(a.out + ".otio", "w"), indent=1)
    print(json.dumps({"out": a.out, "duration": round(t_acc, 2), "clips": len(edl), "edl": a.out + ".edl", "otio": a.out + ".otio" if a.otio else None}))

if __name__ == "__main__":
    main()
