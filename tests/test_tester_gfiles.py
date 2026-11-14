"""Tester checks for G-Files part 1 (task mwgoa58eg59i3k).

Independent of tests/test_gfiles.py: loader edge cases, the shipped data and
its files.bbs indexes, package-data coverage, scene_message over many seeds,
main menus for every style, the G-Files screens driven with a fake line, the
Scene Chatter wiring in both message readers, and pty runs (80x24, plus a
temp gfiles root holding literal pipes).
"""
import configparser
import fcntl
import fnmatch
import os
import pty
import random
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

try:
    import pyte
except ImportError:  # pragma: no cover
    pyte = None

from courierhst import ansi, bbs, content, gfiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES = ["renegade", "telegard", "mystic", "pcboard"]
NEEDS_PYTE = unittest.skipIf(pyte is None,
                             "pyte not installed (pip install '.[test]')")
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
ORIGINAL = ["scene", "bbs", "rants", "misc"]
PHONE = re.compile(r"\d{3}-\d{4}")
HARMFUL = re.compile(
    r"\b(carding|card(ed)? number|credit card|calling card|blue ?box|red ?box|"
    r"black ?box|phreak(ing)?|code(s)? ?(scan|hack)|extender|password(s)? ?(is|are)|"
    r"exploit|pipe bomb|explosive|narcotic|cocaine|meth|weed)\b", re.I)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("latin-1"))


class Line:
    """Records everything sent; every pause is a no-op."""

    def __init__(self):
        self.parts = []
        self.online_since = None
        self.status_name = ""
        self.connect_speed = ""
        self.dialing = False

    def send(self, s):
        self.parts.append(s)

    def sendln(self, s=""):
        self.parts.append(s + "\n")

    def type(self, s, fast=False):
        self.parts.append(s)

    def type_hidden(self, s):
        self.parts.append("*" * len(s))

    def enter(self):
        self.parts.append("\n")

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def raw(self):
        return "".join(self.parts)

    def text(self):
        return ansi.strip(self.raw())


def session(style, seed=1):
    line = Line()
    s = bbs.Session(line, random.Random(seed), "Tester", xfer_speedup=1e9,
                    style=style, step_pause=0)
    return s, line


class TmpRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)


