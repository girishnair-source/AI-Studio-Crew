#!/usr/bin/env python3
"""camera_roll.py — roll video clips through Vertex Interactions API (Omni) & Vertex Veo API.

Single config block (CONFIG) for model IDs / hosts / projects — edit here only.
Auth providers (first that works): $AGY_ACCESS_TOKEN, stubby CorpLogin (gLinux), gcloud.
Features: text/image/reference-to-video, Veo 3.1 adapter (:predictLongRunning), parallel
shots via a manifest, retry with backoff + lane fallback on capacity errors, typed
safety-block reporting, last-frame extraction for chaining, token usage extraction,
draft-to-hero promotion (upscale or hero re-roll), and ledger append for Line Producer.

Usage (single shot):
  camera_roll.py roll --prompt "..." --duration 7s --aspect 9:16 [--image ref.png ...] --out take1.mp4
Usage (manifest, parallel):
  camera_roll.py batch --manifest shots.json --parallel 6 [--draft]
Usage (draft -> hero 1080p/4k):
  camera_roll.py promote --summary production/dailies/EP01_SC04/scene_summary.json --resolution 1080p [--method upscale|reroll]
Other:
  camera_roll.py last-frame --video take1.mp4 --out take1_last.png
  camera_roll.py doctor
"""
import argparse, base64, concurrent.futures as cf, csv, getpass, json, mimetypes, os, shutil, subprocess, sys, time, urllib.error, urllib.request

# ───────────────────────────── CONFIG (the only place model/host names live) ─────────────────────────────
CONFIG = {
    "lanes": {
        # name: {api, model, host, project, ...}. Lane names are stable; model ids change here only.
        "omni-1.2": {"api": "interactions", "model": "gemini-omni-1.2-flash", "host": "aiplatform.googleapis.com", "project": os.environ.get("AGY_PROJECT", ""), "min_s": 3, "max_s": 15},
        "omni-1.1": {"api": "interactions", "model": "gemini-omni-1.1-flash-preview", "host": "aiplatform.googleapis.com", "project": os.environ.get("AGY_PROJECT", ""), "min_s": 3, "max_s": 15},
        "veo-3.1": {"api": "veo", "model": "veo-3.1-generate-001", "host": "us-central1-aiplatform.googleapis.com", "location": "us-central1", "project": os.environ.get("AGY_PROJECT", ""), "min_s": 4, "max_s": 8},
        "veo-3.1-fast": {"api": "veo", "model": "veo-3.1-fast-generate-001", "host": "us-central1-aiplatform.googleapis.com", "location": "us-central1", "project": os.environ.get("AGY_PROJECT", ""), "min_s": 4, "max_s": 8},
        "veo-3.1-lite": {"api": "veo", "model": "veo-3.1-lite-generate-001", "host": "us-central1-aiplatform.googleapis.com", "location": "us-central1", "project": os.environ.get("AGY_PROJECT", ""), "min_s": 4, "max_s": 8},
    },
    "default_lane": os.environ.get("AGY_LANE", "omni-1.2"),
    "fallback_lane": os.environ.get("AGY_FALLBACK_LANE", "omni-1.1"),
    "draft_resolution": os.environ.get("AGY_DRAFT_RES", "360p"),
    # Durations are DECIDED PER SHOT from the script (studio-protocol/scripts/duration.py); these are only the model's bounds.
    "min_clip_seconds": 3,
    "max_clip_seconds": 15,
    "resolutions": ["360p", "720p", "1080p", "4k"],
    "max_reference_images": 6,
    "retries": 3,
    "backoff_s": [8, 20, 45],
    "poll_s": 5,
    "timeout_s": 420,
    "ledger": os.path.join(os.environ.get("AGY_PRODUCTION_DIR", "production"), "reports", "ledger.csv"),
}
# Optional pre-release lane for internal testers: set AGY_PREVIEW_MODEL / AGY_PREVIEW_HOST / AGY_PREVIEW_PROJECT in the environment.
if os.environ.get("AGY_PREVIEW_MODEL"):
    CONFIG["lanes"]["preview"] = {"api": os.environ.get("AGY_PREVIEW_API", "interactions"), "model": os.environ["AGY_PREVIEW_MODEL"], "host": os.environ.get("AGY_PREVIEW_HOST", "aiplatform.googleapis.com"), "project": os.environ.get("AGY_PREVIEW_PROJECT", os.environ.get("AGY_PROJECT", "")), "min_s": 3, "max_s": 15}
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────


