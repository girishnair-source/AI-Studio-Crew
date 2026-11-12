#!/usr/bin/env python3
"""assemble.py — Editor's assembly from a cut sheet (JSON). v3:
- Render cache (locality) + fixed merge cache keys (including tr_s & audio_lead_s)
- Lossless concat (-c copy) for contiguous plain cuts (eliminates generational re-encoding loss)
- Fixed J-cut audio lead sync
- Meaning-gated transitions (dissolve=time_passed, fade_black=ended)
- Speed ramps (speed), B-roll / PiP cutaways (broll), eased punch-ins, and dynamic ASS word/karaoke captions
- EDL + OTIO export

  assemble.py --cut cut.json --out production/cuts/EP01_v3.mp4 [--otio] [--no-cache]
"""
import argparse, hashlib, json, os, subprocess


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())


def resolve_out(clip, base):
    if clip.get("out") == "speech":
        qc = os.path.join(os.path.dirname(os.path.join(base, clip["src"])), "qc.json")
        if os.path.exists(qc):
            with open(qc) as f:
                r = json.load(f).get(os.path.basename(clip["src"]))
            if r and r.get("trim_to"):
                return float(r["trim_to"])
        return dur(os.path.join(base, clip["src"]))
    return float(clip.get("out") or dur(os.path.join(base, clip["src"])))


def gate_transition(i, c, n, warnings):
    t = c.get("transition", "cut")
    if t == "dissolve" and not c.get("time_passed"):
        warnings.append(f"clip {i}: dissolve without time_passed=true → cut (a dissolve says time passed)")
        return "cut"
    if t == "fade_black" and not (c.get("ended") or i == n - 1):
        warnings.append(f"clip {i}: fade_black mid-piece without ended=true → cut (a fade to black says it ended)")
        return "cut"
    return t


def smooth(t0, t1):
    """smoothstep(t) between t0..t1 as an ffmpeg expression (commas escaped for use inside drawtext options)."""
    u = f"((t-{t0:.4f})/({t1 - t0:.4f}))"
    return f"if(lt(t\\,{t0:.4f})\\,0\\,if(gt(t\\,{t1:.4f})\\,1\\,{u}*{u}*(3-2*{u})))"


def _ass_time(sec):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_ass_captions(captions, out_ass, W, H, style=None):
    """Generate an ASS subtitle file supporting static, pop, and word-level karaoke highlighting."""
    st = style or {}
    font = st.get("font", "DejaVu Sans")
    size = int(st.get("size", max(36, int(H * 0.042))))
    margin_v = int(st.get("margin_v", int(H * 0.16) if H > W else int(H * 0.08)))
    primary = st.get("primary_color", "&H00FFFFFF")
    highlight = st.get("highlight_color", "&H0000D7FF")  # gold/yellow in BGR
    outline_c = st.get("outline_color", "&H00000000")
    back_c = st.get("back_color", "&H64000000")
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{size},{primary},{highlight},{outline_c},{back_c},-1,0,0,0,100,100,0,0,1,3,1,2,40,40,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for cap in captions:
        t0, t1 = float(cap["from"]), float(cap["to"])
        txt = (cap.get("text") or "").strip()
        if not txt or t1 <= t0:
            continue
        mode = cap.get("mode", st.get("mode", "pop"))
        if mode == "karaoke":
            words = txt.split()
            if not words:
                continue
            total_cs = max(10, int(round((t1 - t0) * 100)))
            per_w = max(5, total_cs // len(words))
            rem = total_cs - per_w * len(words)
            k_parts = []
            for idx, w in enumerate(words):
                dur_cs = per_w + (rem if idx == len(words) - 1 else 0)
                k_parts.append(f"{{\\kf{dur_cs}}}{w}")
            line_txt = " ".join(k_parts)
        elif mode == "pop":
            line_txt = "{\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}" + txt.replace("\n", "\\N")
        else:
            line_txt = txt.replace("\n", "\\N")
        events.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},Default,,0,0,0,,{line_txt}")
    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")
    return out_ass


def _atempo_chain(speed):
    """Build valid ffmpeg atempo filter chain for any positive speed factor (each stage in [0.5, 2.0])."""
    if abs(speed - 1.0) < 1e-3:
        return []
    parts = []
    s = float(speed)
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.4f}")
    return parts


