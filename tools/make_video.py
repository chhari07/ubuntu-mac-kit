#!/usr/bin/env python3
"""Animated, illustrated how-to video: installing the Ubuntu Mac Kit.

Usage: make_video.py OUT.mp4 [--1080p] [--captions] [--endcard] [--srt FILE]
  --1080p     render at 1920x1080 instead of 1280x720
  --captions  burn subtitles into the picture (for feeds that autoplay muted)
  --endcard   add a closing card with the repository link
  --srt FILE  also write the captions as an .srt subtitle file
"""
import math, subprocess, sys
import cairo

W, H, FPS = 1280, 720, 30
ARGS = sys.argv[1:]
OUT = ARGS[0] if ARGS else 'walkthrough.mp4'
SCALE = 1.5 if '--1080p' in ARGS else 1.0
CAPTIONS = '--captions' in ARGS
ENDCARD = '--endcard' in ARGS
SRT = ARGS[ARGS.index('--srt') + 1] if '--srt' in ARGS else None
REPO_URL = 'github.com/chhari07/ubuntu-mac-kit'

# theme-tokens.json colours
def hx(s, a=1.0):
    s = s.lstrip('#')
    r, g, b = (int(s[i:i+2], 16) / 255 for i in (0, 2, 4))
    if len(s) == 8:
        a = int(s[6:8], 16) / 255
    return (r, g, b, a)

CANVAS = hx('#1E1E1E'); WIN = hx('#2C2C2C'); BASE = hx('#272727'); VIEW = hx('#181818')
BORDER = hx('#4A4A4A'); FG = hx('#F7F7F7'); MUTED = hx('#929292')
BLUE = hx('#0073E5'); RING = hx('#2D97FF'); GREEN = hx('#109B26'); ORANGE = hx('#F99B11')
RED = hx('#C7162B'); FTOP = hx('#7FCBFA'); FBACK = hx('#3F9CE6')
FONT = 'Ubuntu Sans'; MONO = 'Ubuntu Mono'

def clamp(x, a=0, b=1): return max(a, min(b, x))
def ease(x):
    x = clamp(x); return 1 - (1 - x) ** 3
def ease_io(x):
    x = clamp(x); return 3 * x * x - 2 * x * x * x
