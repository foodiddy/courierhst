"""Tester acceptance checks for the PR #8 "Also noticed" fixes (task mwfxj435bxgw2e).

1. PCBoard splash "ansi by" credit is right-aligned and never cut.
2. Mystic file list filename column fits 13-char names; header and rows line up.
3. Line.offline_msg removed; status bar and PCBoard file list unchanged vs main.
"""
import json
import os
import random
import re
import subprocess
import sys
import tarfile
import tempfile
import io
import unittest

from courierhst import ansi, bbs
from tests.test_tester_restyle import Capture, session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "8fa11e5"  # main before this task


def raw_out(s):
    """Patch Session.out to record lines *before* its 79-col truncation."""
    lines = []
    orig = s.out

    def out(x):
        lines.extend([x] if isinstance(x, str) else list(x))
        orig(x)
    s.out = out
    return lines


def base_tree():
    """Extract courierhst/ at BASE into a temp dir; return its path or None."""
    try:
        data = subprocess.run(["git", "archive", "--format=tar", BASE, "courierhst"],
                              cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    tmp = tempfile.TemporaryDirectory(prefix="courierhst-base-")
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for m in t.getmembers():  # our own git archive; reject odd paths anyway
            if m.name.startswith(("/", "..")) or not (m.isfile() or m.isdir()):
                raise AssertionError(m.name)
        if hasattr(tarfile, "data_filter"):
            t.extractall(tmp.name, filter="data")
        else:  # Python < 3.12 (members already checked above)
            t.extractall(tmp.name)
    return tmp


# Run in both trees; prints JSON of PCBoard file lists and status bars.
PROBE = r'''
import json, random, time, io
from courierhst import bbs, ansi
from courierhst.modem import Line

class Cap:
    def __init__(self):
        self.parts = []; self.online_since = None; self.status_name = ""
        self.connect_speed = ""; self.dialing = False
    def send(self, s): self.parts.append(s)
    def sendln(self, s=""): self.parts.append(s + "\n")
    local = send
    def type(self, s, fast=False): self.parts.append(s)
    def type_hidden(self, s): self.parts.append("*" * len(s))
    def enter(self): self.parts.append("\n")
    def pause(self, *a): pass
    rpause = pause
    def cls_local(self): pass

res = {"pcb": {}, "status": {}, "credit": {}}
for kind in ("fresh", "games", "utils", "art", "demos"):
    for seed in range(1, 21):
        cap = Cap()
        s = bbs.Session(cap, random.Random(seed), "Tester", xfer_speedup=1e9, style="pcboard")
        cap.parts.clear()
        s.rng.seed(1000 + seed)
        flagged = s.file_list_pcb(kind)
        res["pcb"][f"{kind}/{seed}"] = ["".join(cap.parts), flagged]
for seed in range(1, 21):
    cap = Cap()
    s = bbs.Session(cap, random.Random(seed), "Tester", xfer_speedup=1e9, style="pcboard")
    s.b.art_by = ("Zed", "ACiD")
    cap.parts.clear()
    s.splash_pcb()
    res["credit"][str(seed)] = ansi.strip("".join(cap.parts)).rstrip("\n").split("\n")[-1]

class Out(io.StringIO):
    def fileno(self): raise OSError
real = time.monotonic
for cols in (80, 100, 60):
    for name in ("", "Short BBS", "A Ridiculously Long Board Name That Will Not Fit At All " * 2):
        for state in ("online", "dialing", "offline"):
            line = Line(noise=0, out=Out())
            line.cols, line.rows = cols, 30
            line.left = max(0, (cols - 80) // 2)
            line.status_row = 27
            line.status_name = name
            time.monotonic = lambda: 5000.0
            line.online_since = 5000.0 - 3725 if state == "online" else None
            line.dialing = state == "dialing"
            line._buf.clear()
            line._draw_status(force=True)
            time.monotonic = real
            res["status"][f"{cols}/{len(name)}/{state}"] = "".join(line._buf)
print(json.dumps(res))
'''


def probe(tree):
    env = dict(os.environ, PYTHONPATH=tree)
    p = subprocess.run([sys.executable, "-c", PROBE], cwd=tree, env=env,
                       capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class AgainstMain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = base_tree()
        if base is None:
            raise unittest.SkipTest(f"revision {BASE} not available")
        with base:
            cls.old = probe(base.name)
        cls.new = probe(ROOT)

    def test_pcboard_file_list_identical(self):
        self.assertEqual(set(self.old["pcb"]), set(self.new["pcb"]))
        for k in self.old["pcb"]:
            self.assertEqual(self.new["pcb"][k], self.old["pcb"][k], k)

    def test_status_bar_identical(self):
        self.assertEqual(len(self.old["status"]), 27)
        self.assertEqual(self.new["status"], self.old["status"])
        joined = " ".join(self.new["status"].values())
        for word in ("Offline", "Dialing", "Connected: 01:02:05"):
            self.assertIn(word, joined)

    def test_short_credit_same_text(self):
        for seed, old in self.old["credit"].items():
            new = self.new["credit"][seed]
            self.assertEqual(new.strip(), old.strip(), seed)
            self.assertEqual(new.strip(), "ansi by zed/acid")
            self.assertEqual(len(new), 79)  # now ends exactly at col 79


class PcbCredit(unittest.TestCase):
    def credit_line(self, artist, group="ACiD", seed=1):
        s, cap = session("pcboard", seed)
        s.b.art_by = (artist, group)
        lines = raw_out(s)
        s.splash_pcb()
        return lines[-1], cap

    def test_lengths(self):
        for n in (5, 20, 40, 60):
            for seed in (1, 2, 3):
                artist = ("Ab" * 40)[:n]
                ln, _ = self.credit_line(artist, seed=seed)
                self.assertTrue(ln.startswith("|08"), repr(ln))
                plain = ansi.strip(ln)
                self.assertLessEqual(ansi.vlen(ln), 79, (n, plain))
                want = f"ansi by {artist.lower()}/acid"
                if len(want) <= 79:
                    self.assertTrue(plain.endswith(want), (n, plain))
                    self.assertEqual(len(plain), 79, n)  # right-aligned

    def test_is_last_row_after_rule(self):
        s, cap = session("pcboard", 4)
        s.b.art_by = ("X" * 40, "ACiD")
        lines = raw_out(s)
        s.splash_pcb()
        self.assertIn("ansi by", ansi.strip(lines[-1]))
        self.assertIn("═", ansi.strip(lines[-2]))
        self.assertEqual(sum("ansi by" in ansi.strip(l) for l in lines), 1)
        # and the full text survives the out() truncation
        self.assertIn(f"ansi by {'x' * 40}/acid", cap.text())

    def test_overlong_multiword_drops_whole_words(self):
        artist = "Mega Ultra Super Long Handle Of Elite Doom Number Sixty Seven"
        group = "The Very Long Group Name Inc"
        ln, _ = self.credit_line(artist, group)
        plain = ansi.strip(ln)
        self.assertLessEqual(len(plain), 79)
        text = plain.strip()
        self.assertTrue(text.startswith("ansi by mega"), text)
        self.assertTrue(text.endswith("/" + group.lower()), text)
        kept = text[len("ansi by "):-len("/" + group.lower())]
        self.assertTrue(artist.lower().startswith(kept), kept)
        # no word cut at the edge: kept ends at a word boundary of the artist
        self.assertIn(artist.lower()[len(kept):len(kept) + 1], ("", " "), kept)

    def test_overlong_single_word_fits(self):
        ln, _ = self.credit_line("Q" * 90, "ACiD")
        self.assertLessEqual(ansi.vlen(ln), 79)
        self.assertTrue(ansi.strip(ln).strip().startswith("ansi by q"))
        self.assertTrue(ansi.strip(ln).endswith("/acid"))

    def test_real_boards_fit(self):
        for seed in range(200):
            s, _ = session("pcboard", seed)
            lines = raw_out(s)
            s.splash_pcb()
            plain = ansi.strip(lines[-1])
            self.assertLessEqual(len(plain), 79)
            a, g = s.b.art_by
            self.assertTrue(plain.endswith(f"ansi by {a.lower()}/{g.lower()}"), plain)


class MysticFileList(unittest.TestCase):
    KINDS = ("fresh", "games", "utils", "art", "demos")

    def rows(self, kind, seed, entries=None):
        s, _ = session("mystic", seed)
        if entries is not None:
            s._entries = lambda k: entries
        lines = raw_out(s)
        s.rng.seed(seed)
        try:
            s.file_list(kind)
        except Exception:  # later prompts/downloads are not our concern
            pass
        plain = [ansi.strip(l) for l in lines if l != bbs.CLS]
        hdr = next(i for i, l in enumerate(plain) if "FILENAME" in l)
        body = []
        for l in plain[hdr + 2:]:
            if not l.strip():
                break
            body.append(l)
        return plain[hdr], body, [l for l in lines if l != bbs.CLS]

    def check(self, hdr, body, raw):
        f0, s0 = hdr.index("FILENAME"), hdr.index("SIZE")
        d0 = hdr.index("DESCRIPTION")
        mains = [l for l in body if len(l) - len(l.lstrip(" ")) < f0]
        self.assertTrue(mains)
        for l in mains:
            m = re.match(r"^(\s+\d+\s+)(\S+)(\s+)(\d+k)", l)
            self.assertIsNotNone(m, l)
            self.assertEqual(len(m.group(1)), f0, l)
            self.assertGreaterEqual(len(m.group(3)), 1, l)
            self.assertEqual(m.start(4), s0, l)
            self.assertNotEqual(l[d0 - 1:d0], "", l)
            self.assertEqual(l[d0 - 1], " ", l)
        for l in body:
            if l not in mains:  # continuation lines
                self.assertEqual(len(l) - len(l.lstrip(" ")), d0, l)
        for l in raw:
            self.assertLessEqual(ansi.vlen(l), 79, ansi.strip(l))

    def test_every_kind_seeds_1_to_20(self):
        for kind in self.KINDS:
            for seed in range(1, 21):
                with self.subTest(kind=kind, seed=seed):
                    self.check(*self.rows(kind, seed))

    def test_13_char_artpack_names(self):
        seen = 0
        for seed in range(1, 41):
            hdr, body, raw = self.rows("art", seed)
            self.check(hdr, body, raw)
            seen += sum(bool(re.search(r"\b\S{4}-\d{4}\.ZIP\b", l)) for l in body)
        self.assertGreater(seen, 0)
        # forced: a 13-char name next to a short one
        ents = [("NOiR-1893.ZIP", 400, "07-01-93", 3, ["|07a", "|07b"], None, None),
                ("A.ZIP", 9, "07-01-93", 3, ["|07c"], None, None)]
        hdr, body, raw = self.rows("utils", 1, ents)
        self.check(hdr, body, raw)
        self.assertIn("NOiR-1893.ZIP ", body[0])

    def test_longest_generated_filenames_fit(self):
        longest = 0
        for kind in self.KINDS:
            for seed in range(300):
                s, _ = session("mystic", seed)
                for e in s._entries(kind):
                    longest = max(longest, len(e[0]))
        self.assertLessEqual(longest + 1, 14, longest)


class DeadCode(unittest.TestCase):
    def test_no_offline_msg(self):
        hits = []
        for dp, _, fs in os.walk(os.path.join(ROOT, "courierhst")):
            for f in fs:
                if f.endswith(".py"):
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        if "offline_msg" in fh.read():
                            hits.append(f)
        self.assertEqual(hits, [])

    def test_line_has_no_offline_msg(self):
        from courierhst.modem import Line

        class O(io.StringIO):
            def fileno(self):
                raise OSError
        self.assertFalse(hasattr(Line(noise=0, out=O()), "offline_msg"))

    def test_file_list_pcb_has_no_style_branch(self):
        import inspect
        src = inspect.getsource(bbs.Session.file_list_pcb)
        self.assertNotIn("b.style", src)


if __name__ == "__main__":
    unittest.main()
