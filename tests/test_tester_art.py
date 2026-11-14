"""Tester checks for the original ANSI art library (task mwgm6ym4h93uzr).

Independent of tests/test_art.py and tests/test_art_pty.py:
  * art.PIECES against the spec table (sizes, uses, colours, groups, CP437);
  * pick / piece / credit / side_by_side / wrap contracts;
  * offline Session runs that record every line *before* Session.out
    truncates it, so a line that silently loses its tail is caught, and that
    count screen rows exactly (files, bye + NO CARRIER, both doors);
  * pty runs through pyte at 80x26 and 120x40 for all four styles.
"""
from concurrent.futures import ThreadPoolExecutor
import os
import random
import re
import unittest

from courierhst import ansi, art, bbs, content, doors

try:
    from tests.test_session_pty import BBS_COLS, geometry, pyte, run_session
except ImportError:  # pragma: no cover
    pyte = None

CLS = "\x0c"
STYLES = ["renegade", "telegard", "mystic", "pcboard"]
SPLIT = ["renegade", "telegard", "mystic"]
BLOCKS = set("█▀▄▌▐░▒▓")
SPEC = {
    # name: (use, max cols, min rows, max rows)
    "skull": ("panel", 30, 8, 14),
    "modem": ("panel", 30, 8, 14),
    "floppy": ("panel", 30, 8, 14),
    "dragon": ("door", 30, 8, 12),
    "ship": ("door", 30, 8, 12),
    "phone": ("bye", 34, 8, 12),
}
# well-known real ANSI / scene artist handles that must never be credited
REAL_ARTISTS = {
    "lord jazz", "somms", "the beholder", "jed", "rad man", "radman", "tank",
    "mogel", "luminatus", "napalm", "whazzit", "misfit", "eerie",
    "prisoner #1", "lord scorpio", "aklash", "cat", "dr. jones", "rm",
    "the knight", "mr. x", "ice man", "iceman", "dangerous", "zeus",
    "the dark", "phantom", "sudden death", "lord blood", "pariah",
    "spinsane", "skull", "nail", "h7", "j. random", "fuel", "acid", "ice",
}
REAL_GROUPS = {"acid", "ice", "trank", "mirage", "fire", "cia", "dark",
               "blocktronics", "remorse", "legion"}
CODE = re.compile(r"\|(\d\d)")


def strip(s):
    return ansi.strip(s)


