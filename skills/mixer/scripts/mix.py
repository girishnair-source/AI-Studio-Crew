#!/usr/bin/env python3
"""mix.py — Mixer: voice chain, side-chain ducking (slow release), SFX placement, music in/out, limiter, loudness, report.

Craft (format-craft/editor-craft § Sound): voice first; EQ → de-ess → light comp on the dialogue layer; ducker with slow
release so music swells back between lines; music starts at a turn and its fade-up MIDDLE lands on the first word;
music out just before the key line; limiter at -1 dBTP; -14 LUFS social, -23/-24 broadcast.

  mix.py --video cut.mp4 --out cut_mix.mp4 [--music cue.mp3 --music-gain 0.10 --music-offset 0.0] [--sfx sfx_stem.wav --sfx-gain 0.9] [--lufs -14] [--tp -1]
  mix.py qc --video cut.mp4            # loudness + true peak only
Dialogue is the embedded audio of --video. Music is side-chain ducked by dialogue. Two-pass loudnorm to target.
"""
import argparse, json, os, re, subprocess

def dur(p): return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())

def loudness(p):
    o = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", p, "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", o, re.S)
    return json.loads(m.group(0)) if m else {}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("qc", nargs="?"); ap.add_argument("--video", required=True); ap.add_argument("--out")
    ap.add_argument("--music"); ap.add_argument("--music-gain", type=float, default=0.10); ap.add_argument("--music-offset", type=float, default=0.0)
    ap.add_argument("--sfx"); ap.add_argument("--sfx-gain", type=float, default=0.9); ap.add_argument("--lufs", type=float, default=-14); ap.add_argument("--tp", type=float, default=-1)
    ap.add_argument("--music-in", type=float, help="timecode where music should be fully in (its fade-up middle lands here; e.g. first word of the section)")
    ap.add_argument("--music-out", type=float, help="timecode of the key line; music is out 0.3s before it")
    ap.add_argument("--music-fade", type=float, default=1.2); ap.add_argument("--no-voice-chain", action="store_true"); ap.add_argument("--broadcast", action="store_true", help="-23 LUFS / -1 dBTP")
    a = ap.parse_args()
    if a.qc == "qc" or not a.out:
        print(json.dumps(loudness(a.video), indent=2)); return
    if a.broadcast: a.lufs, a.tp = -23, -1
    D = dur(a.video); inputs = ["-i", a.video]; fc = []; mix_in = ["[dlg]"]
    chain = "" if a.no_voice_chain else "highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=1.5,deesser=i=0.4,acompressor=threshold=-18dB:ratio=2:attack=15:release=120:makeup=2,"
    fc.append(f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,{chain}asplit=2[dlg][key]")
    idx = 1
    if a.music:
        inputs += ["-stream_loop", "-1", "-i", a.music]
        # music in: fade-up whose MIDDLE lands on --music-in (first word of the section); out: gone 0.3s before --music-out (the key line)
        fin_start = max(0.0, (a.music_in - a.music_fade / 2) if a.music_in is not None else 0.0)
        out_end = (a.music_out - 0.3) if a.music_out is not None else D
        fout_start = max(fin_start, out_end - a.music_fade)
        fc.append(f"[{idx}:a]atrim=0:{D+1:.2f},asetpts=PTS-STARTPTS,adelay={int(max(0,a.music_offset)*1000)}|{int(max(0,a.music_offset)*1000)},aformat=sample_rates=48000:channel_layouts=stereo,volume={a.music_gain},"
                  f"afade=t=in:st={fin_start:.2f}:d={a.music_fade:.2f},afade=t=out:st={fout_start:.2f}:d={a.music_fade:.2f},atrim=0:{out_end:.2f},apad=whole_dur={D:.2f}[m]")
        # ducker: moderate ratio, slow release so music swells back between lines instead of pumping
        fc.append("[m][key]sidechaincompress=threshold=0.03:ratio=5:attack=25:release=700:makeup=1[md]"); mix_in.append("[md]"); idx += 1
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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.video, "-i", tmp, "-filter_complex", f"[1:a]{ln},alimiter=limit={10**(a.tp/20):.4f}:attack=5:release=50:level=false[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
    final = loudness(a.out)
    rep = {"out": a.out, "duration": round(D, 2), "target_lufs": a.lufs, "measured_lufs": final.get("input_i"), "true_peak": final.get("input_tp"), "music": a.music, "sfx": a.sfx,
           "voice_chain": not a.no_voice_chain, "music_in": a.music_in, "music_out": a.music_out, "ducker": "ratio 5:1, attack 25ms, release 700ms", "limiter_dbtp": a.tp}
    try: os.remove(tmp)
    except Exception: pass
    open(a.out + ".mix_report.json", "w").write(json.dumps(rep, indent=2)); print(json.dumps(rep, indent=2))

if __name__ == "__main__":
    main()
