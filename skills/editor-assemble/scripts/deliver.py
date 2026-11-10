#!/usr/bin/env python3
"""deliver.py — Post Supervisor delivery: masters per spec, sidecar/burned captions, checksums, optional upload.

  deliver.py --in cut_mix.mp4 --show lfdk --ep EP01 --out-dir production/masters [--specs 9x16:1080p 16x9:1080p] [--srt captions.srt] [--burn] [--upload drive]
"""
import argparse, hashlib, json, os, shutil, subprocess

SPEC = {"9x16": (1080, 1920), "16x9": (1920, 1080), "1x1": (1080, 1080)}
RES = {"720p": 720, "1080p": 1080, "4k": 2160}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--show", required=True); ap.add_argument("--ep", required=True)
    ap.add_argument("--out-dir", required=True); ap.add_argument("--specs", nargs="*", default=["9x16:1080p"]); ap.add_argument("--srt"); ap.add_argument("--burn", action="store_true"); ap.add_argument("--upload", choices=["drive"])
    a = ap.parse_args(); os.makedirs(a.out_dir, exist_ok=True); manifest = []
    for s in a.specs:
        ar, res = s.split(":"); w, h = SPEC[ar]; short = RES[res]
        if w < h: w, h = int(short * 9 / 16) // 2 * 2, short
        else: w, h = short * 16 // 9 // 2 * 2, short
        out = os.path.join(a.out_dir, f"{a.show}_{a.ep}_{ar}_{res}.mp4")
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
        if a.srt and a.burn: vf += f",subtitles={a.srt}"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.inp, "-vf", vf, "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out], check=True)
        if a.srt and not a.burn: shutil.copy(a.srt, os.path.splitext(out)[0] + ".srt")
        entry = {"file": os.path.basename(out), "sha256_16": sha(out), "bytes": os.path.getsize(out)}
        if a.upload == "drive":
            # Any CLI that uploads a file and prints a link; set AGY_UPLOAD_CMD, e.g. 'gdrive files upload' or 'rclone copy ... remote:'
            cmd = os.environ.get("AGY_UPLOAD_CMD")
            if cmd:
                r = subprocess.run(cmd.split() + [out], capture_output=True, text=True); entry["upload"] = (r.stdout or r.stderr).strip()[:200]
            else:
                entry["upload"] = "skipped: set AGY_UPLOAD_CMD"
        manifest.append(entry); print(json.dumps(entry))
    json.dump(manifest, open(os.path.join(a.out_dir, f"{a.show}_{a.ep}_manifest.json"), "w"), indent=2)

if __name__ == "__main__":
    main()
