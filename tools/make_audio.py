#!/usr/bin/env python3
"""Soundtrack for the Ubuntu Mac Kit video: lo-fi music + clicks, keys, pops, whooshes."""
import math, random, struct, sys, wave

SR = 44100
TOTAL = 58.0
N = int(SR * TOTAL)
music = [0.0] * N
sfx = [0.0] * N
rnd = random.Random(3)
cache = {}

def mix(buf, at, samples, gain=1.0):
    i0 = int(at * SR)
    for i, v in enumerate(samples):
        j = i0 + i
        if 0 <= j < N:
            buf[j] += v * gain

def env(i, n, att, rel):
    t = i / SR
    a = min(1.0, t / att) if att > 0 else 1.0
    r = min(1.0, (n - i) / (rel * SR)) if rel > 0 else 1.0
    return a * r

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

def pad(f, dur):
    key = ('pad', f, dur)
    if key in cache: return cache[key]
    n = int(dur * SR); out = []
    for i in range(n):
        t = i / SR
        v = (math.sin(2 * math.pi * f * t) + math.sin(2 * math.pi * f * 1.004 * t) * 0.8
             + math.sin(2 * math.pi * f * 0.996 * t) * 0.8 + math.sin(2 * math.pi * f * 2 * t) * 0.15)
        out.append(v * env(i, n, 0.9, 1.2) * (0.85 + 0.15 * math.sin(2 * math.pi * 0.3 * t)))
    cache[key] = out; return out

def pluck(f, dur=0.9):
    key = ('pluck', f)
    if key in cache: return cache[key]
    n = int(dur * SR); out = []
    for i in range(n):
        t = i / SR
        v = math.sin(2 * math.pi * f * t) * math.exp(-t * 5) + 0.35 * math.sin(4 * math.pi * f * t) * math.exp(-t * 9)
        out.append(v * min(1, t / 0.004))
    cache[key] = out; return out

def bass(f, dur=1.1):
    key = ('bass', f)
    if key in cache: return cache[key]
    n = int(dur * SR)
    out = [math.sin(2 * math.pi * f * i / SR) * env(i, n, 0.01, 0.3) * math.exp(-i / SR * 1.5) for i in range(n)]
    cache[key] = out; return out

def kick():
    if 'kick' in cache: return cache['kick']
    n = int(0.3 * SR); out = []; ph = 0
    for i in range(n):
        t = i / SR; f = 45 + 80 * math.exp(-t * 30); ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 12))
    cache['kick'] = out; return out

def noise_burst(dur, decay, hp=0.0, seed=0):
    r = random.Random(seed); n = int(dur * SR); out = []; prev = 0.0; lp = 0.0
    for i in range(n):
        x = r.uniform(-1, 1)
        y = x - prev * hp; prev = x          # crude high-pass
        out.append(y * math.exp(-i / SR * decay))
    return out

def hat(seed): return noise_burst(0.06, 70, hp=0.95, seed=seed)

def key_click(seed):
    out = noise_burst(0.03, 180, hp=0.6, seed=seed)
    f = 1800 + seed % 7 * 120
    return [v * 0.6 + 0.5 * math.sin(2 * math.pi * f * i / SR) * math.exp(-i / SR * 250) for i, v in enumerate(out)]

def enter_key():
    out = noise_burst(0.06, 90, hp=0.4, seed=99)
    return [v * 0.8 + 0.6 * math.sin(2 * math.pi * 900 * i / SR) * math.exp(-i / SR * 120) for i, v in enumerate(out)]

def mouse_click():
    a = noise_burst(0.012, 400, hp=0.8, seed=5)
    b = [math.sin(2 * math.pi * 3200 * i / SR) * math.exp(-i / SR * 500) for i in range(int(0.02 * SR))]
    out = [0.0] * int(0.09 * SR)
    for i, v in enumerate(a): out[i] += v
    for i, v in enumerate(b): out[i] += v * 0.7
    o2 = int(0.055 * SR)
    for i, v in enumerate(a): out[o2 + i] += v * 0.6
    return out

def pop(f0=520, f1=980):
    n = int(0.09 * SR); out = []; ph = 0
    for i in range(n):
        t = i / SR; f = f0 + (f1 - f0) * min(1, t / 0.05); ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 40) * min(1, t / 0.002))
    return out

def ding(f=1318.5):
    n = int(0.6 * SR)
    return [(math.sin(2 * math.pi * f * i / SR) + 0.4 * math.sin(2 * math.pi * f * 1.5 * i / SR))
            * math.exp(-i / SR * 7) * min(1, i / SR / 0.003) for i in range(n)]

