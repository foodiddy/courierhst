"""Tester acceptance checks for the screen-chrome restyle (task mwfw3g6pskm2u2).

Complements test_ansi / test_modem / test_restyle_pty with independent checks:
helper widths for hostile inputs, the status bar rendered through a VT
emulator, PCBoard staying as it was on main, --board-style CLI handling, and
pty runs at extra sizes and with --no-center / --no-status.
"""
from concurrent.futures import ThreadPoolExecutor
import io
import os
import random
import re
import subprocess
import sys
import time
import unittest

try:
    import pyte
except ImportError:  # pragma: no cover
    pyte = None

from courierhst import ansi, bbs, content
from courierhst.modem import Line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDS_PYTE = unittest.skipIf(pyte is None,
                             "pyte not installed (pip install '.[test]')")
LONG = "Ridiculously Long Name Of Elite Doom " * 6
STYLES = ["renegade", "telegard", "mystic", "pcboard"]


class FakeOut(io.StringIO):
    def fileno(self):
        raise OSError("not a tty")


# ---------------------------------------------------------------- helpers
class HelperWidths(unittest.TestCase):
    def assertFits(self, lines, width=79):
        if isinstance(lines, str):
            lines = [lines]
        for ln in lines:
            self.assertLessEqual(ansi.vlen(ln), width, repr(ansi.strip(ln)))

    def test_frame_table_long_and_many_columns(self):
        cols = [("a" * 40, 30, 13), ("b" * 40, 30, 15), ("c" * 40, 30, 11)]
        rows = [[LONG, LONG, [LONG, LONG]], ["x"], []]
        self.assertFits(ansi.frame_table(cols, rows))
        self.assertFits(ansi.frame_table(cols, rows, indent=0, maxw=79))

    def test_frame_table_rows_line_up(self):
        cols = [("handle", 16, 13), ("group", 13, 14), ("time", 5, 10)]
        out = ansi.frame_table(cols, [["x", LONG, "12:00"], ["y", "z", [LONG, "q"]]])
        widths = {ansi.vlen(ln) for ln in out}
        self.assertEqual(len(widths), 1, [ansi.strip(l) for l in out])
        plain = [ansi.strip(l) for l in out]
        self.assertTrue(plain[0].lstrip().startswith("┌"))
        self.assertTrue(plain[2].lstrip().startswith("├"))
        self.assertTrue(plain[-1].lstrip().startswith("└"))
        self.assertIn("│", plain[1])

    def test_numbered_item_ends_at_78(self):
        for n in (1, 9, 10, 99):
            for name in ("", "X", LONG, "Doors"):
                for desc in ("", "d", LONG, "12 files"):
                    s = ansi.numbered_item(n, name, desc)
                    self.assertLessEqual(ansi.vlen(s), 78, (n, name, desc))
                    if desc:
                        self.assertEqual(ansi.vlen(s), 78, (n, name, desc))
        s = ansi.numbered_item(1, "Name", "a description")
        self.assertEqual(ansi.vlen(s), 78)
        self.assertTrue(ansi.strip(s).endswith("a description"))
        self.assertIn("|06(", s)
        self.assertIn("|1401", s)
        self.assertIn("|10a description", s)

    def test_section_header(self):
        s = ansi.section_header(LONG)
        self.assertFits(s)
        self.assertRegex(ansi.strip(ansi.section_header("ORIGINAL GAMES")),
                         r"^\s*:: ORIGINAL GAMES ::$")
        self.assertIn("|13::", s)

    def test_key_hints(self):
        pairs = [(c, LONG[:12]) for c in "ABCDEFGHIJKLMN"]
        self.assertFits(ansi.key_hints(pairs))
        s = ansi.key_hints([("N", "Next"), ("Q", "Quit")])
        self.assertIn("|12(N)", s)
        self.assertIn("|10Next", s)
        self.assertEqual(ansi.strip(s).strip(), "(N) Next  (Q) Quit")

    def test_corner_info(self):
        out = ansi.corner_info([LONG, "|14CRiMSON TiDE |07World HQ"],
                               [LONG, "|10 3.2|07 gigs online", "x"])
        self.assertEqual(len(out), 3)
        self.assertFits(out)
        self.assertTrue(ansi.strip(out[1]).startswith("CRiMSON TiDE World HQ"))
        self.assertTrue(ansi.strip(out[1]).rstrip().endswith("gigs online"))

    def test_diz_block_45(self):
        for short in (False, True):
            out = ansi.diz_block(LONG, LONG, LONG, 1, 5, LONG, LONG, LONG, LONG,
                                 width=80, short=short)
            self.assertFits(out, 45)
        out = ansi.diz_block("CRiMSON TiDE", "Game", "Pub", 1, 5, "VGA Strategy",
                             "Sup", "Crk", "Doc check removed")
        plain = [ansi.strip(l) for l in out]
        self.assertIn("─┤ CRiMSON TiDE ├─", plain[0])
        self.assertEqual(plain[1], "Game (c) Pub")
        self.assertEqual(plain[2], "[01/05]  VGA Strategy")
        self.assertIn("Supplied by Sup", "\n".join(plain))
        self.assertIn("Cracked by Crk", "\n".join(plain))

    def test_updated_banner(self):
        out = ansi.updated_banner("11/13/93")
        self.assertFits(out)
        self.assertIn("UPDATED> 11/13/93", ansi.strip(out[0]))
        self.assertIn("|12", out[0])
        self.assertIn("|14", out[0])

    def test_nfo_page(self):
        fields = [(k, LONG) for k in ("Release", "Supplier", "Cracker",
                                       "Protection", "Disks", "Date")]
        out = ansi.nfo_page(LONG, fields, [LONG] * 6)
        self.assertFits(out)
        txt = "\n".join(ansi.strip(l) for l in out)
        for k in ("release", "supplier", "cracker", "protection", "disks", "date"):
            self.assertIn(k, txt.lower())
        self.assertIn("greets", txt)

    def test_art_tag(self):
        r = random.Random(7)
        for _ in range(300):
            h, g = content.handle(r), r.choice(content.ART_GROUPS)
            tag = ansi.art_tag(h, g)
            self.assertTrue(tag.startswith("|08"))
            plain = ansi.strip(tag)
            self.assertRegex(plain, r"^[a-z0-9]{2,4}$", (h, g))
            self.assertEqual(tag, ansi.art_tag(h, g))
        for h in ("", "x", "1337", "!!"):
            self.assertRegex(ansi.strip(ansi.art_tag(h)), r"^[a-z0-9]{2,4}$")