def build_part(c, base, fps, W, H, font, ln, tin, src, out, cache_dir):
    speed = float(c.get("speed", 1.0))
    eff_ln = ln / speed
    vf = [f"fps={fps}", f"scale={W}:{H}:force_original_aspect_ratio=decrease", f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
    if abs(speed - 1.0) >= 1e-3:
        vf.append(f"setpts=PTS/{speed:.4f}")
    pi = c.get("punch_in")
    if pi:
        at, to, d = float(pi["at"]), float(pi.get("to", 1.1)), float(pi.get("dur", 0.25))
        f0, f1 = int(at * fps), int((at + d) * fps)
        u = f"((on-{f0})/{max(1, f1 - f0)})"
        zexpr = f"if(lt(on\\,{f0})\\,1\\,if(gt(on\\,{f1})\\,{to}\\,1+({to}-1)*{u}*{u}*(3-2*{u})))"
        vf.append(f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}")

    for o in c.get("overlays", []):
        f0, f1 = float(o.get("from", 0)), float(o.get("to", eff_ln))
        size = o.get("size", 44)
        y = o.get("y", 1040)
        if o.get("ease", True):
            ein, eout = 8 / fps, 5 / fps
            alpha = f"if(lt(t\\,{f0+ein:.4f})\\,{smooth(f0, f0+ein)}\\,if(lt(t\\,{f1-eout:.4f})\\,1\\,1-({smooth(f1-eout, f1)})))"
            yexpr = f"{y}+6*(1-({smooth(f0, f0+ein)}))"
            vf.append(
                f"drawtext=fontfile={font}:text='{esc(o['text'])}':fontsize={size}:fontcolor={o.get('color','white')}:alpha='{alpha}':borderw=3:bordercolor=black@0.85:"
                f"box=1:boxcolor=black@0.35:boxborderw=14:x=(w-text_w)/2:y='{yexpr}':enable='between(t,{f0},{f1})'"
            )
        else:
            vf.append(
                f"drawtext=fontfile={font}:text='{esc(o['text'])}':fontsize={size}:fontcolor={o.get('color','white')}:borderw=3:bordercolor=black@0.85:"
                f"box=1:boxcolor=black@0.35:boxborderw=14:x=(w-text_w)/2:y={y}:enable='between(t,{f0},{f1})'"
            )

    if c.get("captions"):
        ass_path = os.path.join(cache_dir, os.path.basename(out) + ".ass")
        write_ass_captions(c["captions"], ass_path, W, H, c.get("caption_style"))
        vf.append(f"ass={esc(ass_path)}")

    af = ["aformat=sample_rates=48000:channel_layouts=stereo"] + _atempo_chain(speed)
    if c.get("fade_audio_in"):
        af.append(f"afade=t=in:st=0:d={c['fade_audio_in']}")
    if c.get("fade_audio_out"):
        af.append(f"afade=t=out:st={max(0, eff_ln - c['fade_audio_out']):.3f}:d={c['fade_audio_out']}")

    brolls = c.get("broll") or []
    if not brolls:
        vf.append("format=yuv420p")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(tin), "-i", src, "-t", f"{ln:.3f}", "-vf", ",".join(vf), "-af", ",".join(af),
             "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out],
            check=True,
        )
        return eff_ln

    # Composite B-roll (full cutaway or PiP) over primary video while keeping primary audio
    inputs = ["-ss", str(tin), "-t", f"{ln:.3f}", "-i", src]
    fc = [f"[0:v]{','.join(vf)}[base0]"]
    cur_v = "base0"
    for idx, br in enumerate(brolls, 1):
        bsrc = os.path.join(base, br["src"]) if not os.path.isabs(br["src"]) else br["src"]
        btin = float(br.get("in", 0))
        bat = float(br.get("at", 0))
        bdur = float(br.get("dur", 2.0))
        inputs += ["-ss", str(btin), "-t", f"{bdur:.3f}", "-i", bsrc]
        mode = br.get("mode", "full")
        if mode == "pip":
            x, y, pw, ph = br.get("rect", [int(W * 0.58), int(H * 0.06), int(W * 0.36), int(H * 0.36)])
            fc.append(f"[{idx}:v]fps={fps},scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph},setpts=PTS-STARTPTS+{bat:.3f}/TB[br{idx}]")
            fc.append(f"[{cur_v}][br{idx}]overlay=x={x}:y={y}:enable='between(t,{bat:.3f},{bat+bdur:.3f})'[v{idx}]")
        else:
            fc.append(f"[{idx}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=PTS-STARTPTS+{bat:.3f}/TB[br{idx}]")
            fc.append(f"[{cur_v}][br{idx}]overlay=x=0:y=0:enable='between(t,{bat:.3f},{bat+bdur:.3f})'[v{idx}]")
        cur_v = f"v{idx}"
    fc.append(f"[{cur_v}]format=yuv420p[vout]")
    fc.append(f"[0:a]{','.join(af)}[aout]")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out],
        check=True,
    )
    return eff_ln


