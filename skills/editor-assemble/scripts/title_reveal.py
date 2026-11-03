#!/usr/bin/env python3
"""title_reveal.py — word-by-word title slam over a video, with synced synthesized bangs.

  title_reveal.py --video in.mp4 --out out.mp4 --words "LIKE," "FOLLOW," "DIE," "OR KILL." --times 10.6 11.6 12.6 13.6 \
                  [--colors white white "#ff1e28" white] [--black-at 14.7] [--font ...] [--size 72] [--bg-volume 0.85]
Bangs come from sound-sfx presets (title_bang, climax on the last word).
"""
import argparse, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sound-sfx", "scripts"))
from sfx_synth import title_bang, title_bang_climax, SR  # noqa: E402

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--words", nargs="+", required=True); ap.add_argument("--times", nargs="+", type=float, required=True)
    ap.add_argument("--colors", nargs="*", default=[]); ap.add_argument("--black-at", type=float); ap.add_argument("--size", type=int, default=72)
    ap.add_argument("--font", default="/usr/share/fonts/truetype/msttcorefonts/Arial_Black.ttf"); ap.add_argument("--bg-volume", type=float, default=0.85)
    a = ap.parse_args()
    assert len(a.words) == len(a.times)
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "csv=p=0", a.video]).decode().split()
    W, H = int(probe[0].split(",")[0]), int(probe[0].split(",")[1]); fps = 24; D = float(probe[-1]) if len(probe) > 1 else float(probe[0].split(",")[-1])
    try: D = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video]).decode())
    except Exception: pass
    if not os.path.exists(a.font): a.font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".scratch", "title_frames"); os.makedirs(tmp, exist_ok=True)
    n = int(D * fps); bang_frames = [int(t * fps) for t in a.times]; spacing = int(a.size * 1.4); y0 = (H - spacing * len(a.words)) // 2
    for f in range(n):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255 if (a.black_at and f >= int(a.black_at * fps)) else 0))
        if not (a.black_at and f >= int(a.black_at * fps)):
            d = ImageDraw.Draw(img)
            for i, (w, bf) in enumerate(zip(a.words, bang_frames)):
                if f < bf: continue
                age = f - bf; size = int(a.size * (1 + .35 * math.exp(-age * .7))) if age < 6 else a.size
                font = ImageFont.truetype(a.font, size); bb = d.textbbox((0, 0), w, font=font); tw, th = bb[2] - bb[0], bb[3] - bb[1]
                x, y = (W - tw) // 2, y0 + i * spacing + (spacing - th) // 2
                for ox, oy in ((-3, -3), (3, -3), (-3, 3), (3, 3), (0, 4), (0, -4), (4, 0), (-4, 0)): d.text((x + ox, y + oy), w, font=font, fill=(0, 0, 0, 240))
                if age < 4: d.text((x - 4, y), w, font=font, fill=(255, 0, 60, 200)); d.text((x + 4, y), w, font=font, fill=(0, 220, 255, 200))
                col = a.colors[i] if i < len(a.colors) else "white"
                d.text((x, y), w, font=font, fill=col)
            if any(0 <= f - bf < 4 for bf in bang_frames):
                age = min(f - bf for bf in bang_frames if 0 <= f - bf < 4)
                img = Image.alpha_composite(img, Image.new("RGBA", (W, H), (255, 255, 255, int(70 * math.exp(-age)))))
        img.save(os.path.join(tmp, f"f_{f:05d}.png"))
    # audio
    total = np.zeros(int(D * SR), dtype=np.float32)
    for i, t in enumerate(a.times):
        sig = title_bang_climax() if i == len(a.times) - 1 else title_bang(crunch=(i == len(a.times) - 2))
        s = int(t * SR); e = min(len(total), s + len(sig)); total[s:e] += sig[: e - s]
    total = total / (np.max(np.abs(total)) or 1) * .95
    sfx = os.path.join(tmp, "bangs.wav")
    with wave.open(sfx, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((total * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-framerate", str(fps), "-i", os.path.join(tmp, "f_%05d.png"), "-i", sfx, "-filter_complex",
                    f"[0:v][1:v]overlay=0:0[v];[0:a]volume={a.bg_volume}[a0];[2:a]volume=1.2[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", a.out], check=True)
    print(a.out)

if __name__ == "__main__":
    main()
