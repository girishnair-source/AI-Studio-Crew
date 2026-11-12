#!/usr/bin/env python3
"""retake_governor.py — bounded retake loop with structured escalation. The ONLY sanctioned way to roll a scene.

    retake_governor.py run --manifest shots.json --scene EP01_SC04 [--max-auto-retakes 2] [--max-rolls 12] [--parallel 6]

For each shot: roll take 1 → QC (dailies_qc speech + profile) → if flags, apply the deterministic fix for the
reason code and roll again, up to MAX_AUTO_RETAKES (hard cap 2, policy). If still failing: STOP that shot, write
production/dailies/<scene>/escalations/<shot>.json (Escalation/1) and print the one-line question. Never loops further.
Also enforces a per-scene roll budget (max_rolls) and emits a SceneSummary/1 + telemetry spans.

Reason codes → auto-fix (applied to the prompt/params, logged):
  speech-clipped-at-end   → retake 1: append "finish speaking by {dur-1.5}s; hold on the face after"; retake 2: drop speech rate 10% + trim last clause hint
  monotone-read           → retake 1: strengthen intention ("perform, do not read; vary pitch and pace; one quiet sentence, one punched word, one hold")
  audio-peaks-hot         → retake 1: "softer voice, no shouting into the mic"
  safety                  → NO auto retake: escalate immediately with the stunt-safety suggestion
  capacity/timeout        → not a retake (already retried inside camera_roll); escalate if still failing
Anything else            → escalate after the cap.
"""
import argparse, json, os, re, sys, time, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "camera-roll", "scripts")); sys.path.insert(0, os.path.join(HERE, "..", "..", "dailies-qc", "scripts")); sys.path.insert(0, HERE)
from camera_roll import roll, RollError, last_frame, CONFIG as CR_CONFIG  # noqa: E402
CONFIG_CAP = CR_CONFIG["max_clip_seconds"]
from dailies_qc import full_qc  # noqa: E402
import telemetry  # noqa: E402

POLICY_MAX_AUTO_RETAKES = 2  # hard ceiling; CallSheet may lower, never raise

def auto_fix(prompt, reason, attempt, dur, cap=None):
    """Returns (new_prompt, new_duration_s, note). Clipped speech is first fixed by GIVING THE SHOT MORE TIME (the script
    decides length, not a constant); only at the cap do we ask for a tighter read."""
    cap = cap or CONFIG_CAP
    if reason == "speech-clipped-at-end":
        if dur + 2 <= cap: return prompt, dur + 2, f"duration {dur}s → {dur+2}s (speech needs room)"
        if attempt == 1: return prompt + f"\nTiming: all speech must finish by {dur-1.5:.1f} seconds; hold on the listener's face after.", dur, "finish-early hint (at cap)"
        return prompt + f"\nTiming: speak about 10 percent slower but finish by {dur-2.0:.1f} seconds; the final clause may be shortened by one or two words.", dur, "slower + finish-early (at cap)"
    if reason == "monotone-read":
        return prompt + "\nPerformance: this is a performance, not a read. Vary pitch and pace sentence to sentence: one quiet sentence, one punched word, one held pause. Speak to one person.", dur, "performance push"
    if reason == "audio-peaks-hot":
        return prompt + "\nAudio: softer, closer voice; no shouting; peaks well below clipping.", dur, "softer voice"
    if reason == "speech-starts-at-zero":
        return (prompt + "\nTiming: half a second of silence before the first word.", dur + 1 if dur + 1 <= cap else dur, "head handle")
    if reason == "dialogue-mismatch":
        return prompt + "\nDialogue clarity: articulate every word cleanly and verbatim as scripted; no ad-libbing, no dropped words.", dur, "verbatim dialogue emphasis"
    if reason == "hallucinated-speech":
        return prompt + "\nAudio: silent performance, no spoken words or background chatter.", dur, "suppress hallucinated speech"
    if reason in ("face-drift", "continuity-drift"):
        return prompt + "\nContinuity: match the primary reference image's exact face, hair, wardrobe, and lighting across every frame.", dur, "reinforce reference lock"
    if reason == "unprompted-captions":
        return prompt + "\nVisual: clean frame with NO burned-in captions, NO subtitles, and NO on-screen text.", dur, "suppress unprompted captions"
    if reason in ("visual-artifacts", "action-mismatch"):
        return prompt + "\nStaging: keep camera motion smooth and simple; execute one clear physical beat with natural anatomy.", dur, "simplify staging"
    if reason in ("frozen-video", "black-frames"):
        return prompt + "\nMotion: continuous subtle natural movement and steady lighting from the first frame to the last.", dur, "ensure continuous motion"
    return None, dur, None

def qc_take(path, profile, expected_text="", refs=(), action="", no_llm=False):
    return full_qc(path, profile=profile, expected_text=expected_text, refs=refs, action=action, no_llm=no_llm)