class RollError(Exception):
    def __init__(self, kind, message, detail=""):
        super().__init__(message)
        self.kind = kind
        self.detail = detail


# ── auth ────────────────────────────────────────────────────────────────────────────────────────────────
def _token_env():
    return os.environ.get("AGY_ACCESS_TOKEN") or None


def _token_stubby():
    if not shutil.which("stubby") and not os.path.exists("/usr/bin/stubby"):
        return None
    user = getpass.getuser()
    req = f'target: {{ scope: GAIA_USER name: "{user}@google.com" }} target_credential: {{ type: OAUTH2_TOKEN oauth2_attributes: {{ scope: "https://www.googleapis.com/auth/cloud-platform" }} }}'
    try:
        r = subprocess.run(["/usr/bin/stubby", "--proto2", "call", "blade:sso", "CorpLogin.Exchange"], input=req, text=True, capture_output=True, timeout=30)
        for line in r.stdout.splitlines():
            if "oauth2_token:" in line:
                return line.split('"')[1]
    except Exception:
        return None
    return None


def _token_gcloud():
    if not shutil.which("gcloud"):
        return None
    try:
        return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True, timeout=30).strip() or None
    except Exception:
        return None


_TOKEN_CACHE = {"t": None, "ts": 0, "src": None}


def get_token(force=False):
    if not force and _TOKEN_CACHE["t"] and time.time() - _TOKEN_CACHE["ts"] < 45 * 60:
        return _TOKEN_CACHE["t"]
    for name, fn in (("env", _token_env), ("stubby", _token_stubby), ("gcloud", _token_gcloud)):
        t = fn()
        if t:
            _TOKEN_CACHE.update(t=t, ts=time.time(), src=name)
            return t
    raise RollError("auth", "No access token: set AGY_ACCESS_TOKEN, or run on gLinux (stubby), or `gcloud auth login` with your corp account.")


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────
def media_part(path, kind):
    mt, _ = mimetypes.guess_type(path)
    mt = mt or {"image": "image/png", "video": "video/mp4", "audio": "audio/wav"}[kind]
    if mt == "audio/x-wav":
        mt = "audio/wav"
    part = {"type": kind, "mime_type": mt}
    if path.startswith("gs://"):
        part["uri"] = path
    else:
        with open(path, "rb") as f:
            part["data"] = base64.b64encode(f.read()).decode()
    return part


def _http(method, url, token, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        if e.code == 401:
            raise RollError("auth", "401 UNAUTHENTICATED — token invalid/expired", txt[:400])
        if e.code == 403:
            raise RollError("access", "403 PERMISSION_DENIED — account lacks access to project/endpoint", txt[:400])
        if e.code == 429 or e.code >= 500:
            raise RollError("capacity", f"HTTP {e.code}", txt[:400])
        raise RollError("request", f"HTTP {e.code}", txt[:800])


def ledger(row):
    try:
        os.makedirs(os.path.dirname(CONFIG["ledger"]), exist_ok=True)
        new = not os.path.exists(CONFIG["ledger"])
        with open(CONFIG["ledger"], "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts", "id", "lane", "model", "task", "duration", "resolution", "status", "seconds", "interaction_id", "gen_tokens", "note"])
            w.writerow(row)
    except Exception:
        pass


def extract_usage(resp):
    """Extract token counts from Interactions API response usage block."""
    u = resp.get("usage") or {}
    by_mod = u.get("output_tokens_by_modality") or {}
    gen_tokens = int(by_mod.get("video") or u.get("video_tokens") or u.get("output_tokens") or 0)
    llm_in = int(u.get("total_input_tokens") or u.get("input_tokens") or 0)
    llm_out = int(u.get("total_output_tokens") or u.get("output_tokens") or 0)
    return {"gen_tokens": gen_tokens, "llm_in": llm_in, "llm_out": llm_out}


