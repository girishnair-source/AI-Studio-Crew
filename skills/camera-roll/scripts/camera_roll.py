#!/usr/bin/env python3
"""camera_roll.py — roll video clips through the Vertex Interactions API.

Single config block (CONFIG) for model IDs / hosts / projects — edit here only.
Auth providers (first that works): $AGY_ACCESS_TOKEN, stubby CorpLogin (gLinux), gcloud.
Features: text/image/reference-to-video, parallel shots via a manifest, retry with
backoff + lane fallback on capacity errors, typed safety-block reporting, last-frame
extraction for chaining, ledger append for the Line Producer.

Usage (single shot):
  camera_roll.py roll --prompt "..." --duration 7s   # duration comes from duration.py, never a fixed number --aspect 9:16 [--image ref.png ...] --out take1.mp4
Usage (manifest, parallel):
  camera_roll.py batch --manifest shots.json --parallel 6
  manifest = [{"id":"4A","prompt":"...","duration":"15s","aspect":"9:16","images":["..."],"out":"..."}]
Other:
  camera_roll.py last-frame --video take1.mp4 --out take1_last.png
  camera_roll.py doctor
"""
import argparse, base64, concurrent.futures as cf, csv, getpass, json, mimetypes, os, shutil, subprocess, sys, time, urllib.error, urllib.request

# ───────────────────────────── CONFIG (the only place model/host names live) ─────────────────────────────
CONFIG = {
    "lanes": {
        # name: {model, host, project}. Lane names are stable; model ids change here only.
        "omni-1.2": {"model": "gemini-omni-1.2-flash", "host": "aiplatform.googleapis.com", "project": os.environ.get("AGY_PROJECT", "genai-on-vertex-playground")},
        "omni-1.1": {"model": "gemini-omni-1.1-flash-preview", "host": "aiplatform.googleapis.com", "project": os.environ.get("AGY_PROJECT", "genai-on-vertex-playground")},
    },
    "default_lane": os.environ.get("AGY_LANE", "omni-1.2"),
    "fallback_lane": os.environ.get("AGY_FALLBACK_LANE", "omni-1.1"),
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
    CONFIG["lanes"]["preview"] = {"model": os.environ["AGY_PREVIEW_MODEL"], "host": os.environ.get("AGY_PREVIEW_HOST", "aiplatform.googleapis.com"), "project": os.environ.get("AGY_PREVIEW_PROJECT", CONFIG["lanes"]["omni-1.2"]["project"])}
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────

class RollError(Exception):
    def __init__(self, kind, message, detail=""):
        super().__init__(message); self.kind = kind; self.detail = detail

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
    if mt == "audio/x-wav": mt = "audio/wav"
    part = {"type": kind, "mime_type": mt}
    if path.startswith("gs://"):
        part["uri"] = path
    else:
        part["data"] = base64.b64encode(open(path, "rb").read()).decode()
    return part

def _http(method, url, token, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        if e.code == 401: raise RollError("auth", "401 UNAUTHENTICATED — token invalid/expired", txt[:400])
        if e.code == 403: raise RollError("access", "403 PERMISSION_DENIED — account lacks access to project/endpoint", txt[:400])
        if e.code == 429 or e.code >= 500: raise RollError("capacity", f"HTTP {e.code}", txt[:400])
        raise RollError("request", f"HTTP {e.code}", txt[:800])

def ledger(row):
    try:
        os.makedirs(os.path.dirname(CONFIG["ledger"]), exist_ok=True)
        new = not os.path.exists(CONFIG["ledger"])
        with open(CONFIG["ledger"], "a", newline="") as f:
            w = csv.writer(f)
            if new: w.writerow(["ts", "id", "lane", "model", "task", "duration", "resolution", "status", "seconds", "interaction_id", "note"])
            w.writerow(row)
    except Exception:
        pass

# ── core roll ────────────────────────────────────────────────────────────────────────────────────────────
def normalize_duration(duration):
    """Accept '7s', '7', 7, 7.4 -> clamp to [min,max] whole seconds, return 'Ns'."""
    try: v = float(str(duration).rstrip("s"))
    except ValueError: raise RollError("request", f"bad duration {duration!r}")
    v = int(round(v)); lo, hi = CONFIG["min_clip_seconds"], CONFIG["max_clip_seconds"]
    if v < lo or v > hi: raise RollError("request", f"duration {v}s outside model bounds {lo}-{hi}s; split or merge the shot (duration.py)")
    return f"{v}s"

def roll_once(lane_name, prompt, out, task="text_to_video", duration="8s", aspect="9:16", resolution="720p", images=(), audio=None, shot_id=""):
    lane = CONFIG["lanes"][lane_name]
    duration = normalize_duration(duration)
    if len(images) > CONFIG["max_reference_images"]: raise RollError("request", f"{len(images)} reference images > {CONFIG['max_reference_images']}")
    token = get_token()
    inputs = [{"type": "text", "text": prompt}] + [media_part(p, "image") for p in images]
    if audio: inputs.append(media_part(audio, "audio"))
    if task == "text_to_video" and images: task = "reference_to_video"
    rf = {"type": "video"}
    if task != "extend":
        rf.update(aspect_ratio=aspect, resolution=resolution, duration=duration)
    payload = {"model": lane["model"], "input": inputs,
               "generation_config": {"thinking_summaries": "auto", "video_config": {"task": task}},
               "response_format": rf, "background": True}
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
        msg = errs[0].get("message", "") ; code = errs[0].get("code", "")
        kind = "safety" if ("safety" in msg.lower() or "prohibited" in msg.lower() or "blocked" in str(code).lower() or "content_blocked" in str(code) or "prohibited_content" in str(code).lower()) else "failed"
        if kind != "safety" and not resp.get("usage"): kind = "capacity"  # empty usage = never ran
        ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, kind, round(time.time()-t0,1), iid, msg[:120]])
        raise RollError(kind, f"interaction {status}: {msg}", json.dumps(errs)[:600])
    out_containers = resp.get("outputs") or [s for s in resp.get("steps", []) if s.get("type") == "model_output"]
    for o in out_containers:
        for item in (o.get("content") or [o]):
            if item.get("type") == "video" and item.get("data"):
                os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
                open(out, "wb").write(base64.b64decode(item["data"]))
                ledger([time.strftime("%F %T"), shot_id, lane_name, lane["model"], task, duration, resolution, "ok", round(time.time()-t0,1), iid, ""])
                return {"out": out, "lane": lane_name, "model": lane["model"], "interaction_id": iid, "seconds": round(time.time()-t0, 1)}
    raise RollError("failed", "completed but no video in response", json.dumps(resp)[:600])

