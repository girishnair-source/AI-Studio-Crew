#!/usr/bin/env python3
"""telemetry.py — trajectory tracing + token-to-usable-second accounting for the crew.

OpenTelemetry-compatible span model (trace_id / span_id / parent_span_id, start/end ns, attributes, status) written
as JSON lines to production/reports/trace.jsonl. If the `opentelemetry` SDK is installed and OTEL_EXPORTER_OTLP_ENDPOINT
is set, spans are ALSO exported via OTLP; otherwise the JSONL is the source of truth (no dependency required).

Library use (inside tools):
    from telemetry import span, record_tokens
    with span("camera.roll", scene="EP01_SC04", shot="4A", agent="camera") as sp:
        ...; record_tokens(sp, llm_in=1200, llm_out=300, gen_tokens=45120)

CLI:
    telemetry.py start  --agent first-ad --name scene --scene EP01_SC04        -> prints span JSON (export AGY_SPAN=...)
    telemetry.py end    --span '<json>' [--status ok|error] [--attr k=v ...]
    telemetry.py tokens --span '<json>' --llm-in N --llm-out N [--gen N]
    telemetry.py report --production production [--episode EP01]              -> tokens per usable second, per department
Propagation between agents: pass the parent span JSON (or just trace_id+span_id) in the CrewReport/CallSheet 'trace' field.
"""
import argparse, json, os, subprocess, time, uuid, contextlib, sys

PROD = os.environ.get("AGY_PRODUCTION_DIR", "production")
TRACE_FILE = os.path.join(PROD, "reports", "trace.jsonl")

def _write(rec):
    os.makedirs(os.path.dirname(TRACE_FILE), exist_ok=True)
    with open(TRACE_FILE, "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _otlp(rec)

_otel = None
def _otlp(rec):
    """Best-effort OTLP export if SDK + endpoint present."""
    global _otel
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or rec.get("event") != "end": return
    try:
        if _otel is None:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            tp = TracerProvider(); tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter())); trace.set_tracer_provider(tp)
            _otel = trace.get_tracer("ai-studio-crew")
        with _otel.start_as_current_span(rec["name"], start_time=rec["start_ns"]) as s:
            for k, v in rec.get("attributes", {}).items(): s.set_attribute(k, v)
    except Exception:
        _otel = False

def start(name, parent=None, **attrs):
    sp = {"event": "start", "trace_id": (parent or {}).get("trace_id") or uuid.uuid4().hex, "span_id": uuid.uuid4().hex[:16],
          "parent_span_id": (parent or {}).get("span_id"), "name": name, "start_ns": time.time_ns(), "attributes": {k: v for k, v in attrs.items() if v is not None}}
    _write(sp); return sp

def end(sp, status="ok", **attrs):
    rec = dict(sp); rec.update(event="end", end_ns=time.time_ns(), status=status)
    rec["attributes"] = {**sp.get("attributes", {}), **{k: v for k, v in attrs.items() if v is not None}}
    rec["duration_ms"] = round((rec["end_ns"] - rec["start_ns"]) / 1e6, 1); _write(rec); return rec

def record_tokens(sp, llm_in=0, llm_out=0, gen_tokens=0, **extra):
    _write({"event": "tokens", "trace_id": sp["trace_id"], "span_id": sp["span_id"], "name": sp["name"], "ts_ns": time.time_ns(),
            "llm_in": int(llm_in), "llm_out": int(llm_out), "gen_tokens": int(gen_tokens), "attributes": {**sp.get("attributes", {}), **extra}})

@contextlib.contextmanager
def span(name, parent=None, **attrs):
    sp = start(name, parent, **attrs)
    try:
        yield sp; end(sp, "ok")
    except Exception as e:
        end(sp, "error", error=str(e)[:200]); raise

def parent_from_env():
    try: return json.loads(os.environ.get("AGY_SPAN", "") or "null")
    except Exception: return None

# ───────── report ─────────
def _dur(path):
    try: return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode())
    except Exception: return 0.0