# ── core roll ────────────────────────────────────────────────────────────────────────────────────────────
def normalize_duration(duration, lane_cfg=None):
    """Accept '7s', '7', 7, 7.4 -> validate against lane bounds, return 'Ns'."""
    try:
        v = float(str(duration).rstrip("s"))
    except ValueError:
        raise RollError("request", f"bad duration {duration!r}")
    v = int(round(v))
    lo = (lane_cfg or {}).get("min_s", CONFIG["min_clip_seconds"])
    hi = (lane_cfg or {}).get("max_s", CONFIG["max_clip_seconds"])
    if v < lo or v > hi:
        raise RollError("request", f"duration {v}s outside lane bounds {lo}-{hi}s; split or merge the shot (duration.py)")
    return f"{v}s"


def _classify_error(msg, code="", has_usage=True):
    low_m, low_c = (msg or "").lower(), str(code or "").lower()
    if any(k in low_m or k in low_c for k in ("safety", "prohibited", "blocked", "content_blocked", "prohibited_content")):
        return "safety"
    if not has_usage:
        return "capacity"
    return "failed"


def _roll_interactions(lane_name, lane, prompt, out, task, duration, aspect, resolution, images, audio, video, shot_id):
    token = get_token()
    inputs = [{"type": "text", "text": prompt}] + [media_part(p, "image") for p in images]
    if video:
        inputs.append(media_part(video, "video"))
    if audio:
        inputs.append(media_part(audio, "audio"))
    if task == "text_to_video" and images:
        task = "reference_to_video"
    rf = {"type": "video"}
    if task == "upscale":
        rf["resolution"] = resolution
    elif task != "extend":
        rf.update(aspect_ratio=aspect, resolution=resolution, duration=duration)
    payload = {
        "model": lane["model"],
        "input": inputs,
        "generation_config": {"thinking_summaries": "auto", "video_config": {"task": task}},
        "response_format": rf,
        "background": True,
    }
    base = f"https://{lane['host']}/v1beta1/projects/{lane['project']}/locations/global/interactions"
    t0 = time.time()
    resp = _http("POST", base, token, payload)
    iid = resp.get("id", "")
    status = resp.get("status")
    while status in ("in_progress", "queued", None):
        if time.time() - t0 > CONFIG["timeout_s"]:
            raise RollError("timeout", f"interaction {iid} exceeded {CONFIG['timeout_s']}s")
        time.sleep(CONFIG["poll_s"])
        resp = _http("GET", f"{base}/{iid}", get_token())
        status = resp.get("status")
    if status != "completed":
        errs = resp.get("errors") or [{}]
        msg = errs[0].get("message", "")
        code = errs[0].get("code", "")
        kind = _classify_error(msg, code, has_usage=bool(resp.get("usage")))
        ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, kind, round(time.time() - t0, 1), iid, 0, msg[:120]])
        raise RollError(kind, f"interaction {status}: {msg}", json.dumps(errs)[:600])

    usage = extract_usage(resp)
    out_containers = resp.get("outputs") or [s for s in resp.get("steps", []) if s.get("type") == "model_output"]
    for o in out_containers:
        for item in (o.get("content") or [o]):
            if item.get("type") == "video" and item.get("data"):
                os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
                with open(out, "wb") as f:
                    f.write(base64.b64decode(item["data"]))
                ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, "ok", round(time.time() - t0, 1), iid, usage["gen_tokens"], ""])
                return {"out": out, "lane": lane_name, "model": lane["model"], "interaction_id": iid, "seconds": round(time.time() - t0, 1), **usage}
    raise RollError("failed", "completed but no video in response", json.dumps(resp)[:600])