def roll(prompt, out, lane=None, **kw):
    """Roll with retries; capacity → backoff then fallback lane; auth → refresh once; safety → raise immediately."""
    lane = lane or CONFIG["default_lane"]
    attempt, lanes = 0, [lane]
    if CONFIG["fallback_lane"] and CONFIG["fallback_lane"] != lane: lanes.append(CONFIG["fallback_lane"])
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
                    get_token(force=True); continue
                if e.kind in ("capacity", "timeout", "failed"):
                    time.sleep(CONFIG["backoff_s"][min(i, len(CONFIG["backoff_s"]) - 1)]); continue
                if e.kind == "access":
                    break  # try next lane / project
    raise last

# ── utilities ────────────────────────────────────────────────────────────────────────────────────────────
def last_frame(video, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.08", "-i", video, "-frames:v", "1", "-update", "1", out], check=True)
    return out

def doctor():
    print("auth providers:")
    for name, fn in (("AGY_ACCESS_TOKEN", _token_env), ("stubby", _token_stubby), ("gcloud", _token_gcloud)):
        t = fn(); print(f"  {name:16s} {'ok' if t else '—'}")
    for ln, cfg in CONFIG["lanes"].items():
        url = f"https://{cfg['host']}/v1beta1/projects/{cfg['project']}/locations/global/interactions"
        try:
            _http("POST", url, get_token(), {})
            print(f"  lane {ln:8s} {cfg['model']:34s} reachable (400 expected)  ✓")
        except RollError as e:
            tag = {"request": "✓ reachable", "auth": "✗ 401 token", "access": "✗ 403 no access", "capacity": "~ overloaded"}.get(e.kind, e.kind)
            print(f"  lane {ln:8s} {cfg['model']:34s} {tag}")
    print(f"default lane: {CONFIG['default_lane']}  fallback: {CONFIG['fallback_lane']}  clip bounds: {CONFIG['min_clip_seconds']}-{CONFIG['max_clip_seconds']}s (per-shot, from script)  max refs: {CONFIG['max_reference_images']}")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("roll"); r.add_argument("--prompt", required=True); r.add_argument("--out", required=True)
    r.add_argument("--task", default="text_to_video"); r.add_argument("--duration", required=True, help="seconds, decided per shot by duration.py (e.g. 7s)"); r.add_argument("--aspect", default="9:16")
    r.add_argument("--resolution", default="720p"); r.add_argument("--image", action="append", default=[]); r.add_argument("--audio"); r.add_argument("--lane"); r.add_argument("--id", default="")
    b = sub.add_parser("batch"); b.add_argument("--manifest", required=True); b.add_argument("--parallel", type=int, default=6); b.add_argument("--lane")
    lf = sub.add_parser("last-frame"); lf.add_argument("--video", required=True); lf.add_argument("--out", required=True)
    sub.add_parser("doctor")
    a = ap.parse_args()
    if a.cmd == "doctor": return doctor()
    if a.cmd == "last-frame": print(last_frame(a.video, a.out)); return
    if a.cmd == "roll":
        try:
            res = roll(a.prompt, a.out, lane=a.lane, task=a.task, duration=a.duration, aspect=a.aspect, resolution=a.resolution, images=a.image, audio=a.audio, shot_id=a.id)
            print(json.dumps({"status": "ok", **res}))
        except RollError as e:
            print(json.dumps({"status": e.kind, "message": str(e), "detail": e.detail})); sys.exit(2)
        return
    if a.cmd == "batch":
        shots = json.load(open(a.manifest))
        def one(s):
            try:
                res = roll(s["prompt"], s["out"], lane=a.lane or s.get("lane"), task=s.get("task", "text_to_video"), duration=s["duration"],
                           aspect=s.get("aspect", "9:16"), resolution=s.get("resolution", "720p"), images=s.get("images", []), audio=s.get("audio"), shot_id=s.get("id", ""))
                return {"id": s.get("id"), "status": "ok", **res}
            except RollError as e:
                return {"id": s.get("id"), "status": e.kind, "message": str(e), "detail": e.detail[:300]}
        with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
            results = list(ex.map(one, shots))
        for r_ in results: print(json.dumps(r_, ensure_ascii=False))
        sys.exit(0 if all(r_["status"] == "ok" for r_ in results) else 2)

if __name__ == "__main__":
    main()
