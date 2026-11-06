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

PROSODY_PROFILES = {"presenter": (4.5, 3.0), "dialogue": (3.0, 1.8), "narration": (3.5, 2.2), "cold": (2.0, 1.0)}

def prosody(video, profile="dialogue"):
    """Monotony estimate: autocorrelation pitch (f0) on voiced frames -> f0 std in semitones; pace = voiced-run rate variance.
    ffmpeg + numpy only. Thresholds tuned on known-flat vs known-performed clips (see SKILL.md)."""
    try:
        import numpy as np
    except Exception:
        return {}
    sr = 16000
    raw = subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", video, "-vn", "-ac", "1", "-ar", str(sr), "-af", "highpass=f=70,lowpass=f=1200", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < sr: return {}
    win, hop = 640, 160  # 40ms / 10ms
    fmin, fmax = 70, 400; lag_min, lag_max = sr // fmax, sr // fmin
    f0s, voiced = [], []
    for i in range(0, len(x) - win, hop):
        f = x[i:i + win]; e = float(np.sqrt(np.mean(f ** 2)))
        if e < 0.008: voiced.append(0); continue
        f = f - f.mean(); ac = np.correlate(f, f, "full")[win - 1:]; ac /= (ac[0] + 1e-9)
        seg = ac[lag_min:lag_max]; k = int(np.argmax(seg)); peak = float(seg[k])
        if peak < 0.5: voiced.append(0); continue
        voiced.append(1); f0s.append(sr / (lag_min + k))
    if len(f0s) < 30: return {}
    f0 = np.array(f0s); st = 12 * np.log2(f0 / np.median(f0))
    st = st[np.abs(st) < 12]  # drop octave errors
    f0_std = float(np.std(st))
    # pace variance: lengths of voiced runs (approx syllable groups) in 10ms frames
    runs, cur = [], 0
    for v in voiced:
        if v: cur += 1
        elif cur: runs.append(cur); cur = 0
    runs = np.array(runs) if runs else np.array([1])
    pace_cv = float(np.std(runs) / (np.mean(runs) + 1e-9))
    # phrase-level contour: std of per-second median pitch (slow intonation movement)
    sec = max(1, int(sr / hop))
    per_sec = [np.median(st[i:i + sec]) for i in range(0, len(st), sec) if len(st[i:i + sec]) > 5]
    contour_std = float(np.std(per_sec)) if len(per_sec) > 2 else 0.0
    t_f0, t_contour = PROSODY_PROFILES.get(profile, PROSODY_PROFILES["dialogue"])
    monotone = bool(f0_std < t_f0 or contour_std < t_contour)
    return {"f0_std_semitones": round(f0_std, 2), "contour_std_semitones": round(contour_std, 2), "pace_cv": round(pace_cv, 2), "prosody_profile": profile, "monotone": monotone}

def speech(video, floor=-38.0, hold=0.45, step=0.05, profile="dialogue"):
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
    pro = prosody(video, profile)
    if pro.get("monotone"): flags.append("monotone-read")
    return {"duration": round(d, 2), "has_speech": True, "speech_start": round(s, 2), "speech_end": round(e, 2), "margin": margin,
            "trim_to": round(min(d, e + hold), 2), "max_volume_db": mx, **pro, "flags": flags}

def scene(d, profile="dialogue"):
    rep = {}
    for v in sorted(glob.glob(os.path.join(d, "*.mp4"))):
        name = os.path.basename(v)
        rep[name] = speech(v, profile=profile); rep[name]["contact"] = contact(v); rep[name]["last_frame"] = last(v)
    json.dump(rep, open(os.path.join(d, "qc.json"), "w"), indent=2)
    for k, r in rep.items():
        print(f"{k:28s} {r['duration']:5.1f}s  speech_end={r.get('speech_end')}  margin={r.get('margin')}  flags={r['flags']}")
    return rep

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("contact", "speech", "last"):
        s = sub.add_parser(c); s.add_argument("--video", required=True); s.add_argument("--out")
        if c == "contact": s.add_argument("--frames", type=int, default=5)
        if c == "speech": s.add_argument("--floor", type=float, default=-38.0); s.add_argument("--hold", type=float, default=0.45); s.add_argument("--profile", default="dialogue", choices=list(PROSODY_PROFILES))
    s = sub.add_parser("scene"); s.add_argument("--dir", required=True); s.add_argument("--profile", default="dialogue", choices=list(PROSODY_PROFILES))
    a = ap.parse_args()
    if a.cmd == "contact": print(contact(a.video, a.frames, a.out))
    elif a.cmd == "last": print(last(a.video, a.out))
    elif a.cmd == "speech": print(json.dumps(speech(a.video, a.floor, a.hold, profile=a.profile), indent=2))
    else: scene(a.dir, a.profile)

if __name__ == "__main__":
    main()
