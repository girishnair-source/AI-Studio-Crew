#!/usr/bin/env python3
"""lyria_cue.py — render a score cue with Lyria 3 Pro and find the best window.

  lyria_cue.py render --brief "..." --out production/music/EP01/cue_signal_full.mp3
  lyria_cue.py map    --audio cue_full.mp3                   # RMS per second + detected drops/hits
  lyria_cue.py cut    --audio cue_full.mp3 --start 39.5 --len 20 --out cue_20s.mp3 [--fade-in 0.5 --fade-out 1.5]

Auth/project: reuses camera_roll.get_token and CONFIG lane 'prod' project (Lyria is prod-only).
Prompt rules: no artist/track names (refused as prohibited_content). Describe sections with timings.
"""
import argparse, base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "camera-roll", "scripts"))
from camera_roll import get_token, CONFIG  # noqa: E402

MODEL = os.environ.get("LYRIA_MODEL", "lyria-3-pro-preview")

def render(brief, out, project=None):
    project = project or os.environ.get("AGY_PROJECT") or CONFIG["lanes"][CONFIG["default_lane"]].get("project")
    if not project: raise SystemExit("AGY_PROJECT is not set")
    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/global/interactions"
    req = urllib.request.Request(url, data=json.dumps({"model": MODEL, "input": [{"type": "text", "text": brief}]}).encode(),
                                 headers={"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r: resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:500]}")
    for o in resp.get("outputs", []):
        if o.get("type") == "audio" and o.get("data"):
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            open(out, "wb").write(base64.b64decode(o["data"])); print(f"saved {out} in {time.time()-t0:.0f}s"); return out
    raise SystemExit("no audio returned: " + json.dumps(resp)[:400])

def rms_map(audio, step=1.0):
    tmp = audio + ".rms.txt"
    subprocess.run(["ffmpeg", "-loglevel", "quiet", "-i", audio, "-af", f"asetnsamples={int(44100*step)},astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file={tmp}", "-f", "null", "-"], check=True)
    v = [float(m.group(1)) if m.group(1) != "-inf" else -99 for l in open(tmp) for m in [re.search(r"RMS_level=(-?[\d.]+|-inf)", l)] if m]
    os.remove(tmp); return v

def cmd_map(audio):
    v = rms_map(audio); dur = len(v)
    print(f"duration ~{dur}s; RMS dB per second:")
    for i in range(0, dur, 10): print(f"{i:4d}s  " + " ".join(f"{int(x):4d}" for x in v[i:i+10]))
    drops = [i for i in range(1, dur) if v[i] < -40 and v[i-1] > -25]
    hits = [i for i in range(1, dur) if v[i] - v[i-1] > 12]
    print("silences/drops at:", drops); print("hits/slams at:", hits)

def cut(audio, start, length, out, fi, fo):
    af = f"afade=t=in:st=0:d={fi},afade=t=out:st={max(0,length-fo):.2f}:d={fo}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", audio, "-t", str(length), "-af", af, "-c:a", "libmp3lame", "-q:a", "2", out], check=True)
    print(out)

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--brief", required=True); r.add_argument("--out", required=True); r.add_argument("--project")
    m = sub.add_parser("map"); m.add_argument("--audio", required=True)
    c = sub.add_parser("cut"); c.add_argument("--audio", required=True); c.add_argument("--start", type=float, required=True); c.add_argument("--len", type=float, required=True); c.add_argument("--out", required=True); c.add_argument("--fade-in", type=float, default=0.5); c.add_argument("--fade-out", type=float, default=1.5)
    a = ap.parse_args()
    if a.cmd == "render": render(a.brief, a.out, a.project)
    elif a.cmd == "map": cmd_map(a.audio)
    else: cut(a.audio, a.start, a.len, a.out, a.fade_in, a.fade_out)

if __name__ == "__main__":
    main()