def _roll_veo(lane_name, lane, prompt, out, task, duration, aspect, resolution, images, shot_id):
    """Roll via Vertex Veo :predictLongRunning + :fetchPredictOperation."""
    token = get_token()
    loc = lane.get("location", "us-central1")
    dur_sec = int(str(duration).rstrip("s"))
    instance = {"prompt": prompt}
    if images:
        if len(images) == 1 and task in ("image_to_video", "text_to_video"):
            mp = media_part(images[0], "image")
            instance["image"] = {"bytesBase64Encoded": mp["data"], "mimeType": mp["mime_type"]} if "data" in mp else {"gcsUri": mp["uri"], "mimeType": mp["mime_type"]}
        else:
            refs = []
            for p in images:
                mp = media_part(p, "image")
                img_obj = {"bytesBase64Encoded": mp["data"], "mimeType": mp["mime_type"]} if "data" in mp else {"gcsUri": mp["uri"], "mimeType": mp["mime_type"]}
                refs.append({"image": img_obj, "referenceType": "asset"})
            instance["referenceImages"] = refs
    params = {"aspectRatio": aspect, "durationSeconds": dur_sec, "sampleCount": 1, "personGeneration": "allow_adult"}
    if resolution in ("720p", "1080p"):
        params["resolution"] = resolution
    base_model = f"https://{lane['host']}/v1/projects/{lane['project']}/locations/{loc}/publishers/google/models/{lane['model']}"
    t0 = time.time()
    op = _http("POST", f"{base_model}:predictLongRunning", token, {"instances": [instance], "parameters": params})
    op_name = op.get("name", "")
    while not op.get("done"):
        if time.time() - t0 > CONFIG["timeout_s"]:
            raise RollError("timeout", f"veo operation {op_name} exceeded {CONFIG['timeout_s']}s")
        time.sleep(CONFIG["poll_s"])
        op = _http("POST", f"{base_model}:fetchPredictOperation", get_token(), {"operationName": op_name})
    if op.get("error"):
        err = op["error"]
        msg = err.get("message", "")
        code = err.get("code", "")
        kind = _classify_error(msg, code, has_usage=True)
        ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, kind, round(time.time() - t0, 1), op_name, 0, msg[:120]])
        raise RollError(kind, f"veo error: {msg}", json.dumps(err)[:600])

    videos = (op.get("response") or {}).get("videos") or (op.get("response") or {}).get("generatedSamples") or []
    for v in videos:
        b64 = v.get("bytesBase64Encoded") or (v.get("video") or {}).get("bytesBase64Encoded")
        if b64:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "wb") as f:
                f.write(base64.b64decode(b64))
            ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, "ok", round(time.time() - t0, 1), op_name, 0, ""])
            return {"out": out, "lane": lane_name, "model": lane["model"], "interaction_id": op_name, "seconds": round(time.time() - t0, 1), "gen_tokens": 0, "llm_in": 0, "llm_out": 0}
    raise RollError("failed", "veo completed but no video bytes in response", json.dumps(op)[:600])


def _roll_dry_run(prompt, out, duration, aspect, resolution, shot_id):
    """Synthesize a valid test MP4 with moving testsrc2 + modulated tone (zero API cost/auth)."""
    dur_s = int(str(duration).rstrip("s"))
    w, h = (360, 640) if aspect == "9:16" else ((480, 480) if aspect == "1:1" else (640, 360))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    speech_dur = max(1.0, dur_s - 0.8)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=24:d={dur_s}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={speech_dur}",
            "-af", f"adelay=300|300,apad=whole_dur={dur_s}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", str(dur_s), out,
        ],
        check=True,
    )
    ledger([time.strftime("%F %T"), shot_id, "dry-run", "synthetic-ffmpeg", "dry_run", duration, resolution, "ok", 0.1, "dry-run", 0, ""])
    return {"out": out, "lane": "dry-run", "model": "synthetic-ffmpeg", "interaction_id": "dry-run", "seconds": 0.1, "gen_tokens": 0, "llm_in": 0, "llm_out": 0}


def roll_once(lane_name, prompt, out, task="text_to_video", duration="8s", aspect="9:16", resolution="720p", images=(), audio=None, video=None, shot_id="", dry_run=False):
    if dry_run or os.environ.get("AGY_DRY_RUN") == "1":
        duration = normalize_duration(duration)
        return _roll_dry_run(prompt, out, duration, aspect, resolution, shot_id)
    if lane_name not in CONFIG["lanes"]:
        raise RollError("request", f"unknown lane {lane_name!r}; available: {list(CONFIG['lanes'])}")
    lane = CONFIG["lanes"][lane_name]
    if not lane.get("project"):
        raise RollError("request", "AGY_PROJECT is not set — export your Google Cloud project id (the one with Vertex AI enabled)")
    duration = normalize_duration(duration, lane)
    if len(images) > CONFIG["max_reference_images"]:
        raise RollError("request", f"{len(images)} reference images > {CONFIG['max_reference_images']}")
    api = lane.get("api", "interactions")
    if api == "veo":
        return _roll_veo(lane_name, lane, prompt, out, task, duration, aspect, resolution, images, shot_id)
    return _roll_interactions(lane_name, lane, prompt, out, task, duration, aspect, resolution, images, audio, video, shot_id)


