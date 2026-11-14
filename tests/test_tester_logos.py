"""Tester checks for the logo engine (courierhst/logos.py) and its call sites."""
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import io
import tempfile
import unittest

from courierhst import ansi, bbs, content, logos

SUPPORTED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -!.'"
TEXTS = ["", "A", SUPPORTED, "THE ELITE CONNECTION", "X" * 25,
         "Bad Wolf Digital Fortress"[:25], "LaTer", "@#", "Q" * 200,
         "a b c d e f g h i j k l m n o p q r s t u v w x y z"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESC_RE = re.compile(r"\x1b\[[0-9;]*m")
LINEART_CHARS = set("/\\_|-.'` ")


def plain_ansi(line):
    """What a terminal shows for `line` after pipe_to_ansi."""
    return ESC_RE.sub("", ansi.pipe_to_ansi(line))


class Contract(unittest.TestCase):
    def test_styles_tuple(self):
        self.assertEqual(logos.STYLES, ("block", "chunky", "dither", "lineart"))

    def test_every_style_palette_text(self):
        for style in logos.STYLES:
            for pal in ansi.PALETTES:
                for text in TEXTS:
                    for mr in (12, 4, 1):
                        with self.subTest(style=style, pal=pal, text=text[:30], mr=mr):
                            out = logos.render(text, pal, style, 78, mr)
                            self.assertIsInstance(out, list)
                            self.assertTrue(out)
                            self.assertLessEqual(len(out), mr)
                            for ln in out:
                                self.assertIsInstance(ln, str)
                                self.assertLessEqual(ansi.vlen(ln), 79)
                                self.assertLessEqual(len(plain_ansi(ln)), 79)

    def test_unknown_palette_and_style(self):
        for kw in ({"palette": "nope"}, {"style": "nope"},
                   {"palette": "nope", "style": "nope"}):
            with self.subTest(**kw):
                out = logos.render("HELLO", **kw)
                self.assertTrue(out)
                self.assertTrue(all(ansi.vlen(ln) <= 79 for ln in out))

    def test_odd_strings(self):
        for text in ("@#", "\t\n", "ÆØÅ ☃", "|15||", "   ", "-", "'", "!!!"):
            for style in logos.STYLES:
                with self.subTest(text=text, style=style):
                    out = logos.render(text, "cyan", style)
                    self.assertTrue(out)
                    for ln in out:
                        ansi.pipe_to_ansi(ln)

    def test_narrow_width(self):
        for style in logos.STYLES:
            for w in (78, 40, 20):
                with self.subTest(style=style, width=w):
                    out = logos.render("ELITE BOARD", "fire", style, w, 12)
                    self.assertTrue(out)
                    self.assertTrue(all(ansi.vlen(ln) <= 79 for ln in out))


class Block(unittest.TestCase):
    def test_block_identical(self):
        for pal in ansi.PALETTES:
            for text in ("A", "THE ELITE CONNECTION", "X" * 25, "LATER",
                         "ACID PHREAK"):
                with self.subTest(pal=pal, text=text):
                    self.assertEqual(logos.render(text, pal, "block"),
                                     ansi.logo(text, pal, 78))


class Chunky(unittest.TestCase):
    def test_four_rows_per_line(self):
        out = logos.render("ACID", "cyan", "chunky")
        self.assertEqual(len(out), 4)
        out = logos.render("THE ELITE CONNECTION", "cyan", "chunky")
        self.assertEqual(len(out) % 4, 0)
        self.assertGreater(len(out), 4)

    def test_blocks_and_shadow(self):
        out = logos.render("ACID", "cyan", "chunky")
        vis = "".join(ansi.strip(ln) for ln in out)
        self.assertTrue(set(vis) & set("▀▄█"))
        self.assertTrue(set(vis) <= set("▀▄█ "), set(vis))
        self.assertIn("|08", "".join(out))
        # last row holds only the shadow's bottom edge
        self.assertIn("|08", out[-1])

    def test_not_block_font(self):
        self.assertNotEqual(logos.render("ACID", "cyan", "chunky"),
                            ansi.logo("ACID", "cyan", 78))


class Dither(unittest.TestCase):
    def test_shades_and_solid_top(self):
        out = logos.render("SHADOWMIRE", "toxic", "dither")
        vis = [ansi.strip(ln) for ln in out]
        self.assertTrue(set("".join(vis)) & set("░▒▓"))
        self.assertTrue(set(vis[0]) & set("▀▄█"), vis[0])
        self.assertFalse(set(vis[0]) & set("░▒▓"), vis[0])
        self.assertIn("|08|16░", "".join(out))

    def test_darker_lower(self):
        vis = [ansi.strip(ln) for ln in logos.render("HOME", "cyan", "dither")]
        rows_with = {ch: [i for i, r in enumerate(vis) if ch in r] for ch in "▓▒"}
        self.assertTrue(rows_with["▓"] and rows_with["▒"])
        self.assertLess(min(rows_with["▓"]), min(rows_with["▒"]))


class Lineart(unittest.TestCase):
    def test_charset(self):
        # SUPPORTED split into words short enough for line-art (the full
        # 36-glyph run is too wide and correctly falls back to block)
        for text in ("ABCDEFGHIJKLM", "NOPQRSTUVWXYZ", "0123456789 -!.'",
                     "STARLANE", "THE ELITE CONNECTION"):
            out = logos.render(text, "ice", "lineart")
            self.assertTrue(out)
            for ln in out:
                self.assertTrue(set(ansi.strip(ln)) <= LINEART_CHARS,
                                set(ansi.strip(ln)) - LINEART_CHARS)

    def test_pipes_escaped(self):
        out = logos.render("HI", "ice", "lineart")
        joined = "".join(out)
        self.assertIn("||", joined)
        for ln in out:
            vis = ansi.strip(ln)
            # every visible pipe came from an escaped "||" in the source
            self.assertEqual(vis.count("|"), ln.count("||"))
            # and the terminal shows the same thing ansi.strip computes
            self.assertEqual(plain_ansi(ln), vis)
        self.assertIn("|", "".join(ansi.strip(ln) for ln in out))

    def test_height(self):
        self.assertIn(len(logos.render("STARLANE", "ice", "lineart")), (4, 5))

    def test_gradient(self):
        out = logos.render("STARLANE", "ice", "lineart")
        codes = set(re.findall(r"\|(0\d|1[0-5])(?!\d)", "".join(
            ln.replace("||", "") for ln in out)))
        self.assertGreaterEqual(len(codes - {"07"}), 3, codes)


class Distinct(unittest.TestCase):
    def test_styles_differ(self):
        outs = {s: tuple(logos.render("SHADOWMIRE", "toxic", s)) for s in logos.STYLES}
        self.assertEqual(len(set(outs.values())), 4)

    def test_doors_call(self):
        with open(os.path.join(ROOT, "courierhst", "doors.py")) as f:
            src = f.read()
        self.assertIn('logos.render("SHADOWMIRE", "toxic", "dither")', src)
        self.assertIn('logos.render("STARLANE", "ice", "lineart")', src)


# ---------------------------------------------------------------- seed stability
DUMP = r"""
import json, random, sys
from courierhst import bbs
res = {}
for seed in range(1, 61):
    rng = random.Random(seed)
    b = bbs.Board(rng, "Tester")
    d = {k: repr(v) for k, v in vars(b).items() if k not in ("rng", "started", "logo_style")}
    d["__next__"] = rng.choice(("block", "chunky", "dither", "lineart"))
    d["__style__"] = getattr(b, "logo_style", None)
    res[seed] = d
json.dump(res, sys.stdout)
"""


@unittest.skipIf(shutil.which("git") is None, "git not available")
class SeedStability(unittest.TestCase):
    def dump(self, path):
        r = subprocess.run([sys.executable, "-c", DUMP], cwd=path,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        return json.loads(r.stdout)

    def test_fields_unchanged_and_logo_style_last(self):
        tar = subprocess.run(["git", "archive", "14901e8", "courierhst"], cwd=ROOT,
                             capture_output=True, timeout=60)
        if tar.returncode != 0:
            self.skipTest("base commit 14901e8 not available")
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as tf:
                try:
                    tf.extractall(tmp, filter="data")
                except TypeError:
                    tf.extractall(tmp)
            old = self.dump(tmp)
        new = self.dump(ROOT)
        for seed in old:
            o, n = old[seed], new[seed]
            with self.subTest(seed=seed):
                self.assertIsNone(o["__style__"])
                self.assertEqual({k: v for k, v in o.items() if not k.startswith("__")},
                                 {k: v for k, v in n.items() if not k.startswith("__")})
                # logo_style is exactly the next draw after the old constructor
                self.assertEqual(n["__style__"], o["__next__"])

    def test_board_logo_method(self):
        b = bbs.Board(random.Random(7), "Tester")
        self.assertIn(b.logo_style, logos.STYLES)
        self.assertEqual(b.logo("HELLO"),
                         logos.render("HELLO", b.palette, b.logo_style, 78, 12))
        self.assertEqual(b.logo("HELLO", 60, 4),
                         logos.render("HELLO", b.palette, b.logo_style, 60, 4))


# ---------------------------------------------------------------- screen fit
class Capture:
    def __init__(self):
        self.parts = []
        self.online_since = None
        self.status_name = ""
        self.connect_speed = ""
        self.offline_msg = ""
        self.dialing = False

    def send(self, s):
        self.parts.append(s)

    def sendln(self, s=""):
        self.parts.append(s + "\n")

    local = send

    def type(self, s, fast=False):
        self.parts.append(s)

    def type_hidden(self, s):
        self.parts.append("*" * len(s))

    def enter(self):
        self.parts.append("\n")

    def pause(self, *a):
        pass

    rpause = pause

    def cls_local(self):
        pass


def after_cls(cap):
    t = "".join(cap.parts)
    return t[t.rfind("\x0c") + 1:]


class ScreenFit(unittest.TestCase):
    """24-row window: CLS homes the cursor on row 1, so at most 23 newlines."""

    def check_lines(self, text):
        for ln in text.split("\n"):
            self.assertLessEqual(len(ansi.strip(ESC_RE.sub("", ln))), 79)

    def test_splash(self):
        seen = set()
        for seed in range(1, 201):
            for style in ("renegade", "telegard", "mystic", "pcboard"):
                cap = Capture()
                s = bbs.Session(cap, random.Random(seed), "Tester",
                                xfer_speedup=1e9, style=style)
                seen.add(s.b.logo_style)
                s.splash()
                t = after_cls(cap)
                with self.subTest(seed=seed, style=style, logo=s.b.logo_style):
                    self.assertLessEqual(t.count("\n"), 23)
                    self.check_lines(t)
                    self.assertIn(f"Sysop {s.b.sysop}", ansi.strip(t))
        self.assertEqual(seen, set(logos.STYLES))

    def test_worst_case_logo(self):
        # the tallest logo any style can produce at max_rows=12, on each splash
        for logo_style in logos.STYLES:
            for style in ("renegade", "pcboard"):
                cap = Capture()
                s = bbs.Session(cap, random.Random(3), "Tester",
                                xfer_speedup=1e9, style=style)
                s.b.logo_style = logo_style
                s.b.name = "THE ELITE CONNECTION OF DOOM AND GLOOM"
                s.splash()
                with self.subTest(logo=logo_style, style=style):
                    self.assertLessEqual(after_cls(cap).count("\n"), 23)

    def test_bye(self):
        for seed in range(1, 101):
            for logo_style in logos.STYLES:
                cap = Capture()
                s = bbs.Session(cap, random.Random(seed), "Tester", xfer_speedup=1e9)
                s.b.logo_style = logo_style
                s.do_bye()
                t = after_cls(cap)
                with self.subTest(seed=seed, logo=logo_style):
                    self.assertIn("NO CARRIER", t)
                    self.assertLessEqual(t.count("\n"), 23)


if __name__ == "__main__":
    unittest.main()
