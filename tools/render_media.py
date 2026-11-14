#!/usr/bin/env python3
"""Render the README screenshots and GIFs from courierhst's own output.

    python3 tools/render_media.py --out docs/media [--only NAME]

courierhst runs in a pty with fixed seeds, its output goes through a pyte
80x26 screen (the 25-row BBS window plus the status bar), and the cells are
drawn with Px437 IBM VGA 8x16 (tools/fonts) in the 16-colour VGA palette.
Nothing is recorded from anybody's screen. Needs: pip install '.[media]'.
"""
import argparse
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

try:
    import pyte
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("render_media.py needs pyte and Pillow: pip install '.[media]'")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT = os.path.join(HERE, "fonts", "Px437_IBM_VGA_8x16.ttf")

COLS, ROWS = 80, 26
CW, CH = 8, 16

PALETTE = [
    0x000000, 0x0000AA, 0x00AA00, 0x00AAAA, 0xAA0000, 0xAA00AA, 0xAA5500,
    0xAAAAAA, 0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555, 0xFF55FF,
    0xFFFF55, 0xFFFFFF,
]
RGB = [((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in PALETTE]

# pyte colour name -> DOS colour number (0-7, the dark half)
BASE = {"black": 0, "blue": 1, "green": 2, "cyan": 3, "red": 4,
        "magenta": 5, "brown": 6, "yellow": 6, "white": 7}

# A fixed clock for the "Logon ... at HH:MM" line, so no real time of day
# from the machine ends up in the images.
LAUNCH = (
    "import sys, time, runpy;"
    "_t = time.struct_time((1993, 8, 17, 23, 7, 0, 1, 229, 0));"
    "time.localtime = lambda *a: _t;"
    "sys.argv[0] = 'courierhst';"
    "runpy.run_module('courierhst', run_name='__main__', alter_sys=True)"
)
HANDLE = "Raven"


# --------------------------------------------------------------------------
# Running the app
# --------------------------------------------------------------------------

def capture(seed, style, warp, stop=None, extra=(), timeout=240, idle=None):
    """Run one call in a pty. Returns [(simulated_seconds, bytes), ...].

    stop(screen) is called after every chunk; return True to end the run.
    With idle=SECONDS (simulated), the run ends once stop() is true and the
    line then goes quiet for that long (so a screen that is still painting finishes).
    """
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
    env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
    for k in ("COLUMNS", "LINES"):
        env.pop(k, None)
    cmd = [sys.executable, "-c", LAUNCH, "--seed", str(seed),
           "--board-style", style, "--warp", str(warp), "--no-center",
           "--noise", "0", "--calls", "1", "--no-exit-on-key",
           "--handle", HANDLE, *extra]
    proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave,
                            env=env, cwd=ROOT, close_fds=True)
    os.close(slave)
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)
    chunks = []
    t0 = time.monotonic()
    armed = False
    try:
        while time.monotonic() - t0 < timeout:
            r, _, _ = select.select([master], [], [],
                                  idle / warp if armed else 0.5)
            if not r and armed:
                break
            if r:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(((time.monotonic() - t0) * warp, data))
                stream.feed(data)
                if stop and stop(screen):
                    if idle is None:
                        break
                    armed = True
            elif proc.poll() is not None:
                break
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.kill()
        proc.wait()
    return chunks


def text_of(screen):
    return "\n".join(screen.display)


def has(*needles):
    """stop() predicate: every needle is somewhere on the screen."""
    return lambda screen: all(n in text_of(screen) for n in needles)


# --------------------------------------------------------------------------
# Drawing cells
# --------------------------------------------------------------------------

_font = None
_glyphs = {}
_blocks = {}


def _glyph(ch):
    g = _glyphs.get(ch)
    if g is None:
        global _font
        if _font is None:
            _font = ImageFont.truetype(FONT, 16)
        im = Image.new("1", (CW, CH), 0)
        d = ImageDraw.Draw(im)
        d.fontmode = "1"
        d.text((0, 0), ch, font=_font, fill=1)
        g = _glyphs[ch] = im
    return g