def roll(prompt, out, lane=None, **kw):
    """Roll with retries; capacity -> backoff then fallback lane; auth -> refresh once; safety -> raise immediately."""
    lane = lane or CONFIG["default_lane"]
    lanes = [lane]
    if CONFIG["fallback_lane"] and CONFIG["fallback_lane"] != lane:
        lanes.append(CONFIG["fallback_lane"])
    last = None
    for ln in lanes:
        for i in range(CONFIG["retries"]):
            try:
                return roll_once(ln, prompt, out, **kw)
            except RollError as e:
                last = e
                if e.kind in ("safety", "request"):
                    raise
                if e.kind == "auth" and i == 0:
                    get_token(force=True)
                    continue
                if e.kind in ("capacity", "timeout", "failed"):
                    time.sleep(CONFIG["backoff_s"][min(i, len(CONFIG["backoff_s"]) - 1)])
                    continue
                if e.kind == "access":
                    break  # try next lane / project
    raise last


def promote_clip(draft_video, out, resolution="1080p", method="upscale", prompt="", duration="8s", aspect="9:16", images=(), lane=None, shot_id=""):
    """Promote a draft clip (e.g. 360p) to hero resolution (1080p/4k) via upscale or hero reroll."""
    if method == "upscale":
        return roll(prompt or "Upscale preserving exact motion, faces, lighting, and audio.", out, lane=lane, task="upscale", duration=duration, aspect=aspect, resolution=resolution, video=draft_video, shot_id=shot_id)
    return roll(prompt, out, lane=lane, task="reference_to_video" if images else "text_to_video", duration=duration, aspect=aspect, resolution=resolution, images=images, shot_id=shot_id)


