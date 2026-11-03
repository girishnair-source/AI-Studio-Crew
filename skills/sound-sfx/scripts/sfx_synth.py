#!/usr/bin/env python3
"""sfx_synth.py — synthesized SFX presets (no samples, no music). 48 kHz mono WAV (+ optional MP3).

  sfx_synth.py list
  sfx_synth.py make --preset whoosh_shimmer --out production/sfx/whoosh1.wav [--dur 3] [--intensity 1.0] [--mp3]
  sfx_synth.py bank --out-dir production/sfx/bank            # every preset once
  sfx_synth.py stem --cues cues.json --len 131.3 --out production/sfx/EP01/sfx_stem.wav
      cues.json = [{"t": 10.6, "preset": "title_bang", "gain": 1.0}, ...]

Presets: whoosh_shimmer, sub_impact, air_thud, title_bang, title_bang_climax, glitch_hit, riser, room_tone, phone_buzz, dial_tone, keystroke
"""
import argparse, json, os, subprocess, wave
import numpy as np

SR = 48000

def _t(dur): return np.linspace(0, dur, int(SR * dur), endpoint=False)
def _norm(x, peak=0.95): m = np.max(np.abs(x)); return x / m * peak if m > 0 else x
def _brown(n):
    b = np.cumsum(np.random.normal(0, 1, n)) / np.sqrt(SR); b -= b.mean(); return b / (np.max(np.abs(b)) + 1e-9)
def _reverb(sig, delays=(47, 83, 137, 211, 331, 487), decays=(.65, .55, .48, .40, .32, .25), wet=.45):
    out = sig.copy()
    for d, g in zip(delays, decays):
        n = int(d * SR / 1000)
        if n < len(sig):
            dl = np.zeros_like(sig); dl[n:] = sig[:-n] * g
            if 2 * n < len(sig): dl[2*n:] += sig[:-2*n] * g * g * .7
            out += wet * dl
    return out
def _sweep_sine(freq_arr): return np.sin(2 * np.pi * np.cumsum(freq_arr) / SR)

def whoosh_shimmer(dur=3.0, k=1.0):
    t = _t(dur); n = len(t); tp = .55
    env = np.exp(-((t - tp) / .28) ** 2)
    airy = np.random.normal(0, 1, n) * env * (.6 + .4 * _sweep_sine(300 + 2400 * np.exp(-((t - tp) / .35) ** 2)))
    sh = np.zeros(n)
    for i, f in enumerate([1740, 2380, 3120, 4450, 5800, 7200, 8900]):
        vib = 1 + .015 * np.sin(2 * np.pi * 6.2 * t + i)
        e = np.where(t >= .5, np.exp(-(t - .5) * (1.2 + .3 * i)), np.exp(-((t - .5) / .12) ** 2))
        sh += np.sin(2 * np.pi * f * vib * t) * e / (i + 1) ** .6
    siz = np.random.normal(0, 1, n) * np.where(t >= .5, np.exp(-(t - .5) * 6), 0)
    return _norm(np.tanh(_reverb(.5 * airy + .45 * sh + .2 * siz) * 1.5 * k))

def sub_impact(dur=3.0, k=1.0):
    t = _t(dur); n = len(t)
    punch = _sweep_sine(36 + 110 * np.exp(-t * 28)) * np.exp(-t * 7)
    crack = np.random.normal(0, 1, n) * np.exp(-t * 45)
    sub = np.sin(2 * np.pi * 35 * t) * np.exp(-t * 1.2) + .4 * np.sin(2 * np.pi * 70 * t) * np.exp(-t * 2)
    rum = _brown(n) * (.6 + .4 * np.sin(2 * np.pi * 2.2 * t)) * np.exp(-t * .95)
    return _norm(np.tanh((.65 * punch + .3 * crack + .6 * sub + .45 * rum) * 1.8 * k), .96)

def air_thud(dur=2.0, k=1.0):
    t = _t(dur); n = len(t); th = .22
    env = np.where(t <= th, np.exp((t - th) * 22), np.exp(-(t - th) * 35))
    air = np.random.normal(0, 1, n) * env * (.5 + .5 * _sweep_sine(250 + 3200 * np.clip(t / th, 0, 1) ** 2))
    tf = np.maximum(0, t - th); m = (t >= th).astype(float)
    thud = _sweep_sine(52 + 130 * np.exp(-tf * 35)) * np.exp(-tf * 12) * m
    slap = np.random.normal(0, 1, n) * np.exp(-tf * 55) * m
    body = np.sin(2 * np.pi * 55 * tf) * np.exp(-tf * 5.5) * m
    return _norm(np.tanh((.55 * air + .65 * thud + .35 * slap + .45 * body) * 1.7 * k), .96)

