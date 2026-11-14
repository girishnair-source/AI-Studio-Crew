#!/usr/bin/env python3
"""dailies_qc.py — inspect clips without loading video into chat.

  dailies_qc.py contact --video 4A_take1.mp4 [--frames 5] [--out 4A_take1_contact.png]
  dailies_qc.py speech  --video 4A_take1.mp4 [--floor -38] [--hold 0.45]      # speech end, margin, flags
  dailies_qc.py asr     --video 4A_take1.mp4 --expected "..."                 # ASR word-accuracy critic
  dailies_qc.py visual  --video 4A_take1.mp4 [--ref front.png ...] [--action "..."]  # visual continuity critic
  dailies_qc.py full    --video 4A_take1.mp4 [--expected "..."] [--ref ...] [--action "..."] [--no-llm]
  dailies_qc.py last    --video 4A_take1.mp4 [--out 4A_take1_last.png]
  dailies_qc.py scene   --dir production/dailies/EP01_SC04 [--manifest shots.json] [--no-llm]
"""
import argparse, base64, difflib, glob, json, math, os, re, subprocess, sys, tempfile, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CAMERA_ROLL_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "camera-roll", "scripts"))
if CAMERA_ROLL_DIR not in sys.path:
    sys.path.insert(0, CAMERA_ROLL_DIR)

QC_MODEL = os.environ.get("AGY_QC_MODEL", "gemini-2.5-flash")
QC_LOCATION = os.environ.get("AGY_QC_LOCATION", "global")
PROSODY_PROFILES = {"presenter": (4.5, 3.0), "dialogue": (3.0, 1.8), "narration": (3.5, 2.2), "cold": (2.0, 1.0)}


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], timeout=30).decode())


def probe_streams(path):
    """Return basic video/audio stream metadata via ffprobe."""
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate", "-of", "json", path],
        text=True,
        timeout=30,
    )
    streams = json.loads(out).get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "has_video": v is not None,
        "has_audio": a is not None,
        "width": v.get("width") if v else None,
        "height": v.get("height") if v else None,
    }


def contact(video, frames=5, out=None):
    d = dur(video)
    fps = 24
    idx = [int(fps * d * (i + 0.5) / frames) for i in range(frames)]
    sel = "+".join(f"eq(n,{i})" for i in idx)
    out = out or os.path.splitext(video)[0] + "_contact.png"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", f"select='{sel}',scale=216:-1,tile={frames}x1", "-frames:v", "1", out],
        check=True,
        timeout=60,
    )
    return out


def last(video, out=None):
    out = out or os.path.splitext(video)[0] + "_last.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", out], check=True, timeout=60)
    return out


def prosody(video, profile="dialogue"):
    """Monotony estimate: autocorrelation pitch (f0) on voiced frames -> f0 std in semitones; pace = voiced-run rate variance.
    ffmpeg + numpy only. Thresholds tuned on known-flat vs known-performed clips (see SKILL.md)."""
    try:
        import numpy as np
    except Exception:
        return {}
    sr = 16000
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "quiet", "-i", video, "-vn", "-ac", "1", "-ar", str(sr), "-af", "highpass=f=70,lowpass=f=1200", "-f", "s16le", "-"],
        capture_output=True,
    ).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < sr:
        return {}
    win, hop = 640, 160  # 40ms / 10ms
    fmin, fmax = 70, 400
    lag_min, lag_max = sr // fmax, sr // fmin
    f0_track, voiced = [], []  # f0 per 10ms frame, NaN when unvoiced (time-indexed)
    for i in range(0, len(x) - win, hop):
        f = x[i : i + win]
        e = float(np.sqrt(np.mean(f ** 2)))
        if e < 0.008:
            voiced.append(0)
            f0_track.append(np.nan)
            continue
        f = f - f.mean()
        ac = np.correlate(f, f, "full")[win - 1 :]
        ac /= ac[0] + 1e-9
        seg = ac[lag_min:lag_max]
        k = int(np.argmax(seg))
        peak = float(seg[k])
        if peak < 0.5:
            voiced.append(0)
            f0_track.append(np.nan)
            continue
        voiced.append(1)
        f0_track.append(sr / (lag_min + k))
    f0_track = np.array(f0_track, dtype=float)
    f0s = f0_track[~np.isnan(f0_track)]
    if len(f0s) < 30:
        return {}
    med = np.median(f0s)
    st_track = 12 * np.log2(f0_track / med)
    st_track[np.abs(st_track) > 12] = np.nan  # octave errors
    st = st_track[~np.isnan(st_track)]
    f0_std = float(np.std(st))
    runs, cur = [], 0
    for v in voiced:
        if v:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    runs = np.array(runs) if runs else np.array([1])
    pace_cv = float(np.std(runs) / (np.mean(runs) + 1e-9))
    fps = sr // hop
    per_sec = []
    for i in range(0, len(st_track), fps):
        seg = st_track[i : i + fps]
        seg = seg[~np.isnan(seg)]
        if len(seg) >= 10:
            per_sec.append(float(np.median(seg)))
    contour_std = float(np.std(per_sec)) if len(per_sec) >= 3 else float("nan")
    t_f0, t_contour = PROSODY_PROFILES.get(profile, PROSODY_PROFILES["dialogue"])
    monotone = bool(f0_std < t_f0 or (not math.isnan(contour_std) and contour_std < t_contour))
    return {
        "f0_std_semitones": round(f0_std, 2),
        "contour_std_semitones": (None if math.isnan(contour_std) else round(contour_std, 2)),
        "pace_cv": round(pace_cv, 2),
        "prosody_profile": profile,
        "monotone": monotone,
    }