# ---------------------------------------------------------------- loader
class LoaderEdges(TmpRoot):
    def test_sections_constant(self):
        self.assertEqual(gfiles.SECTIONS, [
            ("scene", "Scene & NFOs"), ("bbs", "BBS Lists & Ads"),
            ("rants", "Rants & Editorials"), ("misc", "Humor & Misc")])

    def test_default_root_is_package_data(self):
        want = os.path.join(os.path.dirname(gfiles.__file__), "data", "gfiles")
        self.assertEqual(os.path.realpath(gfiles.DATA_DIR), os.path.realpath(want))
        self.assertEqual(gfiles.load(), gfiles.load(gfiles.DATA_DIR))

    def test_root_is_a_file(self):
        write(self.p("f"), "x")
        self.assertEqual(gfiles.load(self.p("f")), [])

    def test_known_sections_first_then_extras_sorted(self):
        for folder in ("zeta", "misc", "alpha", "scene"):
            write(self.p(folder, "A.TXT"), "x\n")
        self.assertEqual([s["folder"] for s in gfiles.load(self.tmp)],
                         ["scene", "misc", "alpha", "zeta"])

    def test_only_txt_files_case_insensitive(self):
        write(self.p("misc", "a.txt"), "lower\n")
        write(self.p("misc", "B.TxT"), "mixed\n")
        write(self.p("misc", "C.DIZ"), "nope\n")
        write(self.p("misc", "files.bbs"), "a.txt  hi\n")
        os.makedirs(self.p("misc", "DIR.TXT"))
        names = [f["name"] for f in gfiles.load(self.tmp)[0]["files"]]
        self.assertEqual(sorted(names), ["B.TxT", "a.txt"])
        self.assertEqual(names, sorted(names))

    def test_files_bbs_case_continuation_and_length(self):
        write(self.p("misc", "ONE.TXT"), "first line one\n")
        write(self.p("misc", "two.txt"), "first line two\n")
        write(self.p("misc", "THREE.TXT"), "\n\n   \n   third first line   \n")
        write(self.p("misc", "files.bbs"),
              "one.txt       Lower-case index entry\n"
              "              | continuation should be ignored\n"
              "\tTHREE.TXT    tab continuation, not a file entry\n"
              "TWO.TXT       " + "D" * 80 + "\n")
        files = {f["name"]: f for f in gfiles.load(self.tmp)[0]["files"]}
        self.assertEqual(files["ONE.TXT"]["desc"], "Lower-case index entry")
        self.assertEqual(files["two.txt"]["desc"], "D" * 45)
        self.assertEqual(files["THREE.TXT"]["desc"], "third first line")

    def test_files_bbs_garbage_and_directory(self):
        write(self.p("misc", "A.TXT"), "aaa\n")
        write(self.p("misc", "files.bbs"), bytes(range(256)) * 4)
        self.assertEqual(len(gfiles.load(self.tmp)[0]["files"]), 1)
        write(self.p("rants", "B.TXT"), "bbb\n")
        os.makedirs(self.p("rants", "files.bbs"))
        secs = {x["folder"]: x for x in gfiles.load(self.tmp)}
        self.assertEqual(secs["rants"]["files"][0]["desc"], "bbb")

    def test_empty_and_blank_files(self):
        write(self.p("misc", "EMPTY.TXT"), b"")
        write(self.p("misc", "BLANK.TXT"), "\n   \n\t\n")
        files = gfiles.load(self.tmp)[0]["files"]
        self.assertEqual({f["desc"] for f in files}, {""})
        self.assertEqual(gfiles.read(files[1]), [])

    @unittest.skipIf(IS_ROOT, "root can read mode-000 files")
    def test_unreadable_file_and_folder(self):
        write(self.p("misc", "OK.TXT"), "fine\n")
        write(self.p("misc", "LOCKED.TXT"), "secret\n")
        write(self.p("rants", "X.TXT"), "x\n")
        os.chmod(self.p("misc", "LOCKED.TXT"), 0)
        os.chmod(self.p("rants"), 0)
        self.addCleanup(os.chmod, self.p("rants"), 0o755)
        secs = gfiles.load(self.tmp)
        self.assertEqual([s["folder"] for s in secs], ["misc"])
        locked = [f for f in secs[0]["files"] if f["name"] == "LOCKED.TXT"]
        if locked:
            self.assertEqual(gfiles.read(locked[0]), [])

    def test_read_bad_entries(self):
        self.assertEqual(gfiles.read({"path": self.p("missing.txt")}), [])
        os.makedirs(self.p("d"))
        self.assertEqual(gfiles.read({"path": self.p("d")}), [])

    def test_read_control_chars_crlf_cp437(self):
        write(self.p("misc", "C.TXT"),
              b"a\x1b[31mb\x07c\x00d\x7f\r\n\xdb\xb0\xc4 box\r\n\tx\ty\r\n")
        lines = gfiles.read(gfiles.load(self.tmp)[0]["files"][0])
        self.assertEqual(lines[0], "a[31mbcd")
        self.assertEqual(lines[1], "█░─ box")
        self.assertEqual(lines[2], "        x       y")
        for ln in lines:
            self.assertFalse(any(ord(c) < 32 or ord(c) == 127 for c in ln), ln)

    def test_read_tabs_then_truncate(self):
        write(self.p("misc", "T.TXT"), "\t" * 12 + "z\n")
        line = gfiles.read(gfiles.load(self.tmp)[0]["files"][0])[0]
        self.assertLessEqual(len(line), 79)
        self.assertNotIn("\t", line)

    def test_fake_date_many_names(self):
        for i in range(5000):
            name = f"F{i}.TXT"
            d = gfiles.fake_date(name)
            self.assertEqual(d, gfiles.fake_date(name))
            m = re.fullmatch(r"(\d\d)-(\d\d)-(\d\d)", d)
            self.assertIsNotNone(m, d)
            mm, dd, yy = map(int, m.groups())
            self.assertTrue(1 <= mm <= 12 and 1 <= dd <= 31 and 90 <= yy <= 93, d)
        self.assertEqual(gfiles.fake_date("ÿé.TXT"), gfiles.fake_date("ÿé.TXT"))
        self.assertEqual(len({gfiles.fake_date(f"N{i}") for i in range(200)}) > 20, True)