# ------------------------------------------------------------------ pieces
class Pieces(unittest.TestCase):
    def test_exact_required_set_and_uses(self):
        for name, (use, *_rest) in SPEC.items():
            with self.subTest(name=name):
                self.assertIn(name, art.PIECES)
                self.assertIn(use, art.PIECES[name]["uses"])

    def test_keys_and_types(self):
        for name, p in art.PIECES.items():
            with self.subTest(name=name):
                self.assertTrue({"lines", "artist", "group", "uses"} <= set(p))
                self.assertIsInstance(p["lines"], list)
                self.assertIsInstance(p["uses"], tuple)
                self.assertTrue(set(p["uses"]) <= {"panel", "door", "bye"})
                self.assertIn(p["group"], content.ART_GROUPS)
                self.assertTrue(p["artist"].strip())
                for ln in p["lines"]:
                    self.assertIsInstance(ln, str)

    def test_sizes_per_spec_table(self):
        for name, (use, cols, lo, hi) in SPEC.items():
            lines = art.PIECES[name]["lines"]
            with self.subTest(name=name):
                self.assertTrue(lo <= len(lines) <= hi, len(lines))
                widths = {ansi.vlen(x) for x in lines}
                self.assertEqual(len(widths), 1, widths)
                self.assertLessEqual(widths.pop(), cols)

    def test_every_piece_global_limits(self):
        for name, p in art.PIECES.items():
            with self.subTest(name=name):
                self.assertLessEqual(len(p["lines"]), 14)
                self.assertTrue(all(ansi.vlen(x) <= 34 for x in p["lines"]))

    def test_vlen_matches_rendered_text(self):
        for name, p in art.PIECES.items():
            w = ansi.vlen(p["lines"][0])
            for ln in p["lines"]:
                with self.subTest(name=name, line=ln):
                    self.assertEqual(len(strip(ln)), w)
                    self.assertNotIn("\x1b", ln)

    def test_colour_codes_valid_and_at_least_three(self):
        for name, p in art.PIECES.items():
            with self.subTest(name=name):
                codes = set()
                for ln in p["lines"]:
                    ansi.pipe_to_ansi(ln)
                    for c in CODE.findall(ln.replace("||", "")):
                        self.assertLessEqual(int(c), 23, ln)
                        if int(c) <= 15:
                            codes.add(c)
                self.assertGreaterEqual(len(codes), 3, codes)

    def test_uses_cp437_art_glyphs(self):
        for name, p in art.PIECES.items():
            with self.subTest(name=name):
                text = "".join(strip(x) for x in p["lines"])
                self.assertGreaterEqual(sum(c in BLOCKS for c in text), 20)
                for c in text:
                    self.assertTrue(c.isprintable(), repr(c))

    def test_pieces_differ(self):
        seen = {}
        for name, p in art.PIECES.items():
            key = tuple(strip(x) for x in p["lines"])
            self.assertNotIn(key, seen, f"{name} duplicates {seen.get(key)}")
            seen[key] = name

    def test_modem_has_lit_leds(self):
        text = "".join(art.PIECES["modem"]["lines"])
        bright = {c for c in CODE.findall(text) if 9 <= int(c) <= 15 and c != "15"}
        self.assertGreaterEqual(len(bright), 2)

    def test_artists_invented(self):
        for name, p in art.PIECES.items():
            with self.subTest(name=name):
                self.assertNotIn(p["artist"].lower(), REAL_ARTISTS)
                self.assertNotIn(p["group"].lower(), REAL_GROUPS)