def speech(video, floor=-38.0, hold=0.45, step=0.05, profile="dialogue"):
    tmp = video + ".rms.txt"
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "quiet", "-i", video, "-af",
            f"highpass=f=200,lowpass=f=4000,asetnsamples={int(48000*step)},astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file={tmp}",
            "-f", "null", "-",
        ],
        check=True,
    )
    v = [float(m.group(1)) if m.group(1) != "-inf" else -99 for l in open(tmp) for m in [re.search(r"RMS_level=(-?[\d.]+|-inf)", l)] if m]
    os.remove(tmp)
    d = dur(video)
    speaking = [i for i, x in enumerate(v) if x > floor]
    if not speaking:
        return {"duration": round(d, 2), "has_speech": False, "speech_start": None, "speech_end": None, "margin": None, "flags": ["no-speech"]}
    s, e = speaking[0] * step, (speaking[-1] + 1) * step
    margin = round(d - e, 2)
    flags = []
    if margin < 0.3:
        flags.append("speech-clipped-at-end")
    if s < 0.15:
        flags.append("speech-starts-at-zero")
    peak = subprocess.run(["ffmpeg", "-loglevel", "info", "-i", video, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+) dB", peak)
    mx = float(m.group(1)) if m else None
    if mx is not None and mx > -0.5:
        flags.append("audio-peaks-hot")
    pro = prosody(video, profile)
    if pro.get("monotone"):
        flags.append("monotone-read")
    return {
        "duration": round(d, 2),
        "has_speech": True,
        "speech_start": round(s, 2),
        "speech_end": round(e, 2),
        "margin": margin,
        "trim_to": round(min(d, e + hold), 2),
        "max_volume_db": mx,
        **pro,
        "flags": flags,
    }


def visual_basic(video):
    """Deterministic ffmpeg visual sanity: black frames and frozen segments."""
    d = dur(video)
    streams = probe_streams(video)
    err = subprocess.run(
        ["ffmpeg", "-loglevel", "info", "-i", video, "-vf", "blackdetect=d=0.3:pix_th=0.10,freezedetect=n=-60dB:d=1.5", "-f", "null", "-"],
        capture_output=True,
        text=True,
    ).stderr
    black_durs = [float(x) for x in re.findall(r"black_duration:([\d.]+)", err)]
    freeze_starts = [float(x) for x in re.findall(r"lavfi\.freezedetect\.freeze_start:\s*([\d.]+)", err)]
    freeze_durs = [float(x) for x in re.findall(r"lavfi\.freezedetect\.freeze_duration:\s*([\d.]+)", err)]
    if len(freeze_starts) > len(freeze_durs):
        freeze_durs.append(max(0.0, d - freeze_starts[-1]))
    flags = []
    if sum(black_durs) > 0.3:
        flags.append("black-frames")
    if freeze_durs and (max(freeze_durs) >= 1.5 or sum(freeze_durs) > 0.4 * max(1.0, d)):
        flags.append("frozen-video")
    if not streams.get("has_video"):
        flags.append("missing-video")
    return {
        "width": streams.get("width"),
        "height": streams.get("height"),
        "has_audio": streams.get("has_audio"),
        "black_seconds": round(sum(black_durs), 2),
        "freeze_seconds": round(sum(freeze_durs), 2),
        "flags": flags,
    }


def strip_stage_tags(text):
    """Remove inline DOP performance tags like [pause], [whisper], *emphasis*, and ellipses for fair WER comparison."""
    t = re.sub(r"\[[^\]]*\]", " ", text or "")
    t = t.replace("*", " ").replace("...", " ")
    t = re.sub(r"[^\w\s\u0900-\u097F]", " ", t, flags=re.UNICODE)
    return [w.lower() for w in t.split() if w]


def compute_wer(expected_text, transcript_text):
    """Word-level Levenshtein WER + missing/extra words between expected script and ASR transcript."""
    ref = strip_stage_tags(expected_text)
    hyp = strip_stage_tags(transcript_text)
    if not ref:
        return {"wer": 0.0 if not hyp else 1.0, "word_accuracy": 1.0 if not hyp else 0.0, "missing_words": [], "extra_words": hyp}
    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    wer = dp[n][m] / max(1, n)
    sm = difflib.SequenceMatcher(None, ref, hyp)
    missing, extra = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            missing.extend(ref[i1:i2])
        if tag in ("replace", "insert"):
            extra.extend(hyp[j1:j2])
    return {
        "wer": round(wer, 3),
        "word_accuracy": round(max(0.0, 1.0 - wer), 3),
        "missing_words": missing,
        "extra_words": extra,
    }


def _gemini_qc_call(parts, schema=None):
    """Call Gemini Flash on Vertex generateContent using camera_roll auth/project."""
    from camera_roll import get_token, CONFIG  # lazy import so offline audio QC works standalone

    proj = os.environ.get("AGY_PROJECT") or CONFIG["lanes"][CONFIG["default_lane"]].get("project")
    if not proj:
        raise RuntimeError("AGY_PROJECT is not set")
    token = get_token()
    url = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/{QC_LOCATION}/publishers/google/models/{QC_MODEL}:generateContent"
    gen_cfg = {"temperature": 0.0, "responseMimeType": "application/json"}
    if schema:
        gen_cfg["responseSchema"] = schema
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_cfg}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    cand = (resp.get("candidates") or [{}])[0]
    txt = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    return json.loads(txt)