def back(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def seg(t, a, b): return clamp((t - a) / (b - a))
def lerp(a, b, k): return a + (b - a) * k

def col(cr, c, a=1.0):
    cr.set_source_rgba(c[0], c[1], c[2], c[3] * a)

def rrect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()

def text(cr, s, x, y, size, c=FG, bold=False, a=1.0, align='l', font=FONT):
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL,
                        cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(size)
    ext = cr.text_extents(s)
    if align == 'c': x -= ext.x_advance / 2
    elif align == 'r': x -= ext.x_advance
    col(cr, c, a); cr.move_to(x, y); cr.show_text(s); cr.new_path()
    return ext.x_advance

def shadow(cr, x, y, w, h, r, a=1.0):
    for i in range(6, 0, -1):
        rrect(cr, x - i * 2, y - i * 2 + 8, w + i * 4, h + i * 4, r + i * 2)
        cr.set_source_rgba(0, 0, 0, 0.05 * a); cr.fill()

# ---------- illustrations ----------
def folder(cr, x, y, w, a=1.0, label=None):
    h = w * 0.78
    tab_w, tab_h = w * 0.42, h * 0.14
    # back + tab
    cr.new_path()
    rrect(cr, x, y + tab_h * 0.6, w, h - tab_h * 0.6, w * 0.08)
    rrect(cr, x, y, tab_w, tab_h * 1.6, w * 0.06)
    col(cr, FBACK, a); cr.fill()
    # front
    g = cairo.LinearGradient(0, y + tab_h, 0, y + h)
    g.add_color_stop_rgba(0, FTOP[0], FTOP[1], FTOP[2], a)
    g.add_color_stop_rgba(1, 0.36, 0.69, 0.95, a)
    rrect(cr, x, y + tab_h * 1.25, w, h - tab_h * 1.25, w * 0.08)
    cr.set_source(g); cr.fill()
    rrect(cr, x, y + tab_h * 1.25, w, w * 0.025, w * 0.012)
    cr.set_source_rgba(1, 1, 1, 0.35 * a); cr.fill()
    if label:
        text(cr, label, x + w / 2, y + h + 22, 15, FG, a=a, align='c')

def page(cr, x, y, w, tag, tag_col=BLUE, a=1.0, label=None):
    h = w * 1.25; f = w * 0.28
    cr.new_path()
    cr.move_to(x, y); cr.line_to(x + w - f, y); cr.line_to(x + w, y + f)
    cr.line_to(x + w, y + h); cr.line_to(x, y + h); cr.close_path()
    cr.set_source_rgba(0.97, 0.97, 0.97, a); cr.fill()
    cr.move_to(x + w - f, y); cr.line_to(x + w - f, y + f); cr.line_to(x + w, y + f); cr.close_path()
    cr.set_source_rgba(0.78, 0.78, 0.80, a); cr.fill()
    for i in range(3):
        rrect(cr, x + w * 0.18, y + h * (0.35 + i * 0.1), w * (0.64 - i * 0.12), w * 0.04, 2)
        cr.set_source_rgba(0.7, 0.7, 0.72, a); cr.fill()
    rrect(cr, x + w * 0.12, y + h * 0.72, w * 0.76, h * 0.17, 4)
    col(cr, tag_col, a); cr.fill()
    text(cr, tag, x + w / 2, y + h * 0.85, w * 0.2, (1, 1, 1, 1), bold=True, a=a, align='c')
    if label:
        text(cr, label, x + w / 2, y + h + 22, 15, FG, a=a, align='c')

def archive(cr, x, y, w, a=1.0, label=None):
    page(cr, x, y, w, 'TAR.GZ', ORANGE, a)
    # zipper stripe
    for i in range(5):
        rrect(cr, x + w / 2 - 5, y + 8 + i * 9, 10, 5, 1)
        cr.set_source_rgba(0.45, 0.45, 0.48, a); cr.fill()
    if label:
        text(cr, label, x + w / 2, y + w * 1.25 + 22, 15, FG, a=a, align='c')

def laptop(cr, cx, cy, w, title, a=1.0, glow=0.0):
    sw, sh = w, w * 0.62
    x, y = cx - sw / 2, cy - sh / 2
    if glow > 0:
        rrect(cr, x - 10, y - 10, sw + 20, sh + 20, 24); col(cr, RING, 0.25 * glow * a); cr.fill()
    rrect(cr, x, y, sw, sh, 14); cr.set_source_rgba(0.11, 0.11, 0.12, a); cr.fill()
    rrect(cr, x + 10, y + 10, sw - 20, sh - 20, 6)
    g = cairo.LinearGradient(x, y, x + sw, y + sh)
    g.add_color_stop_rgba(0, 0.17, 0.0, 0.12, a); g.add_color_stop_rgba(1, 0.33, 0.12, 0.10, a)
    cr.set_source(g); cr.fill()
    cr.move_to(x - 30, y + sh + 4); cr.line_to(x + sw + 30, y + sh + 4)
    cr.line_to(x + sw + 10, y + sh + 22); cr.line_to(x - 10, y + sh + 22); cr.close_path()
    cr.set_source_rgba(0.55, 0.55, 0.58, a); cr.fill()
    text(cr, title, cx, y + sh + 54, 17, MUTED, a=a, align='c')
    return x + 10, y + 10, sw - 20, sh - 20

def usb(cr, x, y, s, a=1.0):
    rrect(cr, x, y, s * 2.2, s, s * 0.2); col(cr, BLUE, a); cr.fill()
    rrect(cr, x + s * 2.2, y + s * 0.2, s * 0.8, s * 0.6, 3); cr.set_source_rgba(0.8, 0.8, 0.82, a); cr.fill()
    text(cr, 'USB', x + s * 1.1, y + s * 0.68, s * 0.42, (1, 1, 1, 1), bold=True, a=a, align='c')

def check(cr, cx, cy, r, k, a=1.0):
    if k <= 0: return
    cr.arc(cx, cy, r * back(k), 0, 2 * math.pi); col(cr, GREEN, a); cr.fill()
    cr.set_line_width(r * 0.28); cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.set_line_join(cairo.LINE_JOIN_ROUND)
    p = clamp((k - 0.3) / 0.7)
    if p > 0:
        pts = [(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.48, cy - r * 0.35)]
        cr.move_to(*pts[0])
        if p < 0.4:
            q = p / 0.4; cr.line_to(lerp(pts[0][0], pts[1][0], q), lerp(pts[0][1], pts[1][1], q))
        else:
            q = (p - 0.4) / 0.6; cr.line_to(*pts[1]); cr.line_to(lerp(pts[1][0], pts[2][0], q), lerp(pts[1][1], pts[2][1], q))
        cr.set_source_rgba(1, 1, 1, a); cr.stroke()

def pointer(cr, x, y, a=1.0, click=0.0):
    if click > 0:
        cr.arc(x, y, 8 + 22 * click, 0, 2 * math.pi); col(cr, RING, (1 - click) * 0.6 * a)
        cr.set_line_width(3); cr.stroke()
    cr.move_to(x, y); cr.line_to(x, y + 26); cr.line_to(x + 7, y + 20); cr.line_to(x + 12, y + 30)
    cr.line_to(x + 16, y + 28); cr.line_to(x + 11, y + 18); cr.line_to(x + 19, y + 18); cr.close_path()
    cr.set_source_rgba(0, 0, 0, a); cr.fill_preserve(); cr.set_source_rgba(1, 1, 1, a); cr.set_line_width(1.6); cr.stroke()

def terminal(cr, x, y, w, h, lines, a=1.0, title='Terminal — ~'):
    shadow(cr, x, y, w, h, 12, a)
    rrect(cr, x, y, w, h, 12); col(cr, VIEW, a); cr.fill()
    rrect(cr, x, y, w, h, 12); col(cr, BORDER, a); cr.set_line_width(1); cr.stroke()
    cr.save(); rrect(cr, x, y, w, 38, 12); cr.clip(); cr.rectangle(x, y, w, 38); col(cr, WIN, a); cr.fill(); cr.restore()
    for i, c in enumerate([hx('#FF5F57'), hx('#FEBC2E'), hx('#28C840')]):
        cr.arc(x + 22 + i * 22, y + 19, 7, 0, 2 * math.pi); col(cr, c, a); cr.fill()
    text(cr, title, x + w / 2, y + 25, 14, MUTED, a=a, align='c')
    ly = y + 72
    for ln in lines:
        if ln is None: ly += 30; continue
        parts = ln if isinstance(ln, list) else [(ln, FG)]
        lx = x + 22
        for s, c in parts:
            if s == '▌':  # block cursor, drawn because the mono font lacks the glyph
                cr.rectangle(lx + 1, ly - 17, 10, 22); col(cr, FG, 0.85 * a); cr.fill(); lx += 12; continue
            lx += text(cr, s, lx, ly, 19, c, a=a, font=MONO)
        ly += 30
    return ly

def type_fracs(s):
    """Human, uneven keystroke times (fractions 0..1); make_audio.py uses the same schedule."""
    import random
    r = random.Random(len(s) * 7919)
    iv = []
    for i, ch in enumerate(s):
        d = r.uniform(0.55, 1.5)
        if i > 0 and s[i - 1] == ' ': d *= 1.9
        iv.append(d)
    tot = sum(iv); acc = 0; out = []
    for d in iv:
        acc += d; out.append(acc / tot)
    return out

def typed(s, k):
    return s[:sum(1 for f in type_fracs(s) if f <= k)]

def typed_parts(s, k, dur):
    """Typed text split so the newest letter can flash like a typewriter strike."""
    fr = type_fracs(s)
    n = sum(1 for f in fr if f <= k)
    if n == 0 or k >= 1: return [(s[:n], FG)], 0.0
    since = (k - fr[n - 1]) * dur
    strike = clamp(1 - since / 0.12)
    c = tuple(lerp(FG[i], FTOP[i], strike) for i in range(3)) + (1,)
    return [(s[:n - 1], FG), (s[n - 1], c)], strike

def caret(t): return '▌' if int(t * 2.2) % 2 == 0 else ' '

# ---------- frame chrome ----------
STEPS = ['Copy', 'Extract', 'Install', 'Log out / in', 'Done']

def background(cr):
    col(cr, CANVAS); cr.paint()
    g = cairo.RadialGradient(W * 0.75, -100, 50, W * 0.75, -100, 900)
    g.add_color_stop_rgba(0, BLUE[0], BLUE[1], BLUE[2], 0.16); g.add_color_stop_rgba(1, 0, 0, 0, 0)
    cr.set_source(g); cr.paint()

def stepbar(cr, active, k):
    x0, y0 = 360, 40; gap = 140
    for i, name in enumerate(STEPS):
        cx = x0 + i * gap
        if i < len(STEPS) - 1:
            cr.rectangle(cx + 12, y0 - 1.5, gap - 24, 3)
            col(cr, BORDER if i >= active else BLUE); cr.fill()
        on = i <= active
        r = 11 if i != active else 11 + 3 * math.sin(k * math.pi * 2) * 0.3 + 2
        cr.arc(cx, y0, r, 0, 2 * math.pi); col(cr, BLUE if on else WIN); cr.fill()
        if not on:
            cr.arc(cx, y0, r, 0, 2 * math.pi); col(cr, BORDER); cr.set_line_width(2); cr.stroke()
        text(cr, str(i + 1), cx, y0 + 5, 13, FG if on else MUTED, bold=True, align='c')
        text(cr, name, cx, y0 + 32, 13, FG if i == active else MUTED, bold=(i == active), align='c')

def heading(cr, step, title, sub, t):
    k = ease(seg(t, 0.1, 0.8))
    text(cr, f'STEP {step}', 80, 140 - 10 * (1 - k), 15, RING, bold=True, a=k)
    text(cr, title, 80, 180 - 10 * (1 - k), 36, FG, bold=True, a=k)
    k2 = ease(seg(t, 0.4, 1.1))
    text(cr, sub, 80, 214, 18, MUTED, a=k2)

# ---------- scenes ----------
def s_title(cr, t, d):
    k = back(seg(t, 0.2, 1.2))
    cx, cy = W / 2, 290
    cr.save(); cr.translate(cx, cy); cr.scale(k, k)
    # kit box
    shadow(cr, -90, -70, 180, 140, 24)
    rrect(cr, -90, -70, 180, 140, 24); col(cr, WIN); cr.fill()
    rrect(cr, -90, -70, 180, 140, 24); col(cr, BORDER); cr.set_line_width(1.5); cr.stroke()
    folder(cr, -56, -46, 112)
    cr.restore()
    for i, (dx, tg, c) in enumerate([(-230, 'SH', GREEN), (170, 'SVG', BLUE)]):
        kk = back(seg(t, 0.9 + i * 0.25, 1.7 + i * 0.25))
        cr.save(); cr.translate(cx + dx + 30, cy - 10 + math.sin(t * 2 + i) * 6); cr.scale(kk, kk)
        page(cr, -30, -38, 60, tg, c); cr.restore()
    a = ease(seg(t, 1.1, 2.0))
    text(cr, 'Ubuntu Mac Kit', cx, 450 + 12 * (1 - a), 56, FG, bold=True, a=a, align='c')
    a2 = ease(seg(t, 1.6, 2.5))
    text(cr, 'Install your whole Mac look on a new Ubuntu with one command', cx, 494, 21, MUTED, a=a2, align='c')
    a3 = ease(seg(t, 2.3, 3.2))
    chips = ['WhiteSur-dark + blue folders', 'MacTahoe GTK4', 'macOS cursor', 'Mac Bar', 'Glass dock']
    xs = cx - 470
    for i, c in enumerate(chips):
        kk = ease(seg(t, 2.3 + i * 0.15, 3.0 + i * 0.15))
        cr.select_font_face(FONT, 0, 0); cr.set_font_size(15); w = cr.text_extents(c).x_advance + 32
        rrect(cr, xs, 540 + 10 * (1 - kk), w, 34, 17); col(cr, WIN, kk); cr.fill()
        rrect(cr, xs, 540 + 10 * (1 - kk), w, 34, 17); col(cr, BORDER, kk); cr.set_line_width(1); cr.stroke()
        text(cr, c, xs + 16, 562 + 10 * (1 - kk), 15, FG, a=kk); xs += w + 12

def s_copy(cr, t, d):
    stepbar(cr, 0, t)
    heading(cr, 1, 'Copy the kit to the new PC', 'Download it from GitHub Releases, or use a USB stick or scp.', t)
    a = ease(seg(t, 0.3, 1.0))
    lx, ly, lw, lh = laptop(cr, 330, 430, 330, 'This PC (your Mac look)', a)
    # paint the "after" look on the source laptop screen
    cr.save(); rrect(cr, lx, ly, lw, lh, 6); cr.clip()
    col(cr, hx('#101320'), a); cr.paint()
    cr.rectangle(lx, ly, lw, 14); cr.set_source_rgba(0.08, 0.08, 0.1, 0.6 * a); cr.fill()
    for i in range(4):
        folder(cr, lx + 20, ly + 26 + i * 40, 30, a)
    cr.restore()
    b = ease(seg(t, 0.6, 1.3))
    rx, ry, rw, rh = laptop(cr, 950, 430, 330, 'New PC (fresh Ubuntu)', b, glow=ease(seg(t, 5.0, 5.6)))
    # archive travelling
    k = ease_io(seg(t, 2.0, 4.6))
    sx, sy = 330 - 34, 380
    ex, ey = rx + 30, ry + 26
    px = lerp(sx, ex, k); py = lerp(sy, ey, k) - math.sin(k * math.pi) * 140
    if t > 1.4:
        aa = ease(seg(t, 1.4, 1.9))
        if 0.05 < k < 0.95:
            usb(cr, px - 20, py + 70, 26, aa)
        archive(cr, px, py, 62 if k < 1 else 48, aa)
    if k >= 1:
        text(cr, 'ubuntu-mac-kit.tar.gz', rx + 54, ry + 120, 13, FG, align='c')
    # dashed trail
    if 0 < k < 1:
        cr.set_dash([6, 8]); cr.set_line_width(2); col(cr, RING, 0.5)
        cr.move_to(sx + 31, sy + 40)
        for i in range(1, 31):
            q = k * i / 30
            cr.line_to(lerp(sx, ex, q) + 31, lerp(sy, ey, q) - math.sin(q * math.pi) * 140 + 40)
        cr.stroke(); cr.set_dash([])
    c = ease(seg(t, 5.0, 5.8))
    text(cr, 'Put it in your Home folder:  ~/ubuntu-mac-kit.tar.gz', W / 2, 670, 19, FG, a=c, align='c', font=MONO)

def s_extract(cr, t, d):
    stepbar(cr, 1, t)
    heading(cr, 2, 'Extract it', 'Right-click the file and choose Extract, or type the command below.', t)
    cmd = 'tar -xzf ubuntu-mac-kit.tar.gz'
    tk = seg(t, 0.8, 2.6)
    tp, strike = typed_parts(cmd, tk, 1.8)
    cr.save(); cr.translate(0, 1.5 * strike)
    terminal(cr, 80, 260, 580, 170, [[('aman@new-pc', GREEN), (':~$ ', BLUE)] + tp + [(caret(t) if tk < 1 or t < 3 else '', FG)]],
             a=ease(seg(t, 0.3, 0.9)))
    cr.restore()
    # archive pops open into folder + files
    open_k = ease(seg(t, 3.0, 3.8))
    ax, ay = 820, 300
    if open_k < 1:
        cr.save(); cr.translate(ax + 40, ay + 50); s_ = 1 + 0.15 * math.sin(open_k * math.pi); cr.scale(s_, s_)
        archive(cr, -40, -50, 80, 1 - open_k); cr.restore()
    fk = back(seg(t, 3.4, 4.2))
    if fk > 0:
        cr.save(); cr.translate(ax + 50, ay + 40); cr.scale(fk, fk); folder(cr, -50, -40, 100); cr.restore()
        text(cr, 'ubuntu-mac-kit/', ax + 50, ay + 130, 17, FG, bold=True, a=clamp(fk), align='c')
    items = [('install.sh', 'SH', GREEN), ('uninstall.sh', 'SH', RED), ('README.md', 'MD', BLUE),
             ('icons/', None, None), ('themes/', None, None), ('extension/', None, None)]
    for i, (name, tag, c) in enumerate(items):
        k = ease(seg(t, 4.4 + i * 0.25, 5.0 + i * 0.25))
        if k <= 0: continue
        gx = 690 + (i % 3) * 150; gy = 470 + (i // 3) * 110
        oy = 20 * (1 - k)
        if tag: page(cr, gx + 47, gy + oy, 46, tag, c, k)
        else: folder(cr, gx + 40, gy + oy + 8, 60, k)
        text(cr, name, gx + 70, gy + oy + 84, 14, FG, a=k, align='c')
        cr.set_line_width(1.5); col(cr, BORDER, 0.6 * k)
        cr.move_to(ax + 50, ay + 140); cr.line_to(gx + 70, gy + oy - 4); cr.stroke()
    c = ease(seg(t, 5.8, 6.5))
    text(cr, 'Everything the installer needs is inside — no internet, no sudo.', 80, 520, 18, MUTED, a=c)

def s_install(cr, t, d):
    stepbar(cr, 2, t)
    heading(cr, 3, 'Run the installer', 'One command. It copies the theme files and applies every setting.', t)
    cmd = 'cd ubuntu-mac-kit && ./install.sh'
    tk = seg(t, 0.6, 2.4)
    steps = ['Icons — WhiteSur-dark + blue Mac folders + file pages',
             'GTK — Yaru-blue-dark + MacTahoe styling for GTK4 apps',
             'Cursor — macOS',
             'Window buttons — close, minimize, maximize on the left',
             'Mac Bar — glass top bar extension',
             'Dock — glass, bottom, 48px icons',
             'Files dock icon + icon-lock service']
    tp, strike = typed_parts(cmd, tk, 1.8)
    lines = [[('aman@new-pc', GREEN), (':~$ ', BLUE)] + tp + [(caret(t) if tk < 1 else '', FG)]]
    if t > 2.8:
        lines.append([('Ubuntu Mac Kit installer — backing up current settings…', MUTED)])
    start = 3.4; per = 0.85
    done = 0
    for i, s in enumerate(steps):
        st = start + i * per
        if t > st:
            lines.append([('  ', FG), (s, FG)]); done = i + 1
    tx, ty, tw, th = 80, 250, 1120, 420
    cr.save(); cr.translate(0, 1.5 * strike)
    terminal(cr, tx, ty, tw, th, lines, a=ease(seg(t, 0.2, 0.8)), title='Terminal — ~/ubuntu-mac-kit')
    cr.restore()
    for i in range(done):
        st = start + i * per
        k = seg(t, st + 0.25, st + 0.65)
        if k > 0:
            check(cr, tx + 30, ty + 72 + 60 + i * 30 - 6, 9, k)
        else:
            ang = t * 8
            cr.arc(tx + 30, ty + 72 + 60 + i * 30 - 6, 7, ang, ang + 4.5); col(cr, RING); cr.set_line_width(2.5); cr.stroke()
    # progress bar
    p = clamp((t - start) / (per * len(steps) + 0.4))
    if t > start - 0.3:
        bx, by, bw = tx + 22, ty + th - 40, tw - 44
        rrect(cr, bx, by, bw, 10, 5); col(cr, WIN); cr.fill()
        rrect(cr, bx, by, max(10, bw * p), 10, 5); col(cr, BLUE if p < 1 else GREEN); cr.fill()
        text(cr, f'{int(p * 100)}%', bx + bw, by - 10, 15, FG, bold=True, align='r')
    if p >= 1:
        k = ease(seg(t, start + per * len(steps) + 0.6, start + per * len(steps) + 1.2))
        text(cr, 'Done!  Log out and log back in to finish.', tx + 22, ty + th - 58, 19, GREEN, bold=True, a=k, font=MONO)

def s_logout(cr, t, d):
    stepbar(cr, 3, t)
    heading(cr, 4, 'Log out, then log back in', 'Ubuntu (Wayland) loads the new top-bar extension on a fresh login.', t)
    # menu illustration
    mx, my = 760, 250
    a = ease(seg(t, 0.4, 1.0))
    shadow(cr, mx, my, 360, 300, 16, a)
    rrect(cr, mx, my, 360, 300, 16); col(cr, WIN, a); cr.fill()
    rrect(cr, mx, my, 360, 300, 16); col(cr, BORDER, a); cr.set_line_width(1); cr.stroke()
    items = ['About This PC', 'Settings', 'Sleep', 'Restart…', 'Shut Down…', 'Lock Screen', 'Log Out…']
    hi = ease(seg(t, 2.2, 2.6))
    for i, s in enumerate(items):
        iy = my + 22 + i * 38
        if i == 6 and hi > 0:
            rrect(cr, mx + 10, iy - 4, 340, 34, 8); col(cr, BLUE, hi * a); cr.fill()
        if i in (2, 5):
            cr.rectangle(mx + 18, iy - 8, 324, 1); col(cr, BORDER, a); cr.fill()
        text(cr, s, mx + 26, iy + 19, 17, FG, a=a, bold=(i == 6 and hi > 0.5))
    # pointer moves to Log Out
    pk = ease_io(seg(t, 1.0, 2.2))
    px, py = lerp(1150, mx + 200, pk), lerp(640, my + 22 + 6 * 38 + 14, pk)
    click = seg(t, 2.6, 3.1)
    pointer(cr, px, py, a, click if 0 < click < 1 else 0)
    # screen dims then login card
    dim = ease(seg(t, 3.2, 3.9)) * (1 - ease(seg(t, 6.0, 6.6)))
    if dim > 0:
        cr.set_source_rgba(0, 0, 0, 0.85 * dim); cr.paint()
        cx, cy = W / 2, 380
        cr.arc(cx, cy - 40, 52, 0, 2 * math.pi); col(cr, BLUE, dim); cr.fill()
        text(cr, 'A', cx, cy - 22, 50, FG, bold=True, a=dim, align='c')
        text(cr, 'Aman', cx, cy + 50, 26, FG, bold=True, a=dim, align='c')
        rrect(cr, cx - 140, cy + 72, 280, 44, 22); col(cr, WIN, dim); cr.fill()
        dots = int(clamp(seg(t, 4.3, 5.3)) * 8)
        text(cr, '•' * dots, cx, cy + 102, 24, FG, a=dim, align='c')
        if t > 5.5:
            check(cr, cx + 170, cy + 94, 16, seg(t, 5.5, 5.9), dim)

def draw_desktop(cr, x, y, w, h, after, a=1.0):
    cr.save(); cr.rectangle(x, y, w, h); cr.clip()
    if after:
        g = cairo.LinearGradient(x, y, x + w, y + h)
        g.add_color_stop_rgb(0, 0.05, 0.06, 0.11); g.add_color_stop_rgb(1, 0.09, 0.07, 0.16)
        cr.set_source(g); cr.paint()
        # node network wallpaper
        import random
        rnd = random.Random(7)
        pts = [(x + rnd.random() * w, y + rnd.random() * h) for _ in range(34)]
        cr.set_line_width(1)
        for i, p in enumerate(pts):
            for q in pts[i + 1:]:
                if math.dist(p, q) < 150:
                    cr.move_to(*p); cr.line_to(*q); cr.set_source_rgba(0.35, 0.6, 1, 0.12); cr.stroke()
        for p in pts:
            cr.arc(p[0], p[1], 2.5, 0, 2 * math.pi); cr.set_source_rgba(0.5, 0.75, 1, 0.6); cr.fill()
        # glass top bar
        cr.rectangle(x, y, w, 30); col(cr, hx('#14141A59')); cr.fill()
        cr.rectangle(x, y + 30, w, 1); cr.set_source_rgba(1, 1, 1, 0.08); cr.fill()
        cr.arc(x + 22, y + 15, 8, 0, 2 * math.pi); cr.set_source_rgba(0.91, 0.33, 0.13, 1); cr.fill()
        cr.arc(x + 22, y + 15, 4, 0, 2 * math.pi); cr.set_source_rgba(1, 1, 1, 1); cr.fill()
        for i, s in enumerate(['Files', 'Edit', 'View', 'Go']):
            text(cr, s, x + 46 + i * 56, y + 20, 14, FG, bold=(i == 0))
        text(cr, 'Mon 26 Oct  9:41 PM', x + w - 16, y + 20, 14, FG, bold=True, align='r')
        rrect(cr, x + w - 218, y + 7, 16, 16, 3); col(cr, ORANGE); cr.fill()
        # desktop icons
        names = ['projects', 'career', 'notes']
        for i, n in enumerate(names):
            folder(cr, x + w - 120, y + 60 + i * 110, 70, label=n)
        page(cr, x + w - 220, y + 60, 54, 'PDF', RED, label='Resume.pdf')
        page(cr, x + w - 220, y + 170, 54, 'PNG', BLUE, label='me.png')
        # window
        wx, wy, ww, wh = x + 60, y + 60, w * 0.5, h * 0.55
        shadow(cr, wx, wy, ww, wh, 12)
        rrect(cr, wx, wy, ww, wh, 12); col(cr, WIN); cr.fill()
        for i, c in enumerate([hx('#FF5F57'), hx('#FEBC2E'), hx('#28C840')]):
            cr.arc(wx + 20 + i * 20, wy + 20, 6.5, 0, 2 * math.pi); col(cr, c); cr.fill()
        text(cr, 'Home', wx + ww / 2, wy + 25, 14, FG, bold=True, align='c')
        rrect(cr, wx + 10, wy + 44, 140, wh - 54, 8); col(cr, BASE); cr.fill()
        for i, s in enumerate(['Recent', 'Home', 'Desktop', 'Documents', 'Downloads']):
            if i == 1:
                rrect(cr, wx + 16, wy + 54 + i * 30, 128, 26, 6); col(cr, BLUE); cr.fill()
            text(cr, s, wx + 26, wy + 72 + i * 30, 13, FG)
        for i in range(6):
            folder(cr, wx + 180 + (i % 3) * 100, wy + 70 + (i // 3) * 110, 64,
                   label=['Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Videos'][i])
        # glass dock along the bottom
        n_i = 6; dw = n_i * 58 + 18; dx0 = x + (w - dw) / 2; dy0 = y + h - 76
        rrect(cr, dx0, dy0, dw, 64, 18); col(cr, hx('#2C2C2C4D')); cr.fill()
        rrect(cr, dx0, dy0, dw, 64, 18); cr.set_source_rgba(1, 1, 1, 0.14); cr.set_line_width(1); cr.stroke()
        icons = [BLUE, hx('#FF9500'), GREEN, hx('#AF52DE'), RED, hx('#5AC8FA')]
        for i, c in enumerate(icons):
            ix = dx0 + 14 + i * 58
            if i == 0:
                folder(cr, ix, dy0 + 14, 46)
            else:
                rrect(cr, ix, dy0 + 8, 46, 46, 12); col(cr, c); cr.fill()
                rrect(cr, ix, dy0 + 8, 46, 20, 12); cr.set_source_rgba(1, 1, 1, 0.18); cr.fill()
    else:
        g = cairo.LinearGradient(x, y, x + w, y + h)
        g.add_color_stop_rgb(0, 0.17, 0.0, 0.12); g.add_color_stop_rgb(1, 0.91, 0.33, 0.13)
        cr.set_source(g); cr.paint()
        cr.rectangle(x, y, w, 30); cr.set_source_rgb(0.05, 0.05, 0.05); cr.fill()
        text(cr, 'Activities', x + 16, y + 20, 14, FG)
        text(cr, 'Oct 26  21:41', x + w / 2, y + 20, 14, FG, bold=True, align='c')
        cr.rectangle(x, y + 30, 74, h - 30); cr.set_source_rgb(0.12, 0.12, 0.12); cr.fill()
        for i in range(6):
            rrect(cr, x + 13, y + 46 + i * 62, 48, 48, 8); cr.set_source_rgba(0.5 + 0.08 * i, 0.4, 0.3, 1); cr.fill()
        for i, n in enumerate(['projects', 'career', 'notes']):
            yx, yy = x + w - 120, y + 60 + i * 110
            rrect(cr, yx, yy, 70, 52, 6); cr.set_source_rgb(0.55, 0.55, 0.55); cr.fill()
            rrect(cr, yx, yy + 10, 70, 44, 6); cr.set_source_rgb(0.78, 0.47, 0.25); cr.fill()
            text(cr, n, yx + 35, yy + 76, 15, FG, align='c')
    cr.restore()

def s_done(cr, t, d):
    stepbar(cr, 4, t)
    k = ease(seg(t, 0.1, 0.7))
    text(cr, 'STEP 5', 80, 140, 15, RING, bold=True, a=k)
    text(cr, 'Your Mac look is back', 80, 180, 36, FG, bold=True, a=k)
    x, y, w, h = 80, 210, 1120, 470
    shadow(cr, x, y, w, h, 14)
    cr.save(); rrect(cr, x, y, w, h, 14); cr.clip()
    wipe = ease_io(seg(t, 1.5, 4.5))
    draw_desktop(cr, x, y, w, h, after=False)
    cr.save(); cr.rectangle(x, y, w * wipe, h); cr.clip(); draw_desktop(cr, x, y, w, h, after=True); cr.restore()
    cr.restore()
    if 0 < wipe < 1:
        lx = x + w * wipe
        cr.rectangle(lx - 2, y, 4, h); col(cr, FG); cr.fill()
        cr.arc(lx, y + h / 2, 18, 0, 2 * math.pi); col(cr, BLUE); cr.fill()
        text(cr, '< >', lx, y + h / 2 + 6, 16, FG, bold=True, align='c')
    lab = 1 - ease(seg(t, 4.2, 4.8))
    if lab > 0:
        rrect(cr, x + w - 140, y + h - 50, 120, 32, 16); cr.set_source_rgba(0, 0, 0, 0.6 * lab); cr.fill()
        text(cr, 'Before', x + w - 80, y + h - 28, 15, FG, bold=True, a=lab, align='c')
    aft = ease(seg(t, 1.8, 2.4))
    rrect(cr, x + 100, y + h - 50, 120, 32, 16); cr.set_source_rgba(0, 0, 0, 0.6 * aft); cr.fill()
    text(cr, 'After', x + 160, y + h - 28, 15, FG, bold=True, a=aft, align='c')
    for i, (lx, ly, s) in enumerate([(x + 470, y + 22, 'Glass top bar'), (x + w / 2 - 50, y + h - 128, 'Glass dock'),
                                     (x + w - 330, y + 400, 'Blue Mac folders')]):
        kk = back(seg(t, 5.0 + i * 0.4, 5.6 + i * 0.4))
        if kk <= 0: continue
        cr.select_font_face(FONT, 0, 1); cr.set_font_size(15); tw = cr.text_extents(s).x_advance + 28
        cr.save(); cr.translate(lx + tw / 2, ly + 16); cr.scale(kk, kk)
        rrect(cr, -tw / 2, -16, tw, 32, 16); col(cr, BLUE); cr.fill()
        text(cr, s, 0, 6, 15, FG, bold=True, align='c'); cr.restore()

def s_undo(cr, t, d):
    k = ease(seg(t, 0.1, 0.7))
    text(cr, 'CHANGED YOUR MIND?', 80, 140, 15, RING, bold=True, a=k)
    text(cr, 'Undo everything with one command', 80, 180, 36, FG, bold=True, a=k)
    text(cr, 'The installer saved your old settings first, so uninstall puts them back.', 80, 214, 18, MUTED, a=ease(seg(t, 0.4, 1.1)))
    cmd = './uninstall.sh'
    tk = seg(t, 0.9, 2.0)
    tp, strike = typed_parts(cmd, tk, 1.1)
    lines = [[('aman@new-pc', GREEN), (':~/ubuntu-mac-kit$ ', BLUE)] + tp + [(caret(t) if tk < 1 else '', FG)]]
    if t > 2.4: lines.append([('Restoring settings from backup…', MUTED)])
    if t > 3.0: lines.append([('Done. Old theme, cursor, dock and top bar restored.', GREEN)])
    cr.save(); cr.translate(0, 1.5 * strike)
    terminal(cr, 80, 260, 760, 220, lines, a=ease(seg(t, 0.3, 0.9)), title='Terminal — ~/ubuntu-mac-kit')
    cr.restore()
    sp = ease(seg(t, 2.6, 3.6))
    cx, cy = 1030, 370
    cr.save(); cr.translate(cx, cy); cr.rotate(-sp * 2 * math.pi)
    cr.set_line_width(10); cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.new_path(); cr.arc(0, 0, 70, 0.3, 2 * math.pi - 0.3); col(cr, BLUE, k); cr.stroke()
    cr.move_to(70 * math.cos(-0.3) - 18, 70 * math.sin(-0.3) - 10); cr.line_to(70 * math.cos(-0.3), 70 * math.sin(-0.3))
    cr.line_to(70 * math.cos(-0.3) + 14, 70 * math.sin(-0.3) - 18); cr.stroke()
    cr.restore()

def s_end(cr, t, d):
    k = ease(seg(t, 0.1, 0.8))
    text(cr, 'That’s it — 3 commands', W / 2, 170, 44, FG, bold=True, a=k, align='c')
    cmds = [('1', 'Copy', 'download from GitHub Releases'),
            ('2', 'Extract', 'tar -xzf ubuntu-mac-kit.tar.gz'),
            ('3', 'Install', 'cd ubuntu-mac-kit && ./install.sh')]
    for i, (n, name, c) in enumerate(cmds):
        kk = ease(seg(t, 0.6 + i * 0.35, 1.3 + i * 0.35))
        y = 240 + i * 100 + 16 * (1 - kk)
        rrect(cr, 240, y, 800, 76, 16); col(cr, WIN, kk); cr.fill()
        rrect(cr, 240, y, 800, 76, 16); col(cr, BORDER, kk); cr.set_line_width(1); cr.stroke()
        cr.arc(284, y + 38, 20, 0, 2 * math.pi); col(cr, BLUE, kk); cr.fill()
        text(cr, n, 284, y + 45, 20, FG, bold=True, a=kk, align='c')
        text(cr, name, 322, y + 45, 20, FG, bold=True, a=kk)
        text(cr, c, 450, y + 46, 20, FTOP, a=kk, font=MONO)
    kk = ease(seg(t, 2.2, 3.0))
    text(cr, '…then log out and log back in.', W / 2, 590, 21, MUTED, a=kk, align='c')

def s_repo(cr, t, d):
    k = ease(seg(t, 0.1, 0.8))
    cr.save(); cr.translate(W / 2, 205); s_ = back(seg(t, 0.0, 0.7)); cr.scale(s_, s_)
    folder(cr, -60, -48, 120); cr.restore()
    text(cr, 'Ubuntu Mac Kit', W / 2, 345, 54, FG, bold=True, a=k, align='c')
    k2 = ease(seg(t, 0.5, 1.2))
    cr.select_font_face(MONO, 0, 0); cr.set_font_size(26); tw = cr.text_extents(REPO_URL).x_advance + 56
    rrect(cr, W / 2 - tw / 2, 382, tw, 56, 28); col(cr, BLUE, k2); cr.fill()
    text(cr, REPO_URL, W / 2, 419, 26, FG, a=k2, align='c', font=MONO)
    k3 = ease(seg(t, 0.9, 1.6))
    text(cr, 'Ubuntu 24.04  ·  GNOME 46  ·  No sudo  ·  Full uninstall', W / 2, 492, 20, MUTED, a=k3, align='c')
    text(cr, 'Free and open source (GPL-3.0)', W / 2, 524, 20, MUTED, a=k3, align='c')

# (start, end, text) in seconds of the full video
CAPTION_LINES = [
    (0.4, 4.8, 'Ubuntu Mac Kit: my whole macOS-style desktop in one installer'),
    (5.3, 9.0, 'Step 1: download the kit from GitHub Releases'),
    (9.0, 12.3, 'One 14 MB file. It installs offline.'),
    (12.8, 15.4, 'Step 2: extract the archive'),
    (15.4, 20.2, 'Inside: install.sh, uninstall.sh and the theme files'),
    (20.8, 24.0, 'Step 3: run ./install.sh (no sudo needed)'),
    (24.0, 28.5, 'It backs up your settings, then applies icons, cursor, GTK, top bar and dock'),
    (28.5, 31.8, 'Everything goes into your home folder'),
    (32.3, 38.7, 'Step 4: log out and back in to load the new top bar'),
    (39.3, 44.0, 'Step 5: before and after'),
    (44.0, 47.2, 'Glass top bar, glass dock, blue macOS folders'),
    (47.8, 52.7, 'Changed your mind? ./uninstall.sh restores everything'),
    (53.3, 57.8, 'Three steps, then log out and back in'),
    (58.2, 62.3, 'Link in the comments. Feedback welcome.'),
]

def draw_caption(cr, T):
    for a, b, s in CAPTION_LINES:
        if a <= T < b:
            k = min(ease(seg(T, a, a + 0.2)), 1 - ease(seg(T, b - 0.2, b)))
            cr.select_font_face(FONT, 0, cairo.FONT_WEIGHT_BOLD); cr.set_font_size(24)
            tw = cr.text_extents(s).x_advance
            rrect(cr, W / 2 - tw / 2 - 22, 652, tw + 44, 46, 12); cr.set_source_rgba(0, 0, 0, 0.78 * k); cr.fill()
            text(cr, s, W / 2, 683, 24, FG, bold=True, a=k, align='c')

def write_srt(path, total):
    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
        return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'
    with open(path, 'w') as f:
        n = 0
        for a, b, s in CAPTION_LINES:
            if a >= total: continue
            n += 1
            f.write(f'{n}\n{ts(a)} --> {ts(min(b, total))}\n{s}\n\n')

SCENES = [(s_title, 5.0), (s_copy, 7.5), (s_extract, 8.0), (s_install, 11.5),
          (s_logout, 7.0), (s_done, 8.5), (s_undo, 5.5), (s_end, 5.0)]
if ENDCARD:
    SCENES.append((s_repo, 4.5))

def main():
    total = sum(d for _, d in SCENES)
    n = int(total * FPS)
    PW, PH = int(W * SCALE), int(H * SCALE)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra',
                           '-s', f'{PW}x{PH}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                           '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, PW, PH)
    for f in range(n):
        T = f / FPS
        acc = 0
        for fn, d in SCENES:
            if T < acc + d or fn is SCENES[-1][0]:
                break
            acc += d
        t = T - acc
        cr = cairo.Context(surf)
        cr.set_antialias(cairo.ANTIALIAS_BEST)
        cr.scale(SCALE, SCALE)
        background(cr)
        # slide + zoom transition: scenes enter from the right and leave to the left
        kin = 1.0 if fn is SCENES[0][0] else ease(seg(t, 0, 0.55))
        kout = 0.0 if fn is SCENES[-1][0] else ease_io(seg(t, d - 0.45, d))
        dx = 90 * (1 - kin) - 90 * kout
        sc = 1 - 0.04 * (1 - kin) - 0.04 * kout
        cr.push_group()
        cr.save()
        cr.translate(W / 2 + dx, H / 2); cr.scale(sc, sc); cr.translate(-W / 2, -H / 2)
        fn(cr, t, d)
        cr.restore()
        cr.pop_group_to_source()
        cr.paint_with_alpha(min(kin, 1 - kout))
        # light sweep across the screen at each scene change
        sw = seg(t, 0, 0.6) if fn is not SCENES[0][0] else 1
        if sw < 1:
            sx = lerp(-200, W + 200, ease_io(sw))
            g = cairo.LinearGradient(sx - 160, 0, sx + 160, 0)
            g.add_color_stop_rgba(0, RING[0], RING[1], RING[2], 0)
            g.add_color_stop_rgba(0.5, RING[0], RING[1], RING[2], 0.22 * math.sin(sw * math.pi))
            g.add_color_stop_rgba(1, RING[0], RING[1], RING[2], 0)
            cr.set_source(g); cr.paint()
        if CAPTIONS:
            draw_caption(cr, T)
        surf.flush()
        ff.stdin.write(bytes(surf.get_data()))
    ff.stdin.close(); ff.wait()
    print('frames', n, 'seconds', total)

if __name__ == '__main__':
    if SRT:
        write_srt(SRT, sum(d for _, d in SCENES))
    main()