def escalate(scene_dir, scene, shot, takes, reason, evidence, parent):
    opts = {
        "speech-clipped-at-end": ([("A", "Split the line across two chained shots", "+1 roll, keeps every word"), ("B", "Accept the best take and trim the tail", "loses the last word"), ("C", "Cut the last clause from the script", "script change")], "A"),
        "monotone-read": ([("A", "Have the DOP re-direct the line with stronger intention and fewer words", "+1 roll"), ("B", "Accept the best take", "flat read stays")], "A"),
        "safety": ([("A", "Use Stunt & Safety's restaging of this beat", "+1 roll, beat preserved"), ("B", "Drop this shot from the scene", "no roll")], "A"),
        "capacity": ([("A", "Wait and retry in 10 minutes", "no cost"), ("B", "Roll on the fallback lane at lower resolution", "quality trade")], "A"),
        "dialogue-mismatch": ([("A", "Simplify or split the line with Voice Director", "+1 roll, clean lip-sync"), ("B", "Accept the best take and fix in captions/ADR", "minor wording drift")], "A"),
        "face-drift": ([("A", "Refresh/lock front-facing reference via Casting and re-roll", "+1 roll, locks identity"), ("B", "Accept the best take", "visible drift stays")], "A"),
        "continuity-drift": ([("A", "Re-roll anchored on previous shot's last frame", "+1 roll"), ("B", "Accept the best take and match in Colorist grade", "props/wardrobe may differ")], "A"),
        "visual-artifacts": ([("A", "Have DOP simplify camera motion and action beat", "+1 roll"), ("B", "Accept the best take", "artifact remains")], "A"),
    }.get(reason, ([("A", "Retake once more with a human note", "+1 roll"), ("B", "Accept the best take", "")], "B"))
    esc = {"schema": "Escalation/1", "scene": scene, "shot": shot, "takes_tried": takes, "auto_retakes_used": max(0, takes - 1), "reason_code": reason,
           "reason": f"{reason} persisted after {takes} take(s)", "at": time.strftime("%F %T"), "evidence": evidence[-4:],
           "options": [{"key": k, "label": l, "effect": e} for k, l, e in opts[0]], "recommended": opts[1],
           "question": f"We tried {max(0, takes-1)} retake(s) on {shot}; {reason.replace('-', ' ')}. Which option?", "resolved": None}
    d = os.path.join(scene_dir, "escalations"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{shot}.json"); json.dump(esc, open(p, "w"), indent=2)
    telemetry._write({"event": "escalation", "trace_id": parent["trace_id"], "span_id": parent["span_id"], "name": "escalate", "ts_ns": time.time_ns(), "attributes": {"scene": scene, "shot": shot, "reason": reason}})
    return p, esc

def run_shot(s, scene, scene_dir, max_auto, budget, parent, no_llm_qc=False):
    shot = s["id"]; dur = int(round(float(str(s["duration"]).rstrip("s")))); profile = s.get("profile", "dialogue")
    prompt = s["prompt"]; images = list(s.get("images", [])); evidence = []; takes = 0; best = None
    exp_dlg = s.get("dialogue") or ""
    if isinstance(exp_dlg, list):
        exp_dlg = " ".join(x.get("line", "") for x in exp_dlg)
    action = s.get("action", "")
    with telemetry.span("shot", parent, agent="camera", scene=scene, shot=shot) as sp:
        while True:
            if budget["rolls"] >= budget["max_rolls"]:
                p, esc = escalate(scene_dir, scene, shot, takes, "roll-budget-exhausted", evidence, sp); return {"shot": shot, "status": "escalate", "escalation": p, "best": best}
            takes += 1; budget["rolls"] += 1
            out = os.path.join(scene_dir, f"{shot}_take{takes}.mp4")
            try:
                with telemetry.span("camera.roll", sp, agent="camera", scene=scene, shot=shot, take=takes) as rs:
                    res = roll(prompt, out, task=s.get("task", "text_to_video"), duration=f"{dur}s", aspect=s.get("aspect", "9:16"), resolution=s.get("resolution", "720p"), images=images, shot_id=f"{scene}/{shot}/t{takes}")
                    telemetry.record_tokens(rs, gen_tokens=res.get("gen_tokens", 0), llm_in=res.get("llm_in", 0), llm_out=res.get("llm_out", 0))
            except RollError as e:
                evidence.append(f"take{takes}: {e.kind}: {str(e)[:120]}")
                reason = "safety" if e.kind == "safety" else ("capacity" if e.kind in ("capacity", "timeout") else e.kind)
                if reason in ("safety", "capacity", "auth", "access", "request") or takes - 1 >= max_auto:
                    p, esc = escalate(scene_dir, scene, shot, takes, reason, evidence, sp); return {"shot": shot, "status": "escalate", "escalation": p, "best": best}
                continue
            with telemetry.span("qc", sp, agent="dailies-qc", scene=scene, shot=shot, take=takes):
                q = qc_take(out, profile, expected_text=exp_dlg, refs=images, action=action, no_llm=no_llm_qc)
            try: last_frame(out, out.replace(".mp4", "_last.png"))
            except Exception: pass
            flags = [f for f in q.get("flags", []) if f != "no-speech" or s.get("dialogue")]
            evidence.append(f"take{takes}: flags={flags} margin={q.get('margin')} f0={q.get('f0_std_semitones')}")
            cand = {"take": out, "qc": q, "n": takes}
            if best is None or len(flags) < len(best["qc"].get("flags", [])): best = cand
            if not flags:
                return {"shot": shot, "status": "ok", "take": out, "takes": takes, "qc": q}
            if takes - 1 >= max_auto:
                p, esc = escalate(scene_dir, scene, shot, takes, flags[0], evidence, sp); return {"shot": shot, "status": "escalate", "escalation": p, "best": best, "takes": takes}
            new_prompt, new_dur, fix = auto_fix(prompt, flags[0], takes, dur)
            if not new_prompt:
                p, esc = escalate(scene_dir, scene, shot, takes, flags[0], evidence, sp); return {"shot": shot, "status": "escalate", "escalation": p, "best": best, "takes": takes}
            prompt, dur = new_prompt, new_dur; evidence.append(f"auto-fix {takes}: {fix}")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--manifest", required=True); r.add_argument("--scene", required=True); r.add_argument("--max-auto-retakes", type=int, default=POLICY_MAX_AUTO_RETAKES)
    r.add_argument("--max-rolls", type=int, default=12); r.add_argument("--parallel", type=int, default=6); r.add_argument("--production", default=os.environ.get("AGY_PRODUCTION_DIR", "production")); r.add_argument("--no-llm-qc", action="store_true")
    a = ap.parse_args()
    max_auto = min(a.max_auto_retakes, POLICY_MAX_AUTO_RETAKES)
    shots = json.load(open(a.manifest)); scene_dir = os.path.join(a.production, "dailies", a.scene); os.makedirs(scene_dir, exist_ok=True)
    budget = {"rolls": 0, "max_rolls": a.max_rolls}
    parent = telemetry.start("scene", telemetry.parent_from_env(), agent="first-ad", scene=a.scene)
    # chained shots run after their parent; independents in parallel
    done, results, pending = {}, [], list(shots)
    while pending:
        ready = [s for s in pending if not s.get("chain_from") or s["chain_from"] in done]
        if not ready: break
        with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
            for s, res in zip(ready, ex.map(lambda s: run_shot(s, a.scene, scene_dir, max_auto, budget, parent, no_llm_qc=a.no_llm_qc), ready)):
                done[s["id"]] = res; results.append(res); pending.remove(s)
    for s in pending:  # parents escalated → children blocked
        results.append({"shot": s["id"], "status": "blocked", "reason": f"chain parent {s['chain_from']} not locked"})
    locked = [{"shot": r["shot"], "take": r["take"], "trim_to": r["qc"].get("trim_to")} for r in results if r["status"] == "ok"]
    retakes = sum(max(0, r.get("takes", 1) - 1) for r in results)
    causes = {}
    for r in results:
        if r["status"] == "escalate": causes[json.load(open(r["escalation"]))["reason_code"]] = causes.get(json.load(open(r["escalation"]))["reason_code"], 0) + 1
    summary = {"schema": "SceneSummary/1", "scene": a.scene, "locked_at": time.strftime("%F %T"), "locked_takes": locked, "rolls": budget["rolls"], "retakes": retakes,
               "retake_causes": causes, "escalations": [r["escalation"] for r in results if r["status"] == "escalate"], "usable_seconds": sum(r["qc"].get("trim_to") or 0 for r in results if r["status"] == "ok"),
               "one_line": f"{len(locked)}/{len(shots)} shots locked, {budget['rolls']} rolls, {len(causes)} escalation type(s)"}
    json.dump(summary, open(os.path.join(scene_dir, "scene_summary.json"), "w"), indent=2)
    telemetry.end(parent, "ok" if not summary["escalations"] else "partial", rolls=budget["rolls"], locked=len(locked), escalations=len(summary["escalations"]))
    # chat-facing output: URIs + one-liners only
    print(json.dumps({"scene": a.scene, "summary": os.path.join(scene_dir, "scene_summary.json"), "one_line": summary["one_line"],
                      "locked": [f"{l['shot']} → {l['take']}" for l in locked],
                      "escalations": [json.load(open(e))["question"] + "  (" + e + ")" for e in summary["escalations"]]}, indent=2, ensure_ascii=False))
    sys.exit(0 if not summary["escalations"] else 3)

if __name__ == "__main__":
    main()