def asr_check(video, expected_text="", no_llm=False):
    """Transcribe clip audio via Gemini Flash and score word accuracy against expected_text."""
    if no_llm:
        return {"asr_skipped": "disabled", "flags": []}
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav],
            check=True,
        )
        audio_b64 = base64.b64encode(open(wav, "rb").read()).decode()
    except Exception as e:
        return {"asr_skipped": f"audio-extract-failed: {e}", "flags": []}
    finally:
        if os.path.exists(wav):
            os.remove(wav)

    prompt = (
        "Transcribe the spoken dialogue in this audio clip verbatim in its original language/script "
        "(use Latin script for English/Hinglish unless clearly Devanagari). "
        "If no words are spoken, return an empty string for transcript. "
        "Return JSON with fields: transcript (string), language (string), intelligible (boolean)."
    )
    schema = {
        "type": "OBJECT",
        "properties": {
            "transcript": {"type": "STRING"},
            "language": {"type": "STRING"},
            "intelligible": {"type": "BOOLEAN"},
        },
        "required": ["transcript", "intelligible"],
    }
    try:
        res = _gemini_qc_call(
            [{"inlineData": {"mimeType": "audio/wav", "data": audio_b64}}, {"text": prompt}],
            schema=schema,
        )
    except Exception as e:
        return {"asr_skipped": str(e)[:160], "flags": []}

    transcript = (res.get("transcript") or "").strip()
    flags = []
    if expected_text and strip_stage_tags(expected_text):
        scores = compute_wer(expected_text, transcript)
        if scores["wer"] > 0.25 or not res.get("intelligible", True):
            flags.append("dialogue-mismatch")
    else:
        scores = {"wer": 0.0 if not transcript else 1.0, "word_accuracy": 1.0 if not transcript else 0.0, "missing_words": [], "extra_words": strip_stage_tags(transcript)}
        if transcript:
            flags.append("hallucinated-speech")
    return {"transcript": transcript, "language": res.get("language"), "intelligible": res.get("intelligible", True), **scores, "flags": flags}


