#!/usr/bin/env python3
"""deliver.py — Post Supervisor delivery: masters per spec, smart aspect reframing, sidecar/burned captions, checksums, optional upload.

  deliver.py --in cut_mix.mp4 --show lfdk --ep EP01 --out-dir production/masters [--specs 9x16:1080p 16x9:1080p] [--reframe auto|fill|fit] [--srt captions.srt] [--burn] [--upload drive]
"""
import argparse, hashlib, json, os, shutil, subprocess

SPEC = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}
RES = {"720p": 720, "1080p": 1080, "4k": 2160}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def probe_size(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", path],
        text=True,
    ).strip()
    w, h = out.split("x")
    return int(w), int(h)


def build_reframe_vf(src_w, src_h, dst_w, dst_h, mode="auto"):
    """Return ffmpeg scale+crop (fill) or scale+pad (fit) filter string."""
    if mode == "auto":
        src_ar = src_w / max(1, src_h)
        dst_ar = dst_w / max(1, dst_h)
        mode = "fill" if abs(src_ar - dst_ar) > 0.05 else "fit"
    if mode == "fill":
        return f"scale={dst_w}:{dst_h}:force_original_aspect_ratio=increase,crop={dst_w}:{dst_h},format=yuv420p"
    return f"scale={dst_w}:{dst_h}:force_original_aspect_ratio=decrease,pad={dst_w}:{dst_h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--show", required=True)
    ap.add_argument("--ep", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--specs", nargs="*", default=["9x16:1080p"])
    ap.add_argument("--reframe", choices=["auto", "fill", "fit"], default="auto")
    ap.add_argument("--srt")
    ap.add_argument("--burn", action="store_true")
    ap.add_argument("--upload", choices=["drive"])
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    src_w, src_h = probe_size(a.inp)
    manifest = []
    for s in a.specs:
        ar, res = s.split(":")
        w, h = SPEC[ar]
        short = RES[res]
        if w < h:
            w, h = int(short * 9 / 16) // 2 * 2, short
        elif w == h:
            w, h = short, short
        else:
            w, h = short * 16 // 9 // 2 * 2, short
        out = os.path.join(a.out_dir, f"{a.show}_{a.ep}_{ar}_{res}.mp4")
        vf = build_reframe_vf(src_w, src_h, w, h, mode=a.reframe)
        if a.srt and a.burn:
            vf += f",subtitles={a.srt}"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", a.inp, "-vf", vf, "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out],
            check=True,
        )
        if a.srt and not a.burn:
            shutil.copy(a.srt, os.path.splitext(out)[0] + ".srt")
        entry = {"file": os.path.basename(out), "width": w, "height": h, "reframe": a.reframe, "sha256_16": sha(out), "bytes": os.path.getsize(out)}
        if a.upload == "drive":
            cmd = os.environ.get("AGY_UPLOAD_CMD")
            if cmd:
                r = subprocess.run(cmd.split() + [out], capture_output=True, text=True)
                entry["upload"] = (r.stdout or r.stderr).strip()[:200]
            else:
                entry["upload"] = "skipped: set AGY_UPLOAD_CMD"
        manifest.append(entry)
        print(json.dumps(entry))
    with open(os.path.join(a.out_dir, f"{a.show}_{a.ep}_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