# ------------------------------------------------------------- functions
class Functions(unittest.TestCase):
    def test_piece_copy(self):
        for name in art.PIECES:
            a = art.piece(name)
            self.assertEqual(a, art.PIECES[name]["lines"])
            a.append("junk")
            a[0] = "junk"
            self.assertNotEqual(art.piece(name), a)
            self.assertNotIn("junk", art.PIECES[name]["lines"])

    def test_piece_unknown_raises(self):
        with self.assertRaises(KeyError):
            art.piece("no-such-piece")

    def test_pick_use_and_determinism(self):
        for use in ("panel", "door", "bye"):
            want = {n for n, p in art.PIECES.items() if use in p["uses"]}
            got = set()
            for seed in range(200):
                a = art.pick(random.Random(seed), use)
                b = art.pick(random.Random(seed), use)
                self.assertEqual(a, b)
                self.assertIn(a, want)
                got.add(a)
            self.assertEqual(got, want, use)

    def test_pick_independent_of_dict_order(self):
        r1, r2 = random.Random(7), random.Random(7)
        seq1 = [art.pick(r1, "panel") for _ in range(30)]
        seq2 = [art.pick(r2, "panel") for _ in range(30)]
        self.assertEqual(seq1, seq2)

    def test_credit_format(self):
        for name, p in art.PIECES.items():
            c = art.credit(name)
            with self.subTest(name=name):
                self.assertEqual(
                    c, f"|08ansi by {p['artist'].lower()}/{p['group'].lower()}")
                self.assertLessEqual(ansi.vlen(c), 79)
                ansi.pipe_to_ansi(c)

    def test_panel_credit_fits_under_panel(self):
        for name, p in art.PIECES.items():
            if "panel" in p["uses"]:
                self.assertLessEqual(ansi.vlen(art.credit(name)),
                                     ansi.vlen(p["lines"][0]) + 4, name)

    def _check_sbs(self, left, right, gap=2, width=79):
        out = art.side_by_side(left, right, gap, width)
        self.assertEqual(len(out), max(len(left), len(right)))
        lw = max((ansi.vlen(x) for x in left), default=0)
        for i, ln in enumerate(out):
            self.assertLessEqual(ansi.vlen(ln), width)
            ansi.pipe_to_ansi(ln)
            b = right[i] if i < len(right) else ""
            if b and lw + gap + ansi.vlen(b) <= width:
                vis = strip(ln)
                self.assertEqual(vis[lw:lw + gap], " " * gap)
                self.assertEqual(vis[lw + gap:], strip(b))
                self.assertIn("|07|16" + " " * gap + b, ln)
        return out

    def test_left_taller(self):
        left = art.piece("skull")
        right = ["|15one", "|12two"]
        out = self._check_sbs(left, right)
        self.assertEqual(len(out), len(left))

    def test_right_taller(self):
        left = ["|12ab", "|09abcd"]
        right = [f"|1{i % 6}line {i}" for i in range(9)]
        out = self._check_sbs(left, right)
        self.assertEqual(len(out), 9)
        for i in range(2, 9):
            self.assertEqual(strip(out[i])[:6], "      ")

    def test_uneven_left_rows_padded(self):
        out = self._check_sbs(["|14x", "|14xxxxx", ""], ["a", "b", "c"])
        for ln, ch in zip(out, "abc"):
            self.assertEqual(strip(ln).index(ch), 7)

    def test_long_right_truncated(self):
        out = self._check_sbs(art.piece("phone"), ["|07" + "W" * 200] * 3)
        self.assertTrue(all(ansi.vlen(x) == 79 for x in out[:3]))

    def test_custom_gap_and_width(self):
        out = art.side_by_side(["|09aa"], ["|10bb"], gap=5, width=6)
        self.assertEqual(strip(out[0]), "aa    ")

    def test_empty_sides(self):
        self.assertEqual(art.side_by_side([], []), [])
        out = art.side_by_side([], ["|07hi"])
        self.assertEqual(strip(out[0]).strip(), "hi")

    def test_colour_does_not_bleed(self):
        """Rendered: after the left pane the attribute is grey on black."""
        out = art.side_by_side(["|20|14XX"], ["text"])
        esc = ansi.pipe_to_ansi(out[0])
        before = esc[:esc.index("text")]
        last = re.findall(r"\x1b\[([0-9;]*)m", before)[-1].split(";")
        self.assertIn("40", last)
        self.assertNotIn("1", last)
        self.assertIn("37", last)

    def test_wrap_helper(self):
        for w in (20, 43, 47):
            for t in content.TAGLINES:
                lines = art.wrap("|08" + t, w)
                self.assertTrue(all(ansi.vlen(x) <= w for x in lines), (w, t))
                if all(len(x) <= w for x in t.split()):
                    self.assertEqual(" ".join(strip(x) for x in lines).split(),
                                     t.split())
                    self.assertTrue(all(x.startswith("|08") for x in lines))


# ---------------------------------------------------- offline screen capture
class Stop(Exception):
    pass


class Capture:
    """Stand-in for Line.  Every screen is recorded as a list of raw rows."""

    def __init__(self):
        self.parts = []
        self.online_since = None
        self.status_name = ""
        self.connect_speed = ""
        self.offline_msg = ""
        self.dialing = False
        self.stop_on_type = False

    def send(self, s):
        self.parts.append(s)

    def sendln(self, s=""):
        self.parts.append(s + "\n")

    def local(self, s):
        self.parts.append(s)

    def type(self, s, fast=False):
        if self.stop_on_type:
            raise Stop
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

    def last_screen(self):
        """Text from the last CLS on, as visible rows."""
        txt = "".join(self.parts)
        txt = txt[txt.rfind(CLS) + 1:]
        txt = re.sub(r"\x1b\[\d*D", "", ansi.strip(txt))
        return txt.split("\n")


def session(style, seed):
    cap = Capture()
    s = bbs.Session(cap, random.Random(seed), "Tester", xfer_speedup=1e9,
                    style=style)
    raw = []
    orig = s.out

    def out(lines):
        if isinstance(lines, str):
            lines = [lines]
        raw.extend(lines)
        orig(lines)

    s.out = out
    return s, cap, raw