def visual_check(contact_png, refs=(), expected_action="", no_llm=False):
    """Evaluate contact sheet (and optional bible/previous-shot refs) for face drift, continuity, captions, and artifacts."""
    if no_llm:
        return {"visual_skipped": "disabled", "flags": []}
    if not contact_png or not os.path.exists(contact_png):
        return {"visual_skipped": "missing-contact-sheet", "flags": []}

    parts = []
    ref_labels = []
    for idx, rpath in enumerate(refs or ()):
        if rpath and os.path.exists(rpath):
            mt = "image/png" if rpath.lower().endswith(".png") else "image/jpeg"
            parts.append({"inlineData": {"mimeType": mt, "data": base64.b64encode(open(rpath, "rb").read()).decode()}})
            ref_labels.append(f"Reference image {idx+1}: {os.path.basename(rpath)}")

    parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(open(contact_png, "rb").read()).decode()}})
    prompt = (
        "You are a film Script Supervisor reviewing a 5-frame chronological contact sheet from a generated video take"
        + (f" against the attached character/continuity reference image(s) ({', '.join(ref_labels)})." if ref_labels else ".")
        + (f"\nExpected action beat: {expected_action}" if expected_action else "")
        + "\nEvaluate strictly and return JSON:\n"
        "- face_consistency (integer 1-5, or 5 if no person/ref): 5=identical identity across frames & refs, 1=clear face drift or borrowed face\n"
        "- wardrobe_consistency (integer 1-5): 5=clothing/glasses/props/lighting match across frames & refs, 1=drifted or changed\n"
        "- unprompted_captions (boolean): true if burned-in subtitles/text captions appear on screen\n"
        "- morphing_or_artifacts (boolean): true if severe anatomy distortion, extra limbs, or broken physics\n"
        "- action_match (boolean): true if frames match the expected action (or true if none specified)\n"
        "- issues (array of short <=100-char strings describing concrete defects, empty if clean)"
    )
    parts.append({"text": prompt})
    schema = {
        "type": "OBJECT",
        "properties": {
            "face_consistency": {"type": "INTEGER"},
            "wardrobe_consistency": {"type": "INTEGER"},
            "unprompted_captions": {"type": "BOOLEAN"},
            "morphing_or_artifacts": {"type": "BOOLEAN"},
            "action_match": {"type": "BOOLEAN"},
            "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["face_consistency", "wardrobe_consistency", "unprompted_captions", "morphing_or_artifacts", "action_match", "issues"],
    }
    try:
        res = _gemini_qc_call(parts, schema=schema)
    except Exception as e:
        return {"visual_skipped": str(e)[:160], "flags": []}

    flags = []
    if res.get("face_consistency", 5) <= 2:
        flags.append("face-drift")
    if res.get("wardrobe_consistency", 5) <= 2:
        flags.append("continuity-drift")
    if res.get("unprompted_captions"):
        flags.append("unprompted-captions")
    if res.get("morphing_or_artifacts"):
        flags.append("visual-artifacts")
    if expected_action and not res.get("action_match", True):
        flags.append("action-mismatch")
    return {**res, "flags": flags}


def full_qc(video, profile="dialogue", expected_text="", refs=(), action="", no_llm=False):
    """Run audio envelope + prosody + deterministic visual + optional ASR & multimodal continuity QC."""
    sp = speech(video, profile=profile)
    c_path = contact(video)
    l_path = last(video)
    vb = visual_basic(video)
    flags = list(sp.get("flags", [])) + [f for f in vb.get("flags", []) if f not in sp.get("flags", [])]

    asr_res = asr_check(video, expected_text=expected_text, no_llm=no_llm) if (expected_text or sp.get("has_speech")) else {"flags": []}
    vis_res = visual_check(c_path, refs=refs, expected_action=action, no_llm=no_llm)
    for f in asr_res.get("flags", []) + vis_res.get("flags", []):
        if f not in flags:
            flags.append(f)

    out = {
        **sp,
        "contact": c_path,
        "last_frame": l_path,
        "visual_basic": {k: v for k, v in vb.items() if k != "flags"},
        "asr": {k: v for k, v in asr_res.items() if k != "flags"},
        "visual_qc": {k: v for k, v in vis_res.items() if k != "flags"},
        "flags": flags,
    }
    return out


def _manifest_lookup(manifest_path):
    if not manifest_path or not os.path.exists(manifest_path):
        return {}
    shots = json.load(open(manifest_path))
    return {str(s.get("id")): s for s in shots if s.get("id")}


def scene(d, profile="dialogue", manifest=None, no_llm=False):
    rep = {}
    by_id = _manifest_lookup(manifest)
    for v in sorted(glob.glob(os.path.join(d, "*.mp4"))):
        name = os.path.basename(v)
        shot_id = re.sub(r"_take\d+\.mp4$", "", name)
        s = by_id.get(shot_id, {})
        exp = s.get("dialogue") or ""
        if isinstance(exp, list):
            exp = " ".join(x.get("line", "") for x in exp)
        rep[name] = full_qc(
            v,
            profile=s.get("profile", profile),
            expected_text=exp,
            refs=s.get("images", ()),
            action=s.get("action", ""),
            no_llm=no_llm,
        )
    json.dump(rep, open(os.path.join(d, "qc.json"), "w"), indent=2)
    for k, r in rep.items():
        wer = r.get("asr", {}).get("wer")
        wer_s = f"  wer={wer}" if wer is not None else ""
        print(f"{k:28s} {r['duration']:5.1f}s  speech_end={r.get('speech_end')}  margin={r.get('margin')}{wer_s}  flags={r['flags']}")
    build_board(d)
    try:
        proto_dir = os.path.abspath(os.path.join(HERE, "..", "..", "studio-protocol", "scripts"))
        if proto_dir not in sys.path:
            sys.path.insert(0, proto_dir)
        import studio_board
        prod_dir = os.path.dirname(os.path.dirname(os.path.abspath(d.rstrip("/"))))
        studio_board.refresh_hub(prod_dir)
    except Exception:
        pass
    return rep


def build_board(scene_dir, out=None, embed=False, embed_video=False):
    """Generate a dark-mode HTML Dailies Review Board with inline HTML5 <video> playback + contact strips."""
    import html as _html
    qc_path = os.path.join(scene_dir, "qc.json")
    qc = json.load(open(qc_path)) if os.path.exists(qc_path) else {}
    out = out or os.path.join(scene_dir, "dailies_board.html")
    out_dir = os.path.dirname(os.path.abspath(out))
    shots = {}
    # Include both qc.json entries and any .mp4 files in scene_dir even if qc.json wasn't run yet
    all_mp4s = {os.path.basename(p) for p in glob.glob(os.path.join(scene_dir, "*.mp4"))}
    for name in sorted(set(qc.keys()) | all_mp4s):
        sid = re.sub(r"_take\d+\.mp4$", "", os.path.splitext(name)[0] if not name.endswith(".mp4") else name)
        shots.setdefault(sid, []).append((name, qc.get(name, {})))

    cards = []
    for sid, takes in shots.items():
        take_html = []
        for name, info in takes:
            vpath = os.path.join(scene_dir, name)
            vid_src = ""
            if os.path.exists(vpath):
                if embed_video:
                    with open(vpath, "rb") as vf:
                        vid_src = "data:video/mp4;base64," + base64.b64encode(vf.read()).decode()
                else:
                    vid_src = os.path.relpath(os.path.abspath(vpath), out_dir)
            cpath = info.get("contact") or os.path.join(scene_dir, os.path.splitext(name)[0] + "_contact.png")
            img_src = ""
            if os.path.exists(cpath):
                if embed:
                    with open(cpath, "rb") as f:
                        img_src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                else:
                    img_src = os.path.relpath(os.path.abspath(cpath), out_dir)
            flags = info.get("flags") or []
            badges = "".join(f"<span class='flag'>{_html.escape(fl)}</span>" for fl in flags) or "<span class='ok'>CLEAN</span>"
            wer = info.get("asr", {}).get("wer")
            tr = info.get("asr", {}).get("transcript") or ""
            vis = info.get("visual_qc", {})
            meta = f"dur={info.get('duration')}s · margin={info.get('margin')}s · f0={info.get('f0_std_semitones')}"
            if wer is not None:
                meta += f" · WER={wer}"
            if vis.get("face_consistency") is not None:
                meta += f" · face={vis['face_consistency']}/5"
            prov_html = ""
            sidecar = os.path.join(scene_dir, name + ".meta.json")
            if os.path.exists(sidecar):
                with open(sidecar, encoding="utf-8") as pf:
                    pm = json.load(pf)
                refs_txt = ", ".join(os.path.basename(r.get("path", "")) + (f" #{r['sha256_16'][:8]}" if r.get("sha256_16") else "") for r in pm.get("refs", [])) or "none"
                prov_html = (
                    f"<details class='prov'><summary>🔍 Exact Prompt & Resources ({_html.escape(pm.get('model',''))})</summary>"
                    f"<div class='meta'>Refs: {_html.escape(refs_txt)} · Chars: {_html.escape(', '.join(pm.get('characters',[])) or '—')}</div>"
                    f"<pre>{_html.escape(pm.get('prompt',''))}</pre></details>"
                )
            poster_attr = f" poster='{img_src}'" if img_src else ""
            player_html = (
                f"<video class='vid' controls playsinline preload='metadata'{poster_attr} src='{vid_src}'></video>"
                if vid_src
                else ""
            )
            strip_html = (
                f"<details class='strip'><summary>🎞 5-Frame Continuity Strip</summary><img src='{img_src}' alt='{_html.escape(name)}'/></details>"
                if (img_src and vid_src)
                else (f"<img src='{img_src}' alt='{_html.escape(name)}'/>" if img_src else "")
            )
            take_html.append(
                f"<div class='take' data-shot='{_html.escape(sid)}' data-take='{_html.escape(name)}'>"
                f"<div class='th'><strong>▶ {_html.escape(name)}</strong> <div>{badges}</div></div>"
                + player_html
                + strip_html
                + f"<div class='meta'>{_html.escape(meta)}</div>"
                + (f"<div class='tr'>\"{_html.escape(tr)}\"</div>" if tr else "")
                + prov_html
                + f"<input class='note' placeholder='💬 Director note for {_html.escape(sid)}...' oninput=\"note('{_html.escape(sid)}',this.value)\"/>"
                + f"<button onclick=\"pick('{_html.escape(sid)}','{_html.escape(name)}',this)\">✓ Select Take</button></div>"
            )
        cards.append(f"<section class='shot'><h2>Shot {_html.escape(sid)}</h2><div class='grid'>{''.join(take_html)}</div></section>")

    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Dailies Board — {_html.escape(os.path.basename(os.path.abspath(scene_dir)))}</title>
<style>body{{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:24px}}h1,h2{{margin:0 0 12px}}.bar{{position:sticky;top:0;z-index:10;background:#1b1b1b;padding:12px 16px;border:1px solid #333;border-radius:8px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center}}.shot{{margin-bottom:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:14px}}.take{{background:#1a1a1a;border:2px solid #2b2b2b;border-radius:8px;padding:12px}}.take.picked{{border-color:#22c55e}}.vid{{width:100%;max-height:460px;background:#000;border-radius:6px;margin:8px 0}}.take img{{width:100%;border-radius:4px;margin:6px 0}}.strip{{font-size:11px;color:#94a3b8;margin:4px 0}}.strip summary{{cursor:pointer}}.th{{display:flex;justify-content:space-between;align-items:center}}.ok{{background:#14532d;color:#86efac;padding:2px 8px;border-radius:99px;font-size:12px}}.flag{{background:#7f1d1d;color:#fca5a5;padding:2px 8px;border-radius:99px;font-size:12px;margin-left:4px}}.meta,.tr{{font-size:12px;color:#aaa;margin:4px 0}}details.prov{{background:#12151c;border:1px solid #2b3445;border-radius:6px;padding:6px 8px;margin:6px 0;font-size:11px}}details.prov summary{{cursor:pointer;color:#93c5fd;font-weight:600}}details.prov pre{{white-space:pre-wrap;color:#cbd5e1;max-height:140px;overflow:auto;margin:6px 0 0}}.note{{width:100%;background:#0e1015;border:1px solid #333;color:#eee;padding:6px 8px;border-radius:5px;font-size:12px;margin-top:6px;box-sizing:border-box}}button{{margin-top:8px;background:#2563eb;color:#fff;border:0;padding:6px 12px;border-radius:6px;cursor:pointer;font-weight:600}}</style></head>
<body><div class="bar"><div><strong>🎬 Dailies Screening Room</strong> · {_html.escape(scene_dir)}</div><code id="sel">No takes selected</code></div>
{''.join(cards)}
<script>document.addEventListener('play',e=>{{document.querySelectorAll('video').forEach(v=>{{if(v!==e.target)v.pause();}});}},true);const picks={{}},notes={{}};function refresh(){{const p=Object.entries(picks).map(([k,v])=>k+'='+v).join(', ');const n=Object.entries(notes).filter(([,v])=>v).map(([k,v])=>k+': '+v).join(' | ');document.getElementById('sel').textContent=(p?'Approve: '+p:'')+(p&&n?' · ':'')+(n?'Notes: '+n:'')||'No takes selected';}}function pick(s,t,btn){{picks[s]=t;document.querySelectorAll(`.take[data-shot="${{s}}"]`).forEach(e=>e.classList.remove('picked'));btn.closest('.take').classList.add('picked');refresh();}}function note(s,v){{notes[s]=v;refresh();}}</script></body></html>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("contact", "speech", "last"):
        s = sub.add_parser(c)
        s.add_argument("--video", required=True)
        s.add_argument("--out")
        if c == "contact":
            s.add_argument("--frames", type=int, default=5)
        if c == "speech":
            s.add_argument("--floor", type=float, default=-38.0)
            s.add_argument("--hold", type=float, default=0.45)
            s.add_argument("--profile", default="dialogue", choices=list(PROSODY_PROFILES))

    a_p = sub.add_parser("asr")
    a_p.add_argument("--video", required=True)
    a_p.add_argument("--expected", default="")
    a_p.add_argument("--no-llm", action="store_true")

    v_p = sub.add_parser("visual")
    v_p.add_argument("--video", required=True)
    v_p.add_argument("--ref", action="append", default=[])
    v_p.add_argument("--action", default="")
    v_p.add_argument("--no-llm", action="store_true")

    f_p = sub.add_parser("full")
    f_p.add_argument("--video", required=True)
    f_p.add_argument("--expected", default="")
    f_p.add_argument("--ref", action="append", default=[])
    f_p.add_argument("--action", default="")
    f_p.add_argument("--profile", default="dialogue", choices=list(PROSODY_PROFILES))
    f_p.add_argument("--no-llm", action="store_true")

    s = sub.add_parser("scene")
    s.add_argument("--dir", required=True)
    s.add_argument("--profile", default="dialogue", choices=list(PROSODY_PROFILES))
    s.add_argument("--manifest")
    s.add_argument("--no-llm", action="store_true")

    b = sub.add_parser("board")
    b.add_argument("--dir", required=True)
    b.add_argument("--out")
    b.add_argument("--embed", action="store_true", help="embed contact PNGs as base64")
    b.add_argument("--embed-video", action="store_true", help="embed MP4 videos as base64 for single-file portability")

    a = ap.parse_args()
    if a.cmd == "contact":
        print(contact(a.video, a.frames, a.out))
    elif a.cmd == "last":
        print(last(a.video, a.out))
    elif a.cmd == "speech":
        print(json.dumps(speech(a.video, a.floor, a.hold, profile=a.profile), indent=2))
    elif a.cmd == "asr":
        print(json.dumps(asr_check(a.video, a.expected, no_llm=a.no_llm), indent=2, ensure_ascii=False))
    elif a.cmd == "visual":
        c_png = contact(a.video)
        res = {"visual_basic": visual_basic(a.video), "visual_qc": visual_check(c_png, refs=a.ref, expected_action=a.action, no_llm=a.no_llm)}
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif a.cmd == "full":
        print(json.dumps(full_qc(a.video, profile=a.profile, expected_text=a.expected, refs=a.ref, action=a.action, no_llm=a.no_llm), indent=2, ensure_ascii=False))
    elif a.cmd == "board":
        print(build_board(a.dir, out=a.out, embed=a.embed, embed_video=a.embed_video))
    else:
        scene(a.dir, a.profile, manifest=a.manifest, no_llm=a.no_llm)


if __name__ == "__main__":
    main()
