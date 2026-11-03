#!/usr/bin/env python3
"""mix.py — Mixer: music ducking under dialogue, SFX placement, loudness normalisation, report.

  mix.py --video cut.mp4 --out cut_mix.mp4 [--music cue.mp3 --music-gain 0.10 --music-offset 0.0] [--sfx sfx_stem.wav --sfx-gain 0.9] [--lufs -14] [--tp -1]
  mix.py qc --video cut.mp4            # loudness + true peak only
Dialogue is the embedded audio of --video. Music is side-chain ducked by dialogue. Two-pass loudnorm to target.
"""
import argparse, json, re, subprocess

def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())

def loudness(p):
    o = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", p, "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", o, re.S)
    return json.loads(m.group(0)) if m else {}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("qc", nargs="?"); ap.add_argument("--video", required=True); ap.add_argument("--out")
    ap.add_argument("--music"); ap.add_argument("--music-gain", type=float, default=0.10); ap.add_argument("--music-offset", type=float, default=0.0)
    ap.add_argument("--sfx"); ap.add_argument("--sfx-gain", type=float, default=0.9); ap.add_argument("--lufs", type=float, default=-14); ap.add_argument("--tp", type=float, default=-1)
    a = ap.parse_args()
    if a.qc == "qc" or not a.out:
        print(json.dumps(loudness(a.video), indent=2)); return
    D = dur(a.video); inputs = ["-i", a.video]; fc = []; mix_in = ["[dlg]"]
    fc.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[dlg][key]")
    idx = 1
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
        fc.append(f"[{idx}:a]atrim=0:{D+1:.2f},asetpts=PTS-STARTPTS,adelay={int(max(0,a.music_offset)*1000)}|{int(max(0,a.music_offset)*1000)},aformat=sample_rates=48000:channel_layouts=stereo,volume={a.music_gain},afade=t=in:st=0:d=1,afade=t=out:st={max(0,D-2.5):.2f}:d=2.5[m]")
        fc.append("[m][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md]"); mix_in.append("[md]"); idx += 1
    else:
        fc.append("[key]anullsink")
    if a.sfx:
        inputs += ["-i", a.sfx]; fc.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={a.sfx_gain}[sx]"); mix_in.append("[sx]"); idx += 1
    fc.append("".join(mix_in) + f"amix=inputs={len(mix_in)}:duration=first:dropout_transition=0:normalize=0[pre]")
    # pass 1 measure on the pre-mix
    tmp = a.out + ".pre.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[pre]", "-c:a", "pcm_s16le", tmp], check=True)
    m = loudness(tmp)
    ln = (f"loudnorm=I={a.lufs}:TP={a.tp}:LRA=11:measured_I={m.get('input_i')}:measured_TP={m.get('input_tp')}:measured_LRA={m.get('input_lra')}:measured_thresh={m.get('input_thresh')}:offset={m.get('target_offset')}:linear=true"
          if m.get("input_i") else f"loudnorm=I={a.lufs}:TP={a.tp}:LRA=11")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-i", tmp, "-filter_complex", f"[1:a]{ln}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
    final = loudness(a.out)
    rep = {"out": a.out, "duration": round(D, 2), "target_lufs": a.lufs, "measured_lufs": final.get("input_i"), "true_peak": final.get("input_tp"), "music": a.music, "sfx": a.sfx}
    open(a.out + ".mix_report.json", "w").write(json.dumps(rep, indent=2)); print(json.dumps(rep, indent=2))

if __name__ == "__main__":
    main()