def report(production, episode=None):
    tf = os.path.join(production, "reports", "trace.jsonl")
    recs = [json.loads(l) for l in open(tf)] if os.path.exists(tf) else []
    if episode: recs = [r for r in recs if (r.get("attributes", {}).get("scene") or "").startswith(episode) or r.get("attributes", {}).get("episode") == episode]
    by_dept = {}
    for r in recs:
        dept = r.get("attributes", {}).get("agent") or r["name"].split(".")[0]
        d = by_dept.setdefault(dept, {"spans": 0, "ms": 0.0, "llm_in": 0, "llm_out": 0, "gen_tokens": 0, "errors": 0})
        if r["event"] == "end": d["spans"] += 1; d["ms"] += r.get("duration_ms", 0); d["errors"] += (r.get("status") == "error")
        if r["event"] == "tokens": d["llm_in"] += r["llm_in"]; d["llm_out"] += r["llm_out"]; d["gen_tokens"] += r["gen_tokens"]
    # usable seconds = duration of masters (fallback: locked cuts)
    masters = [os.path.join(production, "masters", f) for f in os.listdir(os.path.join(production, "masters"))] if os.path.isdir(os.path.join(production, "masters")) else []
    masters = [m for m in masters if m.endswith(".mp4") and (not episode or episode in os.path.basename(m))]
    usable = sum(_dur(m) for m in masters)
    if not usable:
        cuts = [os.path.join(production, "cuts", f) for f in os.listdir(os.path.join(production, "cuts"))] if os.path.isdir(os.path.join(production, "cuts")) else []
        cuts = [c for c in cuts if c.endswith("_mix.mp4") and (not episode or episode in os.path.basename(c))]
        usable = sum(_dur(c) for c in cuts)
    # rolls from ledger
    ledger = os.path.join(production, "reports", "ledger.csv"); rolls = ok = 0; gen_seconds = 0.0
    if os.path.exists(ledger):
        import csv
        for row in csv.DictReader(open(ledger)):
            if episode and not (row.get("id") or "").startswith(episode): continue
            rolls += 1; ok += (row.get("status") == "ok")
            try: gen_seconds += float((row.get("duration") or "0s").rstrip("s")) if row.get("status") == "ok" else 0
            except ValueError: pass
    tot_llm = sum(d["llm_in"] + d["llm_out"] for d in by_dept.values()); tot_gen = sum(d["gen_tokens"] for d in by_dept.values())
    out = {"episode": episode, "usable_seconds": round(usable, 1), "generated_seconds": round(gen_seconds, 1),
           "yield": round(usable / gen_seconds, 2) if gen_seconds else None, "rolls": rolls, "rolls_ok": ok,
           "llm_tokens": tot_llm, "gen_tokens": tot_gen,
           "tokens_per_usable_second": round((tot_llm + tot_gen) / usable, 1) if usable else None,
           "llm_tokens_per_usable_second": round(tot_llm / usable, 1) if usable else None,
           "by_department": {k: {**v, "ms": round(v["ms"])} for k, v in sorted(by_dept.items(), key=lambda x: -(x[1]["llm_in"] + x[1]["llm_out"] + x[1]["gen_tokens"]))}}
    return out

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start"); s.add_argument("--name", required=True); s.add_argument("--agent"); s.add_argument("--scene"); s.add_argument("--shot"); s.add_argument("--parent")
    e = sub.add_parser("end"); e.add_argument("--span", required=True); e.add_argument("--status", default="ok"); e.add_argument("--attr", action="append", default=[])
    t = sub.add_parser("tokens"); t.add_argument("--span", required=True); t.add_argument("--llm-in", type=int, default=0); t.add_argument("--llm-out", type=int, default=0); t.add_argument("--gen", type=int, default=0)
    r = sub.add_parser("report"); r.add_argument("--production", default=PROD); r.add_argument("--episode"); r.add_argument("--md", action="store_true")
    a = ap.parse_args()
    if a.cmd == "start": print(json.dumps(start(a.name, json.loads(a.parent) if a.parent else parent_from_env(), agent=a.agent, scene=a.scene, shot=a.shot)))
    elif a.cmd == "end": print(json.dumps(end(json.loads(a.span), a.status, **dict(x.split("=", 1) for x in a.attr))))
    elif a.cmd == "tokens": record_tokens(json.loads(a.span), a.llm_in, a.llm_out, a.gen); print("ok")
    else:
        rep = report(a.production, a.episode)
        if a.md:
            print(f"# Efficiency report {rep['episode'] or ''}\n\n| metric | value |\n|---|---|\n| usable seconds (masters) | {rep['usable_seconds']} |\n| generated seconds (ok rolls) | {rep['generated_seconds']} |\n| yield (usable / generated) | {rep['yield']} |\n| rolls (ok/total) | {rep['rolls_ok']}/{rep['rolls']} |\n| LLM tokens | {rep['llm_tokens']} |\n| generative tokens | {rep['gen_tokens']} |\n| **tokens per usable second** | **{rep['tokens_per_usable_second']}** |\n\n| department | spans | ms | llm in | llm out | gen tokens | errors |\n|---|---|---|---|---|---|---|")
            for k, v in rep["by_department"].items(): print(f"| {k} | {v['spans']} | {v['ms']} | {v['llm_in']} | {v['llm_out']} | {v['gen_tokens']} | {v['errors']} |")
        else: print(json.dumps(rep, indent=2))

if __name__ == "__main__":
    main()