# ---------------------------------------------------------------- status bar
@NEEDS_PYTE
class StatusBarRendered(unittest.TestCase):
    """Feed _draw_status output into pyte and inspect the actual cells."""

    def render(self, cols, name, state):
        line = Line(noise=0, out=FakeOut())
        line.cols, line.rows = cols, 30
        line.left = max(0, (cols - 80) // 2)
        line.status_row = 27
        line.status_name = name
        line.online_since = time.monotonic() - 21 if state == "online" else None
        line.dialing = state == "dialing"
        line._buf.clear()
        line._draw_status(force=True)
        screen = pyte.Screen(cols, 30)
        pyte.Stream(screen).feed("".join(line._buf))
        row = screen.buffer[26]
        text = "".join(row[x].data for x in range(cols))
        used = [x for x in range(cols) if row[x].bg != "default"]
        return line, row, text, used

    def test_matrix(self):
        for cols in (20, 40, 60, 79, 80, 81, 100, 120, 200):
            for name in ("", "Nite Owl", LONG, "Pipe|Board"):
                for state in ("online", "dialing", "offline"):
                    with self.subTest(cols=cols, name=name, state=state):
                        line, row, text, used = self.render(cols, name, state)
                        width = min(80, cols) - 1
                        self.assertTrue(used, text)
                        self.assertEqual(used[0], line.left)
                        self.assertEqual(len(used), width, text)
                        self.assertEqual(used[-1], line.left + width - 1)
                        for x in used:
                            self.assertEqual(row[x].bg, "blue", (x, text))
                        for x in used:
                            if row[x].data.strip():
                                self.assertEqual(row[x].fg, "white", (x, text))
                        # nothing past the bar
                        self.assertEqual(text[line.left + width:].strip(), "")
                        if cols >= 80 and state == "online":
                            self.assertIn("14400/ARQ/HST", text)
                            self.assertIn("Connected: 00:00:2", text)
                            self.assertIn("ALT-Z for menu", text)
                            self.assertNotIn("Telnet", text)
                        if cols >= 80 and state == "dialing":
                            self.assertIn(" Dialing ", text)
                            self.assertIn("... | ALT-Z for menu", text)
                        if state == "offline":
                            self.assertTrue(text[line.left:].startswith(" Offline | ALT-Z"))

    def test_online_short_name_exact(self):
        _, _, text, _ = self.render(80, "Nite Owl", "online")
        self.assertRegex(text.rstrip(),
                         r"^ Nite Owl \| 14400/ARQ/HST \| Connected: 00:00:2\d \| ALT-Z for menu$")

    def test_connected_counts_up(self):
        line = Line(noise=0, out=FakeOut())
        line.cols, line.rows, line.left, line.status_row = 80, 30, 0, 27
        line.status_name = "B"
        line.online_since = time.monotonic() - 3725
        line._buf.clear()
        line._draw_status(force=True)
        self.assertIn("Connected: 01:02:05", ansi.strip("".join(line._buf)))


# ---------------------------------------------------------------- boards
class Capture:
    """Minimal stand-in for Line that records everything sent."""

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

    def local(self, s):
        self.parts.append(s)

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

    def text(self):
        return ansi.strip("".join(self.parts))


def session(style, seed=1):
    cap = Capture()
    s = bbs.Session(cap, random.Random(seed), "Tester", xfer_speedup=1e9,
                    style=style)
    return s, cap


class Boards(unittest.TestCase):
    def test_style_weights(self):
        w = {s: bbs.Board.STYLES.count(s) for s in set(bbs.Board.STYLES)}
        self.assertEqual(w, {"renegade": 2, "telegard": 1, "mystic": 2, "pcboard": 1})

    def test_mystic_software_and_prompt(self):
        s, _ = session("mystic")
        self.assertEqual(s.b.software, "Mystic BBS v1.07")
        self.assertEqual(ansi.strip(bbs.prompt(s.b)), "::: (Main) -> ")

    def test_renegade_prompt_kept(self):
        s, _ = session("renegade")
        self.assertRegex(ansi.strip(bbs.prompt(s.b)),
                         r"^\[\d\d:\d\d\] \[Main\] \(Tl:\d+\) Command » $")

    def test_style_forced_for_every_board(self):
        for st in STYLES:
            for seed in range(20):
                self.assertEqual(session(st, seed)[0].b.style, st)

    def test_splash_no_ansi_by_and_has_corners(self):
        for st in ("renegade", "telegard", "mystic"):
            for seed in range(10):
                s, cap = session(st, seed)
                s.splash()
                txt = cap.text()
                self.assertNotIn("ansi by", txt)
                self.assertIn(s.b.affils[0], txt)
                self.assertIn("gigs online", txt)
                self.assertIn(ansi.strip(s.b.art_tag), txt)

    def test_pcboard_splash_unchanged_from_main(self):
        """Spec: PCBoard screens stay as they are on main (only the global
        status bar changes).  main's splash has the centred node/gigs/modem
        tag, the World HQ / Dist line and the 'ansi by x/y' credit."""
        for seed in range(5):
            s, cap = session("pcboard", seed)
            s.splash()
            txt = cap.text()
            with self.subTest(seed=seed):
                self.assertIn(ansi.strip(ansi.elite("World HQ")) + ": "
                              + s.b.affils[0], txt)
                self.assertIn("ansi by " + s.b.art_by[0].lower(), txt)
                self.assertNotIn("gigs online", txt)

    def test_pcboard_splash_source_matches_main(self):
        """The PCBoard splash body must be byte-identical to main's splash()."""
        try:
            main_src = subprocess.run(
                ["git", "show", "e7b83f9:courierhst/bbs.py"], cwd=ROOT,
                capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("main revision e7b83f9 not available")
        import inspect

        def body(src, name):
            m = re.search(r"^    def %s\(self\):\n(.*?)(?=^    def |^class |\Z)" % name,
                          src, re.S | re.M)
            self.assertIsNotNone(m, name)
            return m.group(1).rstrip()
        here = inspect.getsource(bbs)
        # Task mwfxj435bxgw2e intentionally changed only the "ansi by" credit
        # line (now right-aligned via _ansi_credit); everything else must match.
        old_credit = ("        art.append(f\"|08{' ' * 55}ansi by {b.art_by[0].lower()}"
                      "/{b.art_by[1].lower()}\")")
        new_credit = '        art.append("|08" + self._ansi_credit())'
        old_body = body(main_src, "splash")
        self.assertIn(old_credit, old_body)
        self.assertEqual(body(here, "splash_pcb"),
                         old_body.replace(old_credit, new_credit))

    def test_framed_file_list_shows_full_filenames_and_headers(self):
        """Filenames must not be cut by the framed column (art-pack names
        such as NOiR-1893.ZIP are 13 chars), and column titles must be whole."""
        for st in ("renegade", "telegard"):
            for seed in range(40):
                s, cap = session(st, seed)
                seen = []
                orig = s._entries

                def spy(kind, _orig=orig):
                    e = _orig(kind)
                    seen.extend(x[0] for x in e)
                    return e
                s._entries = spy
                s.file_list("art")
                s.file_list("fresh")
                txt = cap.text()
                with self.subTest(style=st, seed=seed):
                    for fn in seen:
                        self.assertIn(fn, txt)
                    hdr = next(l for l in txt.splitlines() if "filename" in l)
                    titles = [t.strip() for t in hdr.strip().strip("│").split("│")]
                    self.assertIn("size/date", titles + [hdr])

    def test_selection_prompt_answer_inside_brackets(self):
        for st in ("renegade", "telegard"):
            s, cap = session(st)
            s.select("12", width=3)
            raw = "".join(cap.parts)
            self.assertIn("What is your selection?", ansi.strip(raw))
            m = re.search(r"\[(   )\|06\]\x1b\[(\d+)D", raw)
            self.assertTrue(m, repr(raw))
            self.assertEqual(int(m.group(2)), 4)  # back over "   ]" to the slot
        s, cap = session("mystic")
        s.select("3", "Files")
        self.assertIn("::: (Files) -> 3", cap.text())

    def test_mystic_mail_scan(self):
        for has in (True, False):
            s, cap = session("mystic")
            s.mail_scan(has)
            txt = cap.text()
            self.assertRegex(txt, r">> There are [\d,]+ messages on this system "
                                  r"\(\d+ are new messages\)\.")
            self.assertIn(">> You have", txt)
            for ln in txt.splitlines():
                self.assertLessEqual(len(ln), 79)

    def test_mystic_forum_list(self):
        s, cap = session("mystic", 4)
        bases = content.MSG_BASES[:6]
        s.mystic_forums(bases, [(100 * i, i % 2) for i in range(6)])
        txt = cap.text()
        self.assertRegex(txt, r"BASE\s+NETWORK\s+TOTAL\s+NEW\s+YOURS")
        self.assertRegex(txt, r"(local|fido|scene|warez) ─{5,}")
        self.assertIn("NEW MESSAGES   PERSONAL   EMAIL   ALL   LIST   QUIT", txt)
        self.assertIn("[MESSAGE FORUMS] Select forum, type to search, or CTRL-Z for help.", txt)
        self.assertIn("|00|18[MESSAGE FORUMS]", "".join(cap.parts))
        for ln in txt.splitlines():
            self.assertLessEqual(len(ln), 79, ln)

    def test_file_lists_fit_and_frame(self):
        for st in ("renegade", "telegard", "mystic"):
            for seed in range(15):
                s, cap = session(st, seed)
                for kind in [k for _, k in content.FILE_AREAS]:
                    try:
                        s.file_list(kind)
                    except (KeyError, ValueError, IndexError):
                        continue
                txt = cap.text()
                with self.subTest(style=st, seed=seed):
                    for ln in txt.splitlines():
                        self.assertLessEqual(len(ln), 79, ln)
                    self.assertIn("UPDATED>" if st != "mystic" else ">>", txt)
                    if st != "mystic":
                        self.assertIn("┌", txt)
                        self.assertIn("filename", txt)


# ---------------------------------------------------------------- CLI
class Cli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONPATH=ROOT)
        return subprocess.run([sys.executable, "-m", "courierhst", *args],
                              capture_output=True, text=True, env=env, cwd=ROOT,
                              timeout=30)

    def test_bad_board_style_rejected(self):
        p = self.run_cli("--board-style", "wildcat")
        self.assertEqual(p.returncode, 2)
        self.assertIn("invalid choice", p.stderr)

    def test_help_lists_board_style(self):
        p = self.run_cli("--help")
        self.assertIn("--board-style", p.stdout)
        for st in STYLES:
            self.assertIn(st, p.stdout)

    def test_readme_documents_flag(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.assertIn("--board-style", f.read())


# ---------------------------------------------------------------- pty
@NEEDS_PYTE
class ExtraPty(unittest.TestCase):
    """More sizes/seeds, plus --no-center and --no-status, for every style."""

    def one(self, style, seed, cols, rows, center=True, status=True):
        from tests.test_session_pty import run_session
        want = 25 + (1 if status else 0)
        left = max(0, (cols - 80) // 2) if center else 0
        top = max(0, (rows - want) // 2) + 1 if center else 1
        avail = rows - top + 1 - (1 if status else 0)
        bottom = top + max(3, min(25, avail)) - 1
        srow = bottom + 1
        width = min(80, cols) - 1
        seen = {"bar": False, "sel": False, "colons": False, "arrows": False}

        def check(screen):
            for y in range(rows):
                line = screen.buffer[y]
                for x in range(cols):
                    if line[x].data.strip() == "":
                        continue
                    in_win = top - 1 <= y <= bottom - 1 and left <= x < left + 80
                    in_bar = status and y == srow - 1 and left <= x < left + width
                    if not (in_win or in_bar):
                        raise AssertionError(
                            f"glyph outside window x={x} y={y} {line[x].data!r}")
                    if in_win and x >= left + 80:
                        raise AssertionError("glyph at col >= 80")
            if status:
                r = screen.buffer[srow - 1]
                t = "".join(r[x].data for x in range(cols))
                if "ALT-Z for menu" in t:
                    seen["bar"] = True
                    for x in range(left, left + width):
                        if r[x].bg != "blue":
                            raise AssertionError(f"status cell {x} bg {r[x].bg}")
            for y in range(top - 1, bottom):
                t = "".join(screen.buffer[y][x].data for x in range(cols))
                if re.search(r"What is your selection\? \[\s*\S+\s*\]", t):
                    seen["sel"] = True
                if ":::" in t:
                    seen["colons"] = True
                if ">>" in t:
                    seen["arrows"] = True

        extra = ["--board-style", style]
        if not center:
            extra.append("--no-center")
        if not status:
            extra.append("--no-status")
        code, text = run_session(seed, cols, rows, check, extra=tuple(extra))
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit {code}")
        if status and not seen["bar"]:
            raise AssertionError("status bar never seen")
        return seen

    def test_matrix(self):
        cases = []
        for st in STYLES:
            for cols, rows in ((80, 24), (100, 30)):
                for seed in (6, 7, 8):
                    cases.append((st, seed, cols, rows, True, True))
            cases.append((st, 9, 120, 40, False, True))
            cases.append((st, 10, 120, 40, True, False))
            cases.append((st, 11, 80, 25, True, False))
        with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            futs = [(c, ex.submit(self.one, *c)) for c in cases]
        for c, f in futs:
            with self.subTest(case=c):
                seen = f.result()
                if c[0] in ("renegade", "telegard"):
                    self.assertTrue(seen["sel"], "no 'What is your selection? [x]'")
                if c[0] == "mystic":
                    self.assertTrue(seen["colons"])
                    self.assertTrue(seen["arrows"])


if __name__ == "__main__":
    unittest.main()