# ---------------------------------------------------------------- shipped
class Shipped(unittest.TestCase):
    def setUp(self):
        self.secs = gfiles.load()

    def files(self):
        for s in self.secs:
            for f in s["files"]:
                yield s, f

    def test_line_counts_width_and_encoding(self):
        for s, f in self.files():
            with open(f["path"], "rb") as fh:
                raw = fh.read()
            text = raw.decode("cp437")
            lines = text.splitlines()
            self.assertTrue(25 <= len(lines) <= 80, (f["name"], len(lines)))
            for n, ln in enumerate(lines, 1):
                self.assertLessEqual(len(ln.expandtabs(8)), 79, f"{f['name']}:{n}")
                self.assertNotIn("\x1b", ln, f"{f['name']}:{n}")

    def test_phone_numbers(self):
        for s, f in self.files():
            with open(f["path"], "rb") as fh:
                text = fh.read().decode("cp437")
            for num in PHONE.findall(text):
                self.assertRegex(num, r"^555-01\d\d$", f["name"])

    def test_harmless_keywords(self):
        # Part-1 sections only; hackphrk discusses boxes as history and has
        # its own denylist in tests/test_tester_hackphrk.py.
        for s, f in self.files():
            if s["folder"] not in ORIGINAL:
                continue
            with open(f["path"], "rb") as fh:
                text = fh.read().decode("cp437")
            self.assertIsNone(HARMFUL.search(text), f["name"])

    def test_three_or_four_per_section(self):
        self.assertEqual([s["folder"] for s in self.secs][:4], ORIGINAL)
        for s in self.secs:
            if s["folder"] in ORIGINAL:
                self.assertTrue(3 <= len(s["files"]) <= 4, s["folder"])

    def test_upper_case_names(self):
        for s, f in self.files():
            self.assertEqual(f["name"], f["name"].upper())
            self.assertRegex(f["name"], r"^[A-Z0-9_]{1,8}\.TXT$", "not 8.3")

    def test_files_bbs_index_matches(self):
        for s in self.secs:
            folder = os.path.dirname(s["files"][0]["path"])
            with open(os.path.join(folder, "files.bbs"), "rb") as fh:
                lines = fh.read().decode("cp437").splitlines()
            names = {f["name"] for f in s["files"]}
            listed = set()
            for ln in lines:
                if not ln.strip() or ln[0] in " \t":
                    continue
                name = ln.split()[0]
                listed.add(name)
                self.assertIn(name, names, f"{s['folder']}/files.bbs: {name}")
                self.assertLessEqual(len(ln[13:].strip()), 45, ln)
            self.assertEqual(listed, names, s["folder"])
            for f in s["files"]:
                with open(os.path.join(folder, "files.bbs")) as fh:
                    row = [l for l in fh if l.split() and l.split()[0] == f["name"]][0]
                self.assertEqual(f["desc"], row.split(None, 1)[1].strip()[:45])

    def test_files_bbs_layout_name_padded_to_13(self):
        """Spec: filename left-padded to 13 columns, then the description."""
        for s in self.secs:
            folder = os.path.dirname(s["files"][0]["path"])
            with open(os.path.join(folder, "files.bbs")) as fh:
                for ln in fh.read().splitlines():
                    if not ln.strip() or ln[0] in " \t":
                        continue
                    with self.subTest(section=s["folder"], line=ln):
                        name = ln.split()[0]
                        self.assertLessEqual(len(name), 12, "name overflows the 13-col field")
                        self.assertEqual(ln[:13].rstrip(), name)

    def test_package_data_covers_shipped_files(self):
        with open(os.path.join(ROOT, "pyproject.toml")) as fh:
            text = fh.read()
        m = re.search(r"\[tool\.setuptools\.package-data\]\s*\n\s*courierhst\s*=\s*\[([^\]]*)\]", text)
        self.assertIsNotNone(m, "package-data for courierhst missing")
        pats = re.findall(r'"([^"]+)"', m.group(1))
        for p in ("data/gfiles/*/*.txt", "data/gfiles/*/files.bbs"):
            self.assertIn(p, pats)
        pkg = os.path.dirname(gfiles.__file__)
        for dirpath, _, names in os.walk(os.path.join(pkg, "data", "gfiles")):
            for n in names:
                rel = os.path.relpath(os.path.join(dirpath, n), pkg).replace(os.sep, "/")
                self.assertTrue(any(fnmatch.fnmatchcase(rel, p) for p in pats), rel)