def _block(ch, fg, bg):
    key = (ch, fg, bg)
    b = _blocks.get(key)
    if b is None:
        b = Image.new("P", (CW, CH), bg)
        if ch.strip():
            b.paste(fg, (0, 0), _glyph(ch))
        _blocks[key] = b
    return b


def _nearest(hexcol):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
    return min(range(16), key=lambda i: sum((a - c) ** 2
                                            for a, c in zip(RGB[i], (r, g, b))))


def colour(name, bold, default):
    """pyte colour name (+ bold) -> palette index."""
    if name == "default":
        idx = default
    elif name.startswith("bright") and name[6:] in BASE:
        idx = BASE[name[6:]] + 8
    elif name in BASE:
        idx = BASE[name]
    elif len(name) == 6:
        try:
            return _nearest(name)
        except ValueError:
            idx = default
    else:
        idx = default
    if bold and idx < 8:
        idx += 8
    return idx


def cell_colours(c):
    fg = colour(c.fg, c.bold, 7)
    bg = colour(c.bg, False, 0)
    if c.reverse:
        fg, bg = bg, fg
    return fg, bg


def palette_image(w, h):
    im = Image.new("P", (w, h), 0)
    flat = []
    for r, g, b in RGB:
        flat += [r, g, b]
    im.putpalette(flat + [0] * (768 - len(flat)))
    return im


def snapshot(screen):
    """Immutable copy of the screen, cheap to compare."""
    return tuple(tuple(screen.buffer[y][x] for x in range(COLS))
                 for y in range(ROWS))


def draw(snap, rows=None):
    """Render a snapshot to a P-mode image (8x16 cells, VGA palette)."""
    first, last = rows or (0, ROWS)
    im = palette_image(COLS * CW, (last - first) * CH)
    for y in range(first, last):
        for x in range(COLS):
            c = snap[y][x]
            fg, bg = cell_colours(c)
            im.paste(_block(c.data, fg, bg), (x * CW, (y - first) * CH))
    return im


def snap_text(snap):
    return "\n".join("".join(c.data for c in row) for row in snap)


# --------------------------------------------------------------------------
# Replaying captured output
# --------------------------------------------------------------------------

def replay(chunks, dt):
    """Yield (tick_time, snapshot) every dt simulated seconds."""
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)
    i, n = 0, len(chunks)
    if not n:
        return
    end = chunks[-1][0]
    k = 0
    while k * dt <= end + dt:
        t = k * dt
        while i < n and chunks[i][0] <= t:
            stream.feed(chunks[i][1])
            i += 1
        yield t, snapshot(screen)
        k += 1


def frames(chunks, dt, start=None, end=None, hold=2.0, cap=2.5):
    """Sample the screen, drop duplicates, return [(snapshot, seconds)].

    start/end are texts: the window opens when `start` is on screen (from the
    beginning if None) and closes `hold` seconds after `end` appears. A frame
    that stays put is shown for at most `cap` seconds.
    """
    out = []
    opened = start is None
    closing = None
    for t, snap in replay(chunks, dt):
        txt = None
        if not opened:
            txt = snap_text(snap)
            if start in txt:
                opened = True
        if not opened:
            continue
        if closing is None and end is not None:
            if txt is None:
                txt = snap_text(snap)
            if end in txt:
                closing = t + hold
        if out and out[-1][0] == snap:
            out[-1][1] += dt
        else:
            out.append([snap, dt])
        if closing is not None and t >= closing:
            break
    return [(s, min(d, cap)) for s, d in out]


def write_gif(path, frs, last_hold=3.0):
    imgs = [draw(s) for s, _ in frs]
    # GIF delays are whole centiseconds
    durs = [max(2, int(round(d * 100))) * 10 for _, d in frs]
    durs[-1] = max(durs[-1], int(last_hold * 1000))
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=durs,
                 loop=0, optimize=False, disposal=1)


def write_png(path, snap, rows=None):
    draw(snap, rows).save(path, optimize=True)


# --------------------------------------------------------------------------
# What to render
# --------------------------------------------------------------------------

