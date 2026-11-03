#!/usr/bin/env python3
"""grade.py — Colorist's ffmpeg grade pass.

  grade.py --in cut.mp4 --out cut_graded.mp4 [--exposure 0.0] [--temp 0] [--sat 1.0] [--contrast 1.0] [--gamma 1.0] [--lut look.cube] [--grain 0]
  grade.py match --in clip.mp4 --ref ref_clip.mp4 --out clip_matched.mp4      # mean-luma/colour match (coarse)
exposure in EV (±1), temp in -100..100 (neg = cooler), grain 0..20.
"""
import argparse, json, subprocess, sys

def stats(p):
    o = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", p, "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG:key=lavfi.signalstats.UAVG:key=lavfi.signalstats.VAVG", "-f", "null", "-"], capture_output=True, text=True).stderr
    import re
    y = [float(x) for x in re.findall(r"YAVG=([\d.]+)", o)]; u = [float(x) for x in re.findall(r"UAVG=([\d.]+)", o)]; v = [float(x) for x in re.findall(r"VAVG=([\d.]+)", o)]
    return (sum(y)/len(y) if y else 128, sum(u)/len(u) if u else 128, sum(v)/len(v) if v else 128)

def build_vf(exposure=0, temp=0, sat=1, contrast=1, gamma=1, lut=None, grain=0):
    vf = []
    if lut: vf.append(f"lut3d=file={lut}")
    rb = 1 + temp / 400.0; bb = 1 - temp / 400.0
    vf.append(f"eq=brightness={exposure*0.08:.4f}:contrast={contrast}:saturation={sat}:gamma={gamma}:gamma_r={rb:.4f}:gamma_b={bb:.4f}")
    if grain: vf.append(f"noise=alls={grain}:allf=t")
    vf.append("format=yuv420p"); return ",".join(vf)

def run(inp, out, vf):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", inp, "-vf", vf, "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "copy", out], check=True); print(out)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "match":
        ap = argparse.ArgumentParser(); ap.add_argument("match"); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--ref", required=True); ap.add_argument("--out", required=True)
        a = ap.parse_args(); yi, ui, vi = stats(a.inp); yr, ur, vr = stats(a.ref)
        exposure = (yr - yi) / 40.0; temp = (vr - vi) * 2 - (ur - ui) * 2
        print(json.dumps({"delta_luma": round(yr - yi, 1), "exposure_ev": round(exposure, 2), "temp": round(temp, 1)}))
        run(a.inp, a.out, build_vf(exposure=exposure, temp=temp)); return
    ap = argparse.ArgumentParser(); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
    for k, d in (("exposure", 0.0), ("temp", 0.0), ("sat", 1.0), ("contrast", 1.0), ("gamma", 1.0), ("grain", 0.0)): ap.add_argument(f"--{k}", type=float, default=d)
    ap.add_argument("--lut"); a = ap.parse_args()
    run(a.inp, a.out, build_vf(a.exposure, a.temp, a.sat, a.contrast, a.gamma, a.lut, int(a.grain)))

if __name__ == "__main__":
    main()