def after_cls(raw):
    return raw[len(raw) - raw[::-1].index(CLS):]


SEEDS = range(12)


class FileScreen(unittest.TestCase):
    def run_files(self, style, seed):
        s, cap, raw = session(style, seed)
        cap.stop_on_type = True
        with self.assertRaises(Stop):
            s.do_files()
        return s, cap, after_cls(raw)

    def test_split_layout(self):
        for st in SPLIT:
            for seed in SEEDS:
                with self.subTest(style=st, seed=seed):
                    s, cap, rows = self.run_files(st, seed)
                    for ln in rows:
                        self.assertLessEqual(ansi.vlen(ln), 79, ln)
                    # header, UPDATED banner above the split
                    vis = [strip(x) for x in rows]
                    self.assertIn("FILE AREAS", "\n".join(vis[:3]))
                    self.assertIn("UPDATED", "\n".join(vis).upper())
                    panel = [n for n in art.PIECES
                             if "panel" in art.PIECES[n]["uses"]
                             and strip(art.PIECES[n]["lines"][0]) in "\n".join(vis)]
                    self.assertEqual(len(panel), 1, "panel art not found")
                    name = panel[0]
                    plines = [strip(x) for x in art.PIECES[name]["lines"]]
                    pw = len(plines[0])
                    start = next(i for i, v in enumerate(vis) if v.startswith(plines[0]))
                    for k, pl in enumerate(plines):
                        self.assertTrue(vis[start + k].startswith(pl), (k, vis[start + k]))
                    credit = strip(art.credit(name))
                    self.assertTrue(vis[start + len(plines)].startswith(credit),
                                    vis[start + len(plines)])
                    # list on the right, every area row beside art/credit
                    for i, (nm, _k) in enumerate(content.FILE_AREAS, 1):
                        row = next((v for v in vis if f"{i:02d}" in v[pw:] and nm in v), None)
                        self.assertIsNotNone(row, f"area {i} {nm!r} missing or cut")
                        self.assertLessEqual(len(row) - pw - 2, 46 + 2)
                    # screen + selection prompt fit in 24 rows
                    self.assertLessEqual(len(rows) + 1, 24, len(rows))

    def test_pcboard_unsplit(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                s, cap, rows = self.run_files("pcboard", seed)
                vis = "\n".join(strip(x) for x in rows)
                self.assertNotIn("ansi by", vis)
                self.assertNotIn("FILE AREAS", vis)
                for nm, _k in content.FILE_AREAS:
                    self.assertIn(nm, vis)
                for p in art.PIECES.values():
                    self.assertNotIn(strip(p["lines"][1]), vis)


class ByeScreen(unittest.TestCase):
    def run_bye(self, style, seed, user="Tester"):
        s, cap, raw = session(style, seed)
        s.user = user
        s.do_bye()
        return s, cap, after_cls(raw)

    def test_layout(self):
        for st in STYLES:
            for seed in SEEDS:
                with self.subTest(style=st, seed=seed):
                    s, cap, rows = self.run_bye(st, seed)
                    for ln in rows:
                        self.assertLessEqual(ansi.vlen(ln), 79, ln)
                    logo = s.b.logo("GOOD BYE", max_rows=4)
                    self.assertLessEqual(len(logo), 4)
                    self.assertEqual(rows[:len(logo)], logo)
                    vis = [strip(x) for x in rows]
                    phone = [strip(x) for x in art.PIECES["phone"]["lines"]]
                    pw = len(phone[0])
                    body = vis[len(logo):]
                    for k, pl in enumerate(phone):
                        self.assertTrue(body[k].startswith(pl), (k, body[k]))
                    right = [v[pw + 2:].rstrip() for v in body[:-1]]
                    text = [i for i, t in enumerate(right) if t]
                    self.assertTrue(right[text[0]].startswith("GOOD BYE FRIEND!"))
                    joined = " ".join(right[i] for i in text)
                    for want in ("Thanks for calling", s.b.name, "Tester!",
                                 "You were on for", "minutes.", "Call back soon",
                                 s.b.phone[2:], "24 hours"):
                        self.assertIn(want, joined)
                    self.assertTrue(any(" ".join(t.split()) in " ".join(joined.split())
                                        for t in content.TAGLINES), "no tagline")
                    # vertically centred against the phone
                    if len(text) < len(phone):
                        top = text[0]
                        bottom = len(phone) - 1 - text[-1]
                        self.assertLessEqual(abs(top - bottom), 1, (top, bottom))
                    self.assertEqual(body[-1].strip(), strip(art.credit("phone")))
                    # bye screen + blank + NO CARRIER within 24 rows
                    self.assertLessEqual(len(rows) + 2, 24, len(rows))
                    tail = cap.last_screen()
                    self.assertIn("NO CARRIER", "\n".join(tail))

    def test_long_user_name_still_fits(self):
        for st in STYLES:
            s, cap, rows = self.run_bye(st, 3, user="X" * 40)
            for ln in rows:
                self.assertLessEqual(ansi.vlen(ln), 79, ln)
            self.assertLessEqual(len(rows) + 2, 24)

    def test_every_tagline_fits(self):
        """Walk seeds until every tagline has appeared at least once."""
        seen = set()
        for seed in range(2000):
            s, cap, rows = self.run_bye(STYLES[seed % 4], seed)
            pw = ansi.vlen(art.PIECES["phone"]["lines"][0]) + 2
            joined = " ".join(" ".join(strip(x)[pw:].split()) for x in rows)
            for i, t in enumerate(content.TAGLINES):
                if " ".join(t.split()) in joined:
                    seen.add(i)
            self.assertLessEqual(len(rows) + 2, 24, seed)
            for ln in rows:
                self.assertLessEqual(ansi.vlen(ln), 79, ln)
            if len(seen) == len(content.TAGLINES):
                break
        self.assertEqual(len(seen), len(content.TAGLINES))


class DoorScreens(unittest.TestCase):
    CASES = {
        "shadowmire": ("dragon", ("The Swamp Kingdom of Vael", "v2.10",
                                  "Bogwater Software", "Registered to",
                                  "Welcome back, Tester", "forest fights left")),
        "starlane": ("ship", ("M E R C H A N T", "v3.4", "Deep Orbit Software",
                              "please register!", "Pilot Tester", "awaits",
                              "turns remaining")),
    }

    def run_door(self, door, style, seed):
        s, cap, raw = session(style, seed)

        def more():
            raise Stop

        s.more = more
        with self.assertRaises(Stop):
            getattr(doors, door)(s)
        return s, after_cls(raw)

    def test_door_title_screens(self):
        for door, (pname, wants) in self.CASES.items():
            for st in STYLES:
                for seed in SEEDS:
                    with self.subTest(door=door, style=st, seed=seed):
                        s, rows = self.run_door(door, st, seed)
                        for ln in rows:
                            self.assertLessEqual(ansi.vlen(ln), 79, ln)
                        vis = [strip(x) for x in rows]
                        plines = [strip(x) for x in art.PIECES[pname]["lines"]]
                        pw = len(plines[0])
                        start = next(i for i, v in enumerate(vis)
                                     if v.startswith(plines[0]))
                        self.assertGreater(start, 0, "logo missing above art")
                        for k, pl in enumerate(plines):
                            self.assertTrue(vis[start + k].startswith(pl), k)
                        right = " ".join(v[pw + 2:].strip()
                                         for v in vis[start:start + max(len(plines), 12)])
                        right = " ".join(right.split())
                        for w in wants:
                            self.assertIn(w, right, w)
                        # screen + [Pause] prompt within 24 rows
                        self.assertLessEqual(len(rows) + 1, 24, len(rows))

    def test_door_uses_its_own_piece(self):
        self.assertIn("door", art.PIECES["dragon"]["uses"])
        self.assertIn("door", art.PIECES["ship"]["uses"])
        s, rows = self.run_door("shadowmire", "renegade", 1)
        self.assertNotIn(strip(art.PIECES["ship"]["lines"][4]),
                         "\n".join(strip(x) for x in rows))


# ------------------------------------------------------------------- pty
PTY_SIZES = [(80, 26), (120, 40)]
PTY_SEEDS = range(1, 7)


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class ArtPtyTester(unittest.TestCase):
    def one(self, style, seed, cols, rows_):
        left, top, bottom, status = geometry(cols, rows_)
        seen = set()
        problems = []

        def window(screen):
            return ["".join(screen.buffer[y][x].data
                            for x in range(left, left + BBS_COLS)).rstrip()
                    for y in range(top - 1, bottom)]

        def check(screen):
            rows = window(screen)
            joined = "\n".join(rows)
            for i, t in enumerate(rows):
                if len(t) >= 80 and i != len(rows) - 1:
                    problems.append(f"row {i} reaches column 80 (wrap):\n{joined}")
            if re.search(r"\|\d\d", joined):
                problems.append("raw pipe code on screen:\n" + joined)
            if "FILE AREAS" in joined and "ansi by" in joined and "08" in joined:
                if not any("( 08 )" in t or " 08" in t for t in rows):
                    return
                hy = next(i for i, t in enumerate(rows) if "FILE AREAS" in t)
                lst = [t for t in rows[hy:] if any(nm in t for nm, _ in content.FILE_AREAS)]
                if len(lst) == len(content.FILE_AREAS):
                    beside = sum(any(c in BLOCKS for c in t[:30]) for t in lst)
                    if beside < 6:
                        problems.append("art not beside file list:\n" + joined)
                    seen.add("files")
            if style == "pcboard":
                for t in rows:
                    if "Upload Area" in t and any(c in BLOCKS for c in t[:30]):
                        problems.append("pcboard file list got an art panel:\n" + joined)
            if "GOOD BYE FRIEND!" in joined:
                r = next(i for i, t in enumerate(rows) if "GOOD BYE FRIEND!" in t)
                if not any(c in BLOCKS for c in rows[r][:34]):
                    problems.append("no phone beside GOOD BYE FRIEND!:\n" + joined)
                if "NO CARRIER" in joined and "Call back soon" in joined:
                    # nothing scrolled: the logo rows are still above the art
                    if r < 3:
                        problems.append("bye screen scrolled:\n" + joined)
                    seen.add("bye")
            if "shadowmire" not in seen and "The Swamp Kingdom" in joined \
                    and "forest fights left" in joined:
                i = next(i for i, t in enumerate(rows) if "The Swamp Kingdom" in t)
                if sum(any(c in BLOCKS for c in t[:30]) for t in rows[i:i + 6]) < 4 or i < 2:
                    problems.append("dragon not beside tagline:\n" + joined)
                seen.add("shadowmire")
            if "starlane" not in seen and "M E R C H A N T" in joined \
                    and "turns remaining" in joined:
                i = next(i for i, t in enumerate(rows) if "M E R C H A N T" in t)
                if sum(any(c in BLOCKS for c in t[:30]) for t in rows[i:i + 6]) < 4 or i < 2:
                    problems.append("ship not beside tagline:\n" + joined)
                seen.add("starlane")

        code, text = run_session(seed, cols, rows_, check,
                                 extra=("--board-style", style))
        return code, text, seen, problems[:1]

    def test_all_styles(self):
        cases = [(st, sd, c, r) for st in STYLES for sd in PTY_SEEDS
                 for (c, r) in PTY_SIZES]
        with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            futs = [(c, ex.submit(self.one, *c)) for c in cases]
        total, per_style = set(), {st: set() for st in STYLES}
        for case, f in futs:
            with self.subTest(case=case):
                code, text, seen, problems = f.result()
                self.assertNotIn("Traceback", text, text[-1500:])
                self.assertEqual(code, 0)
                self.assertEqual(problems, [])
                total |= seen
                per_style[case[0]] |= seen
        for st in SPLIT:
            self.assertIn("files", per_style[st], st)
        self.assertNotIn("files", per_style["pcboard"])
        for key in ("bye", "shadowmire", "starlane"):
            self.assertIn(key, total)


if __name__ == "__main__":
    unittest.main()