# ---------------------------------------------------------------- scene chatter
class SceneChatter(unittest.TestCase):
    def test_many_seeds(self):
        want = set(content.message(random.Random(1), "X"))
        uppers = lowers = 0
        subjects = set()
        for seed in range(400):
            rng = random.Random(seed)
            m = content.scene_message(rng, content.bbs_name(rng))
            self.assertEqual(set(m), want)
            subjects.add(m["subj"])
            fields = [m["subj"], m["from"], m["to"], m["date"], m["time"]] + m["body"]
            if m.get("tag"):
                fields.append(m["tag"])
            for ln in fields:
                self.assertIsInstance(ln, str)
                self.assertLessEqual(ansi.vlen(ln), 79, ln)
                self.assertNotIn("{", ln)
                self.assertNotIn("}", ln)
                self.assertNotIn("|", ln)
            body = " ".join(m["body"])
            hit = HARMFUL.search(body.replace(m["from"], "").replace(m["to"], ""))
            if hit and hit.group(0).lower().startswith("phreak"):
                hit = None  # "Phreak" also occurs inside invented handles
            self.assertIsNone(hit, body)
            for num in PHONE.findall(body + " " + m["subj"]):
                self.assertRegex(num, r"^555-01\d\d$")
            uppers += sum(c.isupper() for c in body)
            lowers += sum(c.islower() for c in body)
        self.assertGreater(uppers, lowers * 2, "should be mostly upper case")
        self.assertGreaterEqual(len(subjects), 10)

    def test_deterministic(self):
        a = content.scene_message(random.Random(42), "B")
        b = content.scene_message(random.Random(42), "B")
        self.assertEqual(a, b)

    def test_templates_harmless(self):
        for subj, body in content._SCENE_TEMPLATES:
            self.assertIsNone(HARMFUL.search(subj + " " + " ".join(body)), subj)


class SceneWiring(unittest.TestCase):
    def run_base(self, style, meth, base):
        s, line = session(style, 3)
        with mock.patch.object(content, "MSG_BASES", [base] * 8), \
                mock.patch.object(content, "scene_message",
                                  wraps=content.scene_message) as sm, \
                mock.patch.object(content, "message",
                                  wraps=content.message) as msg:
            getattr(s, meth)()
        return sm.call_count, msg.call_count, line

    def test_scene_base_uses_scene_message(self):
        for style, meth in [("renegade", "do_msgs"), ("mystic", "do_msgs"),
                            ("telegard", "do_msgs"), ("pcboard", "do_msgs_pcb")]:
            with self.subTest(style=style):
                sm, msg, line = self.run_base(style, meth, "Scene Chatter")
                self.assertGreater(sm, 0)
                self.assertEqual(msg, 0)
                for ln in line.text().splitlines():
                    self.assertLessEqual(len(ln), 79 + 40, ln)

    def test_other_base_uses_message(self):
        for style, meth in [("renegade", "do_msgs"), ("pcboard", "do_msgs_pcb")]:
            with self.subTest(style=style):
                sm, msg, _ = self.run_base(style, meth, "General Chat")
                self.assertEqual(sm, 0)
                self.assertGreater(msg, 0)


