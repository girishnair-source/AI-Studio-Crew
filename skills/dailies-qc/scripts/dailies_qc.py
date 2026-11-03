#!/usr/bin/env python3
"""dailies_qc.py — inspect clips without loading video into chat.

  dailies_qc.py contact --video 4A_take1.mp4 [--frames 5] [--out 4A_take1_contact.png]
  dailies_qc.py speech  --video 4A_take1.mp4 [--floor -38] [--hold 0.45]      # speech end, margin, flags
  dailies_qc.py last    --video 4A_take1.mp4 [--out 4A_take1_last.png]
  dailies_qc.py scene   --dir production/dailies/EP01_SC04                    # all takes -> qc.json + contacts + last frames
"""
import argparse, glob, json, os, re, subprocess

def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode())

def contact(video, frames=5, out=None):
    d = dur(video); fps = 24
    idx = [int(fps * d * (i + .5) / frames) for i in range(frames)]
    sel = "+".join(f"eq(n,{i})" for i in idx)
    out = out or os.path.splitext(video)[0] + "_contact.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", f"select='{sel}',scale=216:-1,tile={frames}x1", "-frames:v", "1", out], check=True)
    return out

def last(video, out=None):
    out = out or os.path.splitext(video)[0] + "_last.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", out], check=True)
    return out

def speech(video, floor=-38.0, hold=0.45, step=0.05):
    tmp = video + ".rms.txt"
    subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", video, "-af",
                    f"highpass=f=200,lowpass=f=4000,asetnsamples={int(48000*step)},astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file={tmp}", "-f", "null", "-"], check=True)
    v = [float(m.group(1)) if m.group(1) != "-inf" else -99 for l in open(tmp) for m in [re.search(r"RMS_level=(-?[\d.]+|-inf)", l)] if m]
    os.remove(tmp)
    d = dur(video)
    speaking = [i for i, x in enumerate(v) if x > floor]
    if not speaking:
        return {"duration": round(d, 2), "has_speech": False, "speech_start": None, "speech_end": None, "margin": None, "flags": ["no-speech"]}
    s, e = speaking[0] * step, (speaking[-1] + 1) * step
    margin = round(d - e, 2); flags = []
    if margin < 0.3: flags.append("speech-clipped-at-end")
    if s < 0.15: flags.append("speech-starts-at-zero")
    # clipping / peaks
    peak = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", video, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+) dB", peak); mx = float(m.group(1)) if m else None
    if mx is not None and mx > -0.5: flags.append("audio-peaks-hot")
    return {"duration": round(d, 2), "has_speech": True, "speech_start": round(s, 2), "speech_end": round(e, 2), "margin": margin,
            "trim_to": round(min(d, e + hold), 2), "max_volume_db": mx, "flags": flags}

def scene(d):
    rep = {}
    for v in sorted(glob.glob(os.path.join(d, "*.mp4"))):
        name = os.path.basename(v)
        rep[name] = speech(v); rep[name]["contact"] = contact(v); rep[name]["last_frame"] = last(v)
    json.dump(rep, open(os.path.join(d, "qc.json"), "w"), indent=2)
    for k, r in rep.items():
        print(f"{k:28s} {r['duration']:5.1f}s  speech_end={r.get('speech_end')}  margin={r.get('margin')}  flags={r['flags']}")
    return rep

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("contact", "speech", "last"):
        s = sub.add_parser(c); s.add_argument("--video", required=True); s.add_argument("--out")
        if c == "contact": s.add_argument("--frames", type=int, default=5)
        if c == "speech": s.add_argument("--floor", type=float, default=-38.0); s.add_argument("--hold", type=float, default=0.45)
    s = sub.add_parser("scene"); s.add_argument("--dir", required=True)
    a = ap.parse_args()
    if a.cmd == "contact": print(contact(a.video, a.frames, a.out))
    elif a.cmd == "last": print(last(a.video, a.out))
    elif a.cmd == "speech": print(json.dumps(speech(a.video, a.floor, a.hold), indent=2))
    else: scene(a.dir)

if __name__ == "__main__":
    main()