def _concat_lossless(paths, out):
    lst = out + ".concat.txt"
    with open(lst, "w") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    finally:
        if os.path.exists(lst):
            os.remove(lst)
    return out


def merge_parts(parts, cache_dir, no_cache=False):
    """Merge parts using lossless concat for plain-cut runs, and filter_complex only at transitions/J-cuts."""
    if len(parts) == 1:
        return parts[0]["path"], parts[0]["len"]

    # Group contiguous plain cuts (transition == 'cut' and lead == 0) into lossless segments first
    segs = []
    cur_group = [parts[0]]
    for p in parts[1:]:
        if p["transition"] == "cut" and p["lead"] <= 0:
            cur_group.append(p)
        else:
            segs.append(cur_group)
            cur_group = [p]
    segs.append(cur_group)

    merged_segs = []
    for g in segs:
        if len(g) == 1:
            merged_segs.append(g[0])
        else:
            key = hashlib.sha1("|".join(x["path"] for x in g).encode()).hexdigest()[:14]
            cpath = os.path.join(cache_dir, f"concat_{key}.mp4")
            if no_cache or not os.path.exists(cpath):
                _concat_lossless([x["path"] for x in g], cpath)
            merged_segs.append({
                "path": cpath,
                "transition": g[0]["transition"],
                "tr_s": g[0]["tr_s"],
                "len": sum(x["len"] for x in g),
                "lead": g[0]["lead"],
            })

    run_path = merged_segs[0]["path"]
    total = merged_segs[0]["len"]
    for k in range(1, len(merged_segs)):
        p = merged_segs[k]
        tr = p["transition"]
        key_str = f"{run_path}|{p['path']}|{tr}|{p['tr_s']:.3f}|{p['lead']:.3f}"
        nxt = os.path.join(cache_dir, f"run_{k}_{hashlib.sha1(key_str.encode()).hexdigest()[:12]}.mp4")
        if tr in ("dissolve", "fade_black"):
            d = max(0.1, min(p["tr_s"], total / 2, p["len"] / 2))
            if not os.path.exists(nxt) or no_cache:
                fcs = (
                    f"[0:v][1:v]xfade=transition={'fade' if tr=='dissolve' else 'fadeblack'}:duration={d:.3f}:offset={total - d:.3f}[v];"
                    f"[0:a][1:a]acrossfade=d={d:.3f}:c1=tri:c2=tri[a]"
                )
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-i", p["path"], "-filter_complex", fcs, "-map", "[v]", "-map", "[a]",
                     "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", nxt],
                    check=True,
                )
            total += p["len"] - d
        else:
            lead = max(0.0, min(p["lead"], total / 2))
            if not os.path.exists(nxt) or no_cache:
                if lead > 0:
                    ms = int((total - lead) * 1000)
                    out_dur = total + p["len"]
                    fcs = (
                        f"[0:v][1:v]concat=n=2:v=1:a=0[v];[1:a]adelay={ms}|{ms}[na];"
                        f"[0:a]apad=whole_dur={out_dur:.3f}[pa];[pa][na]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,apad=whole_dur={out_dur:.3f},atrim=0:{out_dur:.3f}[a]"
                    )
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-i", p["path"], "-filter_complex", fcs, "-map", "[v]", "-map", "[a]",
                         "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", nxt],
                        check=True,
                    )
                else:
                    _concat_lossless([run_path, p["path"]], nxt)
            total += p["len"]
        run_path = nxt
    return run_path, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--otio", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    with open(a.cut) as f:
        cut = json.load(f)
    base = os.path.dirname(os.path.abspath(a.cut))
    fps, W, H = cut.get("fps", 24), cut.get("width", 720), cut.get("height", 1280)
    font = cut.get("font", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    cache = os.path.join(os.path.dirname(os.path.abspath(a.out)), ".cache")
    os.makedirs(cache, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    parts, edl, warnings, changes, t_acc = [], [], [], [], 0.0
    n = len(cut["clips"])
    for i, c in enumerate(cut["clips"]):
        if "black" in c:
            key = hashlib.sha1(json.dumps({"black": c["black"], "W": W, "H": H, "fps": fps}, sort_keys=True).encode()).hexdigest()[:16]
            p = os.path.join(cache, f"black_{key}.mp4")
            if a.no_cache or not os.path.exists(p):
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                     "-t", str(c["black"]), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", p],
                    check=True,
                )
                changes.append(f"black@{i}")
            parts.append({"path": p, "transition": gate_transition(i, c, n, warnings), "tr_s": float(c.get("transition_s", 0.5)), "len": float(c["black"]), "lead": 0.0})
            t_acc += float(c["black"])
            continue

        src = os.path.join(base, c["src"]) if not os.path.isabs(c["src"]) else c["src"]
        tin = float(c.get("in", 0))
        tout = resolve_out(c, base)
        ln = tout - tin
        speed = float(c.get("speed", 1.0))
        eff_ln = ln / speed
        tr = gate_transition(i, c, n, warnings)
        spec = {k: v for k, v in c.items() if k not in ("transition", "transition_s", "time_passed", "ended", "audio_lead_s")}
        spec.update(W=W, H=H, fps=fps, font=font, tin=tin, tout=tout, srcmtime=os.path.getmtime(src))
        key = hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]
        p = os.path.join(cache, f"part_{key}.mp4")
        if a.no_cache or not os.path.exists(p):
            build_part(c, base, fps, W, H, font, ln, tin, src, p, cache)
            changes.append(c["src"])
        parts.append({"path": p, "transition": tr, "tr_s": float(c.get("transition_s", 0.5)), "len": eff_ln, "lead": float(c.get("audio_lead_s", 0))})
        edl.append({"n": len(edl) + 1, "src": c["src"], "src_in": tin, "src_out": tout, "rec_in": t_acc, "rec_out": t_acc + eff_ln, "transition": tr})
        t_acc += eff_ln

    run_path, total = merge_parts(parts, cache, no_cache=a.no_cache)
    if cut.get("captions"):
        g_ass = os.path.join(cache, "global_captions.ass")
        write_ass_captions(cut["captions"], g_ass, W, H, cut.get("caption_style"))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-vf", f"ass={esc(g_ass)}", "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "copy", "-movflags", "+faststart", a.out],
            check=True,
        )
    else:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", run_path, "-c", "copy", "-movflags", "+faststart", a.out], check=True)

    def tc(s):
        f = int(round((s % 1) * fps))
        s = int(s)
        return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}:{f:02d}"

    with open(a.out + ".edl", "w") as f:
        f.write(f"TITLE: {os.path.basename(a.out)}\nFCM: NON-DROP FRAME\n\n")
        for e in edl:
            f.write(f"{e['n']:03d}  AX       AA/V  {'D' if e['transition']!='cut' else 'C'}        {tc(e['src_in'])} {tc(e['src_out'])} {tc(e['rec_in'])} {tc(e['rec_out'])}\n* FROM CLIP NAME: {os.path.basename(e['src'])}\n\n")
    if a.otio:
        otio = {
            "OTIO_SCHEMA": "Timeline.1",
            "name": os.path.basename(a.out),
            "tracks": {
                "OTIO_SCHEMA": "Stack.1",
                "children": [
                    {
                        "OTIO_SCHEMA": "Track.1",
                        "kind": "Video",
                        "children": [
                            {
                                "OTIO_SCHEMA": "Clip.1",
                                "name": os.path.basename(e["src"]),
                                "source_range": {
                                    "OTIO_SCHEMA": "TimeRange.1",
                                    "start_time": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": e["src_in"] * fps},
                                    "duration": {"OTIO_SCHEMA": "RationalTime.1", "rate": fps, "value": (e["src_out"] - e["src_in"]) * fps},
                                },
                                "media_reference": {"OTIO_SCHEMA": "ExternalReference.1", "target_url": os.path.abspath(os.path.join(base, e["src"]))},
                            }
                            for e in edl
                        ],
                    }
                ],
            },
        }
        with open(a.out + ".otio", "w") as f:
            json.dump(otio, f, indent=1)
    with open(a.out + ".changes.json", "w") as f:
        json.dump({"re_rendered": changes, "reused": len(parts) - len(changes), "warnings": warnings}, f, indent=1)
    print(json.dumps({"out": a.out, "duration": round(total, 2), "clips": len(edl), "re_rendered": len(changes), "reused": len(parts) - len(changes), "warnings": warnings}))


if __name__ == "__main__":
    main()