# ── utilities ────────────────────────────────────────────────────────────────────────────────────────────
def last_frame(video, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", out], check=True)
    return out


def doctor():
    print("auth providers:")
    for name, fn in (("AGY_ACCESS_TOKEN", _token_env), ("stubby", _token_stubby), ("gcloud", _token_gcloud)):
        t = fn()
        print(f"  {name:16s} {'ok' if t else '—'}")
    if not os.environ.get("AGY_PROJECT"):
        print("  AGY_PROJECT         — not set (export AGY_PROJECT=<your-gcp-project>)")
    for ln, cfg in CONFIG["lanes"].items():
        api = cfg.get("api", "interactions")
        if not cfg.get("project"):
            print(f"  lane {ln:12s} [{api:12s}] {cfg['model']:30s} needs AGY_PROJECT")
            continue
        if api == "veo":
            loc = cfg.get("location", "us-central1")
            url = f"https://{cfg['host']}/v1/projects/{cfg['project']}/locations/{loc}/publishers/google/models/{cfg['model']}:fetchPredictOperation"
            body = {"operationName": f"projects/{cfg['project']}/locations/{loc}/publishers/google/models/{cfg['model']}/operations/0"}
        else:
            url = f"https://{cfg['host']}/v1beta1/projects/{cfg['project']}/locations/global/interactions"
            body = {}
        try:
            _http("POST", url, get_token(), body)
            print(f"  lane {ln:12s} [{api:12s}] {cfg['model']:30s} reachable  ✓")
        except RollError as e:
            tag = {"request": "✓ reachable", "auth": "✗ 401 token", "access": "✗ 403 no access", "capacity": "~ overloaded"}.get(e.kind, e.kind)
            print(f"  lane {ln:12s} [{api:12s}] {cfg['model']:30s} {tag}")
    print(f"default lane: {CONFIG['default_lane']}  fallback: {CONFIG['fallback_lane']}  draft res: {CONFIG['draft_resolution']}  clip bounds: {CONFIG['min_clip_seconds']}-{CONFIG['max_clip_seconds']}s  max refs: {CONFIG['max_reference_images']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("roll")
    r.add_argument("--prompt", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--task", default="text_to_video")
    r.add_argument("--duration", required=True, help="seconds, decided per shot by duration.py (e.g. 7s)")
    r.add_argument("--aspect", default="9:16")
    r.add_argument("--resolution", default="720p")
    r.add_argument("--image", action="append", default=[])
    r.add_argument("--audio")
    r.add_argument("--video")
    r.add_argument("--lane")
    r.add_argument("--id", default="")
    r.add_argument("--dry-run", action="store_true")

    b = sub.add_parser("batch")
    b.add_argument("--manifest", required=True)
    b.add_argument("--parallel", type=int, default=6)
    b.add_argument("--lane")
    b.add_argument("--draft", action="store_true", help="roll all shots at draft resolution (default 360p)")
    b.add_argument("--dry-run", action="store_true")

    pr = sub.add_parser("promote")
    pr.add_argument("--video", help="single draft video to promote")
    pr.add_argument("--summary", help="scene_summary.json with locked_takes to promote")
    pr.add_argument("--manifest", help="optional shots.json for reroll prompts/refs")
    pr.add_argument("--out", help="output path for single --video")
    pr.add_argument("--out-dir", help="output dir for --summary")
    pr.add_argument("--resolution", default="1080p")
    pr.add_argument("--method", choices=["upscale", "reroll"], default="upscale")
    pr.add_argument("--lane")

    lf = sub.add_parser("last-frame")
    lf.add_argument("--video", required=True)
    lf.add_argument("--out", required=True)
    sub.add_parser("doctor")

    a = ap.parse_args()
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "last-frame":
        print(last_frame(a.video, a.out))
        return
    if a.cmd == "roll":
        try:
            res = roll(a.prompt, a.out, lane=a.lane, task=a.task, duration=a.duration, aspect=a.aspect, resolution=a.resolution, images=a.image, audio=a.audio, video=a.video, shot_id=a.id, dry_run=a.dry_run)
            print(json.dumps({"status": "ok", **res}))
        except RollError as e:
            print(json.dumps({"status": e.kind, "message": str(e), "detail": e.detail}))
            sys.exit(2)
        return
    if a.cmd == "promote":
        if a.video:
            out = a.out or a.video.replace(".mp4", f"_{a.resolution}.mp4")
            res = promote_clip(a.video, out, resolution=a.resolution, method=a.method, lane=a.lane)
            print(json.dumps({"status": "ok", **res}))
            return
        if not a.summary:
            raise SystemExit("provide --video or --summary")
        summ = json.load(open(a.summary))
        by_id = {s["id"]: s for s in json.load(open(a.manifest))} if a.manifest else {}
        out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.summary))
        os.makedirs(out_dir, exist_ok=True)
        promoted = []
        for t in summ.get("locked_takes", []):
            s = by_id.get(t["shot"], {})
            out = os.path.join(out_dir, f"{t['shot']}_hero_{a.resolution}.mp4")
            res = promote_clip(t["take"], out, resolution=a.resolution, method=a.method, prompt=s.get("prompt", ""), duration=s.get("duration", "8s"), aspect=s.get("aspect", "9:16"), images=s.get("images", []), lane=a.lane, shot_id=f"{summ.get('scene','')}/{t['shot']}/hero")
            promoted.append({"shot": t["shot"], **res})
        print(json.dumps({"status": "ok", "promoted": promoted}, indent=2))
        return
    if a.cmd == "batch":
        shots = json.load(open(a.manifest))

        def one(s):
            try:
                res_target = CONFIG["draft_resolution"] if a.draft else s.get("resolution", "720p")
                res = roll(
                    s["prompt"], s["out"], lane=a.lane or s.get("lane"), task=s.get("task", "text_to_video"),
                    duration=s["duration"], aspect=s.get("aspect", "9:16"), resolution=res_target,
                    images=s.get("images", []), audio=s.get("audio"), video=s.get("video"), shot_id=s.get("id", ""), dry_run=a.dry_run,
                )
                return {"id": s.get("id"), "status": "ok", **res}
            except RollError as e:
                return {"id": s.get("id"), "status": e.kind, "message": str(e), "detail": e.detail[:300]}

        with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
            results = list(ex.map(one, shots))
        for r_ in results:
            print(json.dumps(r_, ensure_ascii=False))
        sys.exit(0 if all(r_["status"] == "ok" for r_ in results) else 2)


if __name__ == "__main__":
    main()