def title_bang(dur=1.8, k=1.0, climax=False, crunch=False):
    t = _t(dur); n = len(t)
    f0 = 650 if crunch else 550
    punch = _sweep_sine(f0 * np.exp(-t * (24 if climax else 32)) + (38 if climax else 46)) * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * (38 if climax else 44) * t) * np.exp(-t * (1.2 if climax else 2))
    noise = np.random.normal(0, 1, n) * np.exp(-t * 45)
    if crunch: noise += np.sin(2 * np.pi * 320 * t) * np.random.uniform(-.5, .5, n) * np.exp(-t * 15)
    ring = np.sin(2 * np.pi * 780 * t) * np.exp(-t * 10) * .28 + np.sin(2 * np.pi * 1350 * t) * np.exp(-t * 16) * .18
    extra = (np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 22) * .35 + np.sin(2 * np.pi * 28 * t) * np.exp(-t * .8) * .45) if climax else 0
    return _norm(np.tanh((.55 * punch + (.75 if climax else .55) * sub + .45 * noise + ring + extra) * 1.8 * k))

def title_bang_climax(dur=2.2, k=1.3): return title_bang(dur, k, climax=True)

def glitch_hit(dur=1.2, k=1.0):
    t = _t(dur); n = len(t)
    bits = np.round(np.random.normal(0, 1, n) * 4) / 4 * np.exp(-t * 18)
    stut = np.sin(2 * np.pi * 180 * t) * (np.sin(2 * np.pi * 37 * t) > 0) * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * 42 * t) * np.exp(-t * 3)
    return _norm(np.tanh((.5 * bits + .5 * stut + .7 * sub) * 1.6 * k))

def riser(dur=4.0, k=1.0):
    t = _t(dur); n = len(t)
    nz = np.random.normal(0, 1, n) * (t / dur) ** 2.2
    tone = _sweep_sine(120 * 2 ** (t / dur * 3)) * (t / dur) ** 3 * .5
    return _norm(np.tanh((nz + tone) * 1.3 * k))

def room_tone(dur=10.0, k=1.0):
    n = int(SR * dur); b = _brown(n) * .12
    hum = np.sin(2 * np.pi * 50 * _t(dur)) * .01 + np.sin(2 * np.pi * 100 * _t(dur)) * .004
    return _norm(b + hum, .25 * k)

def phone_buzz(dur=2.4, k=1.0):
    t = _t(dur); gate = ((t % .8) < .45).astype(float)
    return _norm(np.sin(2 * np.pi * 160 * t) * (np.sin(2 * np.pi * 28 * t) > 0) * gate * .8, .7 * k)

def dial_tone(dur=2.0, k=1.0):
    t = _t(dur); return _norm((np.sin(2 * np.pi * 350 * t) + np.sin(2 * np.pi * 440 * t)) * .5, .5 * k)

def keystroke(dur=.12, k=1.0):
    t = _t(dur); n = len(t)
    return _norm(np.random.normal(0, 1, n) * np.exp(-t * 90) * .7 + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120) * .3, .8 * k)

PRESETS = {f.__name__: f for f in (whoosh_shimmer, sub_impact, air_thud, title_bang, title_bang_climax, glitch_hit, riser, room_tone, phone_buzz, dial_tone, keystroke)}

def save(sig, out, mp3=False):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
    if mp3:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out, "-c:a", "libmp3lame", "-b:a", "320k", os.path.splitext(out)[0] + ".mp3"], check=True)
    return out

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    m = sub.add_parser("make"); m.add_argument("--preset", required=True, choices=PRESETS); m.add_argument("--out", required=True); m.add_argument("--dur", type=float); m.add_argument("--intensity", type=float, default=1.0); m.add_argument("--mp3", action="store_true")
    b = sub.add_parser("bank"); b.add_argument("--out-dir", required=True); b.add_argument("--mp3", action="store_true")
    s = sub.add_parser("stem"); s.add_argument("--cues", required=True); s.add_argument("--len", type=float, required=True); s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "list":
        for k in PRESETS: print(k)
    elif a.cmd == "make":
        kw = {"k": a.intensity}; 
        if a.dur: kw["dur"] = a.dur
        print(save(PRESETS[a.preset](**kw), a.out, a.mp3))
    elif a.cmd == "bank":
        for k, f in PRESETS.items(): print(save(f(), os.path.join(a.out_dir, f"{k}.wav"), a.mp3))
    elif a.cmd == "stem":
        total = np.zeros(int(SR * a.len), dtype=np.float32)
        for c in json.load(open(a.cues)):
            sig = PRESETS[c["preset"]](**({"k": c.get("gain", 1.0)} | ({"dur": c["dur"]} if "dur" in c else {})))
            i = int(c["t"] * SR); j = min(len(total), i + len(sig)); total[i:j] += sig[: j - i]
        print(save(_norm(total, .9), a.out))

if __name__ == "__main__":
    main()