def whoosh(dur, seed=1, rise=0.55, bright=0.25):
    r = random.Random(seed); n = int(dur * SR); out = []; lp = 0.0; lp2 = 0.0
    for i in range(n):
        p = i / n
        e = (p / rise) if p < rise else (1 - p) / (1 - rise)
        a = 0.02 + bright * e                # filter opens with the swell
        lp += (r.uniform(-1, 1) - lp) * a
        lp2 += (lp - lp2) * a
        out.append(lp2 * e ** 1.5 * 3)
    return out

def chime():
    out = [0.0] * int(1.6 * SR)
    for k, m in enumerate([72, 76, 79, 84]):
        mix_local = pluck(mtof(m), 1.2)
        o = int(k * 0.09 * SR)
        for i, v in enumerate(mix_local):
            if o + i < len(out): out[o + i] += v
    return out

# ---------------- music ----------------
BPM = 96; beat = 60 / BPM; bar = beat * 4
chords = [[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [43, 47, 50, 52]]  # Cmaj7 Am7 Fmaj7 G6
nbars = int(TOTAL / bar) + 1
for b in range(nbars):
    t0 = b * bar
    ch = chords[b % 4]
    for m in ch:
        mix(music, t0, pad(mtof(m + 12), bar + 1.2), 0.035)
    mix(music, t0, bass(mtof(ch[0] - 12)), 0.22)
    mix(music, t0 + beat * 2.5, bass(mtof(ch[0] - 12)), 0.14)
    if b >= 1:
        arp = [ch[0] + 24, ch[2] + 12, ch[1] + 24, ch[3] + 12, ch[2] + 24, ch[1] + 24, ch[3] + 12, ch[2] + 12]
        for k, m in enumerate(arp):
            mix(music, t0 + k * beat / 2, pluck(mtof(m)), 0.07 if k % 2 == 0 else 0.05)
    if 2 <= b < nbars - 1:
        mix(music, t0, kick(), 0.35); mix(music, t0 + beat * 2, kick(), 0.3)
        mix(music, t0 + beat * 2.75, kick(), 0.15)
        for k in range(4):
            mix(music, t0 + k * beat + beat / 2, hat(b * 4 + k), 0.06)
# fade music in/out
for i in range(N):
    t = i / SR
    music[i] *= min(1, t / 1.5) * min(1, (TOTAL - t) / 3.0)

# ---------------- sound effects (times match make_video.py scenes) ----------------
starts = [0, 5, 12.5, 20.5, 32, 39, 47.5, 53]
for s in starts[1:]:
    mix(sfx, s - 0.35, whoosh(0.8, seed=int(s * 10)), 0.35)

def type_fracs(text):
    """Same uneven keystroke schedule as make_video.py."""
    r = random.Random(len(text) * 7919)
    iv = []
    for i, ch in enumerate(text):
        d = r.uniform(0.55, 1.5)
        if i > 0 and text[i - 1] == ' ': d *= 1.9
        iv.append(d)
    tot = sum(iv); acc = 0; out = []
    for d in iv:
        acc += d; out.append(acc / tot)
    return out

def mech_stroke(r, body, n, gain, click):
    """One switch event: sharp click + damped keycap/plate resonances + short thud."""
    out = []; lp = 0.0; prev = 0.0
    f1, f2, f3 = body, body * r.uniform(2.6, 3.1), r.uniform(1800, 2600)
    for i in range(n):
        t = i / SR
        x = r.uniform(-1, 1); hp = x - prev * 0.95; prev = x
        lp += (x - lp) * 0.18
        v = click * hp * math.exp(-t * 900)                       # switch click transient
        v += 0.9 * math.sin(2 * math.pi * f1 * t) * math.exp(-t * 55)   # keycap body
        v += 0.35 * math.sin(2 * math.pi * f2 * t) * math.exp(-t * 90)  # plate ring
        v += 0.12 * math.sin(2 * math.pi * f3 * t) * math.exp(-t * 160)
        v += 0.8 * lp * math.exp(-t * 110)                          # bottom-out thud
        out.append(v * gain * min(1, t / 0.0005))
    return out

def mech_key(seed, kind='key'):
    """Mechanical keyboard press: down-stroke (click + thock) then lighter up-stroke."""
    r = random.Random(seed)
    body = {'key': r.uniform(300, 380), 'space': r.uniform(170, 200), 'enter': r.uniform(220, 250)}[kind]
    n = int(0.16 * SR)
    out = [0.0] * n
    down = mech_stroke(r, body, int(0.09 * SR), 1.0 if kind == 'key' else 1.25, 0.9)
    for i, v in enumerate(down): out[i] += v
    up_at = int(r.uniform(0.055, 0.08) * SR)
    up = mech_stroke(r, body * 1.35, int(0.06 * SR), 0.4, 0.5)
    for i, v in enumerate(up):
        if up_at + i < n: out[up_at + i] += v
    if kind != 'key':                                              # stabilizer rattle
        rt = int(0.012 * SR)
        for i in range(int(0.01 * SR)):
            if rt + i < n: out[rt + i] += r.uniform(-1, 1) * math.exp(-i / SR * 500) * 0.35
    return out

def typing(a, b, text, seed):
    for i, f in enumerate(type_fracs(text)):
        mix(sfx, a + (b - a) * f + random.Random(seed + i).uniform(-0.008, 0.008),
            mech_key(seed + i, 'space' if text[i] == ' ' else 'key'), 0.32)

def enter_at(at):
    mix(sfx, at, mech_key(999, 'enter'), 0.42)

# title
mix(sfx, 0.35, pop(300, 700), 0.4)
mix(sfx, 1.0, pop(), 0.25); mix(sfx, 1.25, pop(600, 1100), 0.25)
for i in range(5): mix(sfx, 2.35 + i * 0.15, pop(700 + i * 60, 1200 + i * 60), 0.12)
# copy
mix(sfx, 5 + 1.45, pop(400, 800), 0.25)
mix(sfx, 5 + 2.0, whoosh(2.6, seed=42, rise=0.5, bright=0.12), 0.3)
mix(sfx, 5 + 4.6, pop(350, 600), 0.4)
mix(sfx, 5 + 5.05, ding(1567.98), 0.18)
# extract
typing(12.5 + 0.8, 12.5 + 2.6, 'tar -xzf ubuntu-mac-kit.tar.gz', 100)
enter_at(12.5 + 2.7)
mix(sfx, 12.5 + 3.05, whoosh(0.5, seed=7, rise=0.3, bright=0.4), 0.25)
mix(sfx, 12.5 + 3.45, pop(300, 650), 0.4)
for i in range(6): mix(sfx, 12.5 + 4.42 + i * 0.25, pop(650 + i * 50, 1050 + i * 50), 0.16)
# install
typing(20.5 + 0.6, 20.5 + 2.4, 'cd ubuntu-mac-kit && ./install.sh', 200)
enter_at(20.5 + 2.5)
notes = [72, 74, 76, 79, 81, 84, 86]
for i in range(7):
    mix(sfx, 20.5 + 3.4 + i * 0.85 + 0.27, ding(mtof(notes[i] + 12)), 0.13)
mix(sfx, 20.5 + 3.4 + 0.85 * 7 + 0.6, chime(), 0.22)
# logout
mix(sfx, 32 + 2.6, mouse_click(), 0.5)
mix(sfx, 32 + 3.2, whoosh(0.9, seed=9, rise=0.2, bright=0.08), 0.35)
for i in range(1, 9): mix(sfx, 32 + 4.3 + i * (1.0 / 8), mech_key(300 + i), 0.24)
mix(sfx, 32 + 5.55, ding(1760), 0.16)
# done
mix(sfx, 39 + 1.5, whoosh(3.0, seed=11, rise=0.5, bright=0.1), 0.35)
mix(sfx, 39 + 4.4, chime(), 0.2)
for i in range(3): mix(sfx, 39 + 5.05 + i * 0.4, pop(600 + i * 100, 1100 + i * 100), 0.25)
# undo
typing(47.5 + 0.9, 47.5 + 2.0, './uninstall.sh', 400)
enter_at(47.5 + 2.1)
rev = whoosh(1.0, seed=13, rise=0.85, bright=0.15)
mix(sfx, 47.5 + 2.6, rev, 0.35)
mix(sfx, 47.5 + 3.05, ding(1318.5), 0.15)
# end
for i in range(3): mix(sfx, 53 + 0.62 + i * 0.35, pop(500 + i * 120, 900 + i * 120), 0.25)
mix(sfx, 53 + 2.25, chime(), 0.22)

# ---------------- master ----------------
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    frames = bytearray()
    for i in range(N):
        m = music[i]
        s = sfx[i]
        l = math.tanh((m + s) * 1.1) * 0.85
        v = int(l * 32767)
        frames += struct.pack('<hh', v, v)
    w.writeframes(bytes(frames))
print('ok')