# ---------------------------------------------------------------- menus / plan
class Menus(unittest.TestCase):
    def test_main_menu_fits_all_styles(self):
        for style in STYLES:
            for seed in range(30):
                s, _ = session(style, seed)
                menu = bbs.main_menu(s.b)
                with self.subTest(style=style, seed=seed):
                    rows = [m for m in menu if m != bbs.CLS]
                    self.assertLessEqual(len(rows), 24)
                    for ln in rows:
                        self.assertLessEqual(ansi.vlen(ln), 79, ansi.strip(ln))
                    self.assertIn("G-Files", ansi.strip("\n".join(rows)))

    def test_keys(self):
        keys = [k for k, _, _ in bbs.MAIN_CMDS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn(("T", "Text Files/G-Files", "gfiles"), bbs.MAIN_CMDS)
        self.assertEqual(len(set(bbs.PCB_KEYS.values())), len(bbs.PCB_KEYS))
        for style in STYLES:
            s, _ = session(style)
            self.assertEqual(bbs.key_for(s.b, "gfiles"),
                             "TF" if style == "pcboard" else "T")
        s, _ = session("pcboard")
        self.assertIn("TF", ansi.strip("\n".join(bbs.main_menu(s.b))))

    def test_every_menu_action_has_handler(self):
        for _, _, act in bbs.MAIN_CMDS:
            self.assertTrue(hasattr(bbs.Session, "do_" + act), act)
            self.assertIn(act, bbs.PCB_KEYS)

    def test_plan(self):
        seen_gf = 0
        for style in STYLES:
            for seed in range(200):
                s, _ = session(style, seed)
                acts = s._plan(s.rng.randint(4, 8))
                self.assertIn("files", acts)
                seen_gf += "gfiles" in acts
        self.assertGreater(seen_gf, 100)


# ---------------------------------------------------------------- screens
class Screens(TmpRoot):
    def run_gfiles(self, style, seed, root=None):
        s, line = session(style, seed)
        secs = gfiles.load(root) if root else gfiles.load()
        with mock.patch.object(gfiles, "load", lambda *a, **k: secs):
            s.do_gfiles()
        return s, line

    def test_all_styles_shipped(self):
        names = {f["name"] for s in gfiles.load() for f in s["files"]}
        for style in STYLES:
            for seed in range(25):
                with self.subTest(style=style, seed=seed):
                    s, line = self.run_gfiles(style, seed)
                    raw = line.raw()
                    for ln in raw.split("\n"):
                        self.assertLessEqual(ansi.vlen(ln.replace(bbs.CLS, "")), 79 + 30)
                    text = line.text()
                    self.assertIn("Scene & NFOs", text)
                    self.assertIn("Humor & Misc", text)
                    self.assertIn(" " + "=" * 76, text)
                    self.assertRegex(text, r"Page [1-3] of \d")
                    self.assertTrue(any(n in text for n in names))
                    pages = re.findall(r"Page (\d) of (\d)", text)
                    self.assertTrue(1 <= len(pages) <= 3)
                    self.assertEqual([int(p[0]) for p in pages],
                                     list(range(1, len(pages) + 1)))
                    self.assertEqual(text.count("Hit a key"), len(pages) - 1)

    def test_screen_builders_fit(self):
        secs = gfiles.load()
        for style in STYLES:
            s, _ = session(style)
            out = s.gfile_sections(secs)
            self.assertLessEqual(len([l for l in out if l != bbs.CLS]), 24)
            for sec in secs:
                lst = s.gfile_listing(sec["title"], sec["files"][:20])
                self.assertLessEqual(len([l for l in lst if l != bbs.CLS]), 24)
                for ln in out + lst:
                    if ln != bbs.CLS:
                        self.assertLessEqual(ansi.vlen(ln), 79, ansi.strip(ln))
                plain = ansi.strip("\n".join(lst))
                self.assertIn(sec["title"], plain)
                for f in sec["files"]:
                    self.assertIn(f["date"], plain)
                    self.assertIn(f"{f['size']:>7}", plain)

    def test_listing_shows_full_filenames(self):
        """The name the caller types must match what the listing shows."""
        for style in STYLES:
            s, _ = session(style)
            for sec in gfiles.load():
                plain = ansi.strip("\n".join(s.gfile_listing(sec["title"], sec["files"])))
                for f in sec["files"]:
                    with self.subTest(style=style, name=f["name"]):
                        self.assertRegex(plain, r"(?m)^ " + re.escape(f["name"]) + r" ")

    def test_listing_capped_at_20(self):
        for i in range(30):
            write(self.p("misc", f"F{i:02d}.TXT"), f"file {i}\n")
        for style in STYLES:
            for seed in range(5):
                s, line = self.run_gfiles(style, seed, self.tmp)
                text = line.text()
                self.assertIn("F19.TXT", text)
                self.assertNotIn("F20.TXT", text.split("Page")[0])

    def test_reader_pages_and_pipes(self):
        body = ["L%02d a|b ||c |07x |15y ||" % i for i in range(70)]
        write(self.p("misc", "PIPES.TXT"), "\n".join(body) + "\n")
        write(self.p("misc", "files.bbs"), "PIPES.TXT     desc | with |12 pipe\n")
        for style in STYLES:
            for seed in range(10):
                with self.subTest(style=style, seed=seed):
                    s, line = self.run_gfiles(style, seed, self.tmp)
                    text = line.text()
                    self.assertIn("desc | with |12 pipe", text)
                    self.assertRegex(text, r"PIPES\.TXT .*Page 1 of 4")
                    shown = [ln for ln in text.splitlines() if re.match(r"L\d\d ", ln)]
                    self.assertTrue(20 <= len(shown) <= 60)
                    self.assertEqual(len(shown) % 20, 0)
                    for ln in shown:
                        self.assertEqual(ln, body[int(ln[1:3])])
                    self.assertIn("|07L00 a||b ||||c ||07x ||15y ||||", line.raw())

    def test_empty(self):
        for style in STYLES:
            s, line = session(style)
            with mock.patch.object(gfiles, "load", return_value=[]):
                self.assertIsNone(s.do_gfiles())
            self.assertEqual(line.text().strip(), "No text files available.")

    def test_unreadable_selected_file(self):
        write(self.p("misc", "GONE.TXT"), "x\n")
        secs = gfiles.load(self.tmp)
        os.remove(secs[0]["files"][0]["path"])
        s, line = session("renegade")
        with mock.patch.object(gfiles, "load", return_value=secs):
            s.do_gfiles()
        self.assertIn("Page 1 of 1", line.text())


# ---------------------------------------------------------------- pty
def geometry(cols, rows):
    top = max(0, (rows - 26) // 2) + 1
    left = max(0, (cols - 80) // 2)
    height = max(3, min(25, rows - top + 1 - 1))
    bottom = top + height - 1
    return left, top, bottom, bottom + 1


RUNNER = (
    "import sys\n"
    "from courierhst import gfiles\n"
    "if sys.argv[1] != '-':\n"
    "    gfiles.DATA_DIR = sys.argv[1]\n"
    "from courierhst.__main__ import main\n"
    "sys.exit(main(sys.argv[2:]))\n"
)


def run_pty(argv, cols, rows, check, root="-", timeout=240):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-c", RUNNER, root, "--warp", "60",
         "--xfer-speedup", "2000", "--calls", "2", "--no-exit-on-key",
         "--noise", "0", *argv],
        stdin=slave, stdout=slave, stderr=slave, env=env, cwd=ROOT,
        close_fds=True)
    os.close(slave)
    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)
    raw = bytearray()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() > deadline:
                proc.kill()
                raise AssertionError("timeout")
            r, _, _ = select.select([master], [], [], 0.5)
            if r:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                raw += data
                stream.feed(data)
                check(screen)
            elif proc.poll() is not None:
                break
        proc.wait(timeout=10)
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.kill()
    return proc.returncode, bytes(raw).decode("utf-8", "replace")