def first_match(chunks, needles, extra=0):
    """Screen at the very first byte where every needle is on screen
    (plus `extra` more characters, to finish a line that has just started).

    Feeding byte by byte makes this independent of how the pty happened to
    split the output into reads.
    """
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.Stream(screen)
    check = has(*needles)
    ends = {n[-1] for n in needles}
    left = None
    for _, data in chunks:
        for ch in data.decode("utf-8", "replace"):
            stream.feed(ch)
            if left is None and ch in ends and check(screen):
                left = extra
            elif left:
                left -= 1
            if left == 0:
                return screen
    return None


def last_screen(chunks):
    screen = pyte.Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)
    for _, data in chunks:
        stream.feed(data)
    return screen


def shot_png(name, seed, style, needles, rows=None, warp=30, idle=3.0,
             exact=False, extra=0):
    """PNG of the screen once `needles` are all on screen.

    exact=True snapshots at the first byte where they all show; otherwise the
    snapshot waits until the screen has finished painting (line goes quiet).
    """
    def job(out):
        chunks = capture(seed, style, warp, stop=has(*needles),
                         idle=None if exact else idle)
        screen = first_match(chunks, needles, extra) if exact else last_screen(chunks)
        if screen is None or not has(*needles)(screen):
            raise SystemExit(f"{name}: {needles!r} never appeared")
        write_png(os.path.join(out, name + ".png"), snapshot(screen), rows)
    return job


def shot_gif(name, seed, style, start=None, end=None, stop=None, dt=0.15,
             warp=5, hold=2.0, cap=2.5):
    """Animated GIF: the screen sampled every `dt` simulated seconds.

    The window opens when text `start` is on screen (default: the first
    frame) and closes `hold` seconds after `end` shows up. `stop` ends the
    capture early: once that text is up and the line has been quiet for
    `hold` seconds, the run is cut off.
    """
    def job(out):
        chunks = capture(seed, style, warp, stop=stop and has(stop),
                         idle=hold if stop else None)
        frs = frames(chunks, dt, start, end, hold, cap)
        if len(frs) < 2:
            raise SystemExit(f"{name}: fewer than 2 frames")
        write_gif(os.path.join(out, name + ".gif"), frs)
    return job


# PNGs run at a high --warp: only the content matters there, and the status
# bar's wall-clock "Connected" timer then stays at 00:00:00 or 01.
FAST = 200

JOBS = {}


def register(name, job):
    JOBS[name] = job


register("dialin", shot_gif("dialin", 3, "renegade", end="Command \u00bb",
                            stop="Command \u00bb", hold=0.3))
register("browse", shot_gif("browse", 5, "telegard", start="G-FILES",
                            end="Page 1 of", stop="Page 1 of", hold=6.0))
register("goodbye", shot_gif("goodbye", 5, "pcboard", start="Log off now?",
                             end="NO CARRIER", hold=3.0))
register("renegade", shot_png("renegade", 1, "renegade",
                              ["[Main]", "Command \u00bb"], warp=FAST, exact=True))
register("telegard", shot_png("telegard", 1, "telegard",
                              ["[Main Menu]", "Time Left"], warp=FAST, exact=True))
register("mystic", shot_png("mystic", 1, "mystic", ["(Main) ->"],
                            warp=FAST, exact=True))
register("pcboard", shot_png("pcboard", 1, "pcboard",
                             ["Main Board Command?"], warp=FAST, exact=True))
register("logo", shot_png("logo", 3, "renegade", ["Enter your handle or NEW:"],
                          warp=FAST, exact=True))
register("art", shot_png("art", 3, "mystic", ["Joined file area", "FILE AREAS"],
                         warp=FAST, exact=True, extra=30))
register("gfiles", shot_png("gfiles", 22, "telegard", ["Page 1 of", "BOXCOLRS"],
                            warp=60))
register("statusbar", shot_png("statusbar", 1, "telegard",
                               ["[Main Menu]", "Time Left"], rows=(22, 26),
                               warp=FAST, exact=True))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--only", help="render just this one (e.g. mystic)")
    a = ap.parse_args(argv)
    if a.only and a.only not in JOBS:
        ap.error("unknown name %r; choose from: %s" % (a.only, ", ".join(JOBS)))
    os.makedirs(a.out, exist_ok=True)
    for name, job in JOBS.items():
        if a.only and name != a.only:
            continue
        print("rendering", name, flush=True)
        job(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