@NEEDS_PYTE
class GFilesPty(TmpRoot):
    def one(self, style, seed, cols, rows, root="-", marker=None):
        left, top, bottom, status = geometry(cols, rows)
        seen = {"sections": False, "listing": False, "page": False,
                "menu": False, "marker": marker is None}

        def check(screen):
            lines = ["".join(screen.buffer[y][x].data for x in range(cols))
                     for y in range(rows)]
            for y, line in enumerate(lines):
                if y == status - 1:
                    continue
                for x, ch in enumerate(line):
                    if ch.strip() and not (top - 1 <= y <= bottom - 1
                                           and left <= x < left + 80):
                        raise AssertionError(f"glyph outside window x={x} y={y}")
            text = "\n".join(lines)
            if re.search(r"(?m)(Scene & NFOs|Pipes)\s+\d+( files)?\s*$", text):
                seen["sections"] = True
            if "=" * 70 in text and ".TXT" in text:
                seen["listing"] = True
            if re.search(r"Page \d of \d", text):
                seen["page"] = True
                if marker and marker in text:
                    seen["marker"] = True
            if "G-Files" in text and "Goodbye" in text:
                seen["menu"] = True

        code, text = run_pty(["--seed", str(seed), "--board-style", style],
                             cols, rows, check, root)
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit code {code}\n{text[-800:]}")
        return seen

    def test_80x24_all_styles(self):
        cases = [(st, sd) for st in STYLES for sd in (3, 5)]
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            futs = [(c, ex.submit(self.one, c[0], c[1], 80, 24)) for c in cases]
        for case, f in futs:
            with self.subTest(style=case[0], seed=case[1]):
                for k, v in f.result().items():
                    self.assertTrue(v, f"{k} never shown")

    def test_literal_pipes_in_pty(self):
        lines = ["PIPE-TEST a|b |07c ||d"] + [f"filler {i}" for i in range(30)]
        write(self.p("pipes", "PIPES.TXT"), "\n".join(lines) + "\n")
        cases = [(st, 3) for st in STYLES]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [(c, ex.submit(self.one, c[0], c[1], 80, 26, self.tmp,
                                  "PIPE-TEST a|b |07c ||d")) for c in cases]
        for case, f in futs:
            with self.subTest(style=case[0]):
                seen = f.result()
                self.assertTrue(seen["page"], "reader never shown")
                self.assertTrue(seen["marker"], "pipes not shown literally")


if __name__ == "__main__":
    unittest.main()
