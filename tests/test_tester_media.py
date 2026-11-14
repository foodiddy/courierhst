"""Tester: v1.0 media (renderer, committed images, README) and hackphrk box borders."""
import datetime
import getpass
import glob
import importlib.util
import os
import re
import socket
import subprocess
import sys
import tempfile
import unittest

from tests.test_wordfilter import offences

try:
    import pyte  # noqa: F401
    from PIL import Image, ImageChops, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "tools", "render_media.py")
FONT = os.path.join(ROOT, "tools", "fonts", "Px437_IBM_VGA_8x16.ttf")
MEDIA = os.path.join(ROOT, "docs", "media")
HACK = os.path.join(ROOT, "courierhst", "data", "gfiles", "hackphrk")
VGA = {(0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170), (170, 0, 0),
       (170, 0, 170), (170, 85, 0), (170, 170, 170), (85, 85, 85),
       (85, 85, 255), (85, 255, 85), (85, 255, 255), (255, 85, 85),
       (255, 85, 255), (255, 255, 85), (255, 255, 255)}
NEED = Image is None
SKIP = "Pillow and pyte are needed"


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_media_t", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frames_of(path):
    im = Image.open(path)
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        yield im.convert("RGB")


_GLYPHS = None


def glyph_table():
    global _GLYPHS
    if _GLYPHS is None:
        font = ImageFont.truetype(FONT, 16)
        chars = set(bytes(range(32, 256)).decode("cp437"))
        _GLYPHS = {}
        for ch in sorted(chars):
            im = Image.new("1", (8, 16), 0)
            d = ImageDraw.Draw(im)
            d.fontmode = "1"
            d.text((0, 0), ch, font=font, fill=1)
            _GLYPHS.setdefault(im.tobytes(), ch)
    return _GLYPHS


def image_text(rgb):
    """Read the cells back as text by matching each 8x16 cell to a font glyph."""
    table = glyph_table()
    w, h = rgb.size
    rows = []
    for y in range(0, h, 16):
        row = []
        for x in range(0, w, 8):
            cell = rgb.crop((x, y, x + 8, y + 16))
            cols = [c for _, c in cell.getcolors(256)]
            ch = "?"
            if len(cols) == 1:
                ch = " "
            else:
                px = list(cell.getdata())
                for c in cols:
                    m = Image.new("1", (8, 16), 0)
                    m.putdata([1 if p == c else 0 for p in px])
                    hit = table.get(m.tobytes())
                    if hit is not None:
                        ch = hit
                        break
            row.append(ch)
        rows.append("".join(row))
    return "\n".join(rows)


def private_needles():
    out = set()
    for v in (socket.gethostname(), socket.getfqdn(), os.path.expanduser("~"),
              os.environ.get("USER", ""), ROOT):
        if v and len(v) >= 3 and v not in ("root", "localhost"):
            out.add(v)
    try:
        u = getpass.getuser()
        if len(u) >= 3 and u != "root":
            out.add(u)
    except Exception:
        pass
    return out


def check_private(test, text, where):
    for n in private_needles():
        test.assertNotIn(n.lower(), text.lower(), f"{where}: {n!r}")
    test.assertIsNone(re.search(r"/home/|/Users/|/root/", text), where)
    m = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    test.assertIsNone(m, f"{where}: IP {m and m.group(0)}")
    today = datetime.date.today()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%b %d %Y", "%d %b %Y"):
        test.assertNotIn(today.strftime(fmt), text, where)
    test.assertIsNone(re.search(r"\b20[2-9]\d\b", text), where)


@unittest.skipIf(NEED, SKIP)
class Render(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        for name in ("statusbar", "mystic", "logo"):
            r = subprocess.run([sys.executable, SCRIPT, "--out", cls.tmp.name, "--only", name],
                               cwd=ROOT, capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp.name, name + ".png")

    def test_only_writes_one_file(self):
        self.assertEqual(sorted(os.listdir(self.tmp.name)),
                         ["logo.png", "mystic.png", "statusbar.png"])

    def test_valid_pngs_and_sizes(self):
        for name, h in (("mystic", 416), ("logo", 416), ("statusbar", None)):
            with Image.open(self.path(name)) as im:
                im.load()
                self.assertEqual(im.format, "PNG")
                self.assertEqual(im.width, 640)
                if h:
                    self.assertEqual(im.height, h)
                else:
                    self.assertLess(im.height, 416)
                    self.assertEqual(im.height % 16, 0)

    def test_only_vga_colours(self):
        for name in ("statusbar", "mystic", "logo"):
            with Image.open(self.path(name)) as im:
                cols = {c for _, c in im.convert("RGB").getcolors(1 << 16)}
            self.assertLessEqual(cols, VGA, name)

    def test_reproducible(self):
        for name in ("statusbar", "mystic", "logo"):
            with Image.open(self.path(name)) as a, \
                    Image.open(os.path.join(MEDIA, name + ".png")) as b:
                self.assertEqual(a.size, b.size, name)
                diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
                self.assertIsNone(diff.getbbox(), name)

    def test_statusbar_shows_status_row(self):
        with Image.open(self.path("statusbar")) as im:
            text = image_text(im.convert("RGB"))
        self.assertTrue(text.strip(), text)

    def test_mystic_main_menu_text(self):
        with Image.open(self.path("mystic")) as im:
            text = image_text(im.convert("RGB"))
        self.assertIn("(Main) ->", text)


@unittest.skipIf(NEED, SKIP)
class Palette(unittest.TestCase):
    def setUp(self):
        self.m = load_renderer()

    def test_palette_values(self):
        self.assertEqual(self.m.PALETTE, [
            0x000000, 0x0000AA, 0x00AA00, 0x00AAAA, 0xAA0000, 0xAA00AA, 0xAA5500,
            0xAAAAAA, 0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555, 0xFF55FF,
            0xFFFF55, 0xFFFFFF])

    def test_names_and_bold(self):
        c = self.m.colour
        for name, i in (("black", 0), ("blue", 1), ("green", 2), ("cyan", 3), ("red", 4),
                        ("magenta", 5), ("brown", 6), ("white", 7)):
            self.assertEqual(c(name, False, 7), i, name)
            self.assertEqual(c(name, True, 7), i + 8, name)
        self.assertEqual(c("default", False, 7), 7)
        self.assertEqual(c("default", True, 7), 15)
        self.assertEqual(c("brightred", False, 7), 12)
        self.assertEqual(c("brightblack", False, 7), 8)

    def test_sgr_through_pyte(self):
        screen = pyte.Screen(80, 26)
        stream = pyte.ByteStream(screen)
        stream.feed(b"\x1b[0;31mA\x1b[1;31mB\x1b[0;1;33mC\x1b[0;33mD\x1b[0;7mE\x1b[0;44;37mF")
        got = [self.m.cell_colours(screen.buffer[0][x]) for x in range(6)]
        self.assertEqual(got, [(4, 0), (12, 0), (14, 0), (6, 0), (0, 7), (7, 1)])


@unittest.skipIf(NEED, SKIP)
class Committed(unittest.TestCase):
    EXPECTED = {"dialin.gif", "browse.gif", "goodbye.gif", "renegade.png",
                "telegard.png", "mystic.png", "pcboard.png", "logo.png",
                "art.png", "gfiles.png", "statusbar.png"}

    def test_exact_file_set(self):
        self.assertEqual(set(os.listdir(MEDIA)), self.EXPECTED)

    def test_tracked_in_git(self):
        r = subprocess.run(["git", "ls-files", "docs/media", "tools"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("no git")
        tracked = set(r.stdout.split())
        for n in self.EXPECTED:
            self.assertIn("docs/media/" + n, tracked)
        for n in ("tools/render_media.py", "tools/fonts/LICENSE.txt",
                  "tools/fonts/Px437_IBM_VGA_8x16.ttf"):
            self.assertIn(n, tracked)

    def test_pngs(self):
        for n in sorted(self.EXPECTED):
            if not n.endswith(".png"):
                continue
            with Image.open(os.path.join(MEDIA, n)) as im:
                im.load()
                self.assertEqual(im.format, "PNG", n)
                self.assertEqual(im.width, 640, n)
                if n != "statusbar.png":
                    self.assertEqual(im.height, 416, n)
                else:
                    self.assertLess(im.height, 416)

    def test_gifs(self):
        for n in ("dialin.gif", "browse.gif", "goodbye.gif"):
            p = os.path.join(MEDIA, n)
            self.assertLess(os.path.getsize(p), 3 * 1024 * 1024, n)
            with Image.open(p) as im:
                self.assertEqual(im.format, "GIF")
                self.assertEqual(im.size, (640, 416), n)
                self.assertTrue(im.is_animated, n)
                self.assertGreater(im.n_frames, 1, n)
                self.assertEqual(im.info.get("loop"), 0, n)
                total = 0
                for i in range(im.n_frames):
                    im.seek(i)
                    total += im.info.get("duration", 0)
                self.assertGreater(total, 2000, n)

    def test_only_vga_colours(self):
        for n in sorted(self.EXPECTED):
            for i, fr in enumerate(frames_of(os.path.join(MEDIA, n))):
                cols = {c for _, c in fr.getcolors(1 << 16)}
                self.assertLessEqual(cols, VGA, f"{n} frame {i}")

    def test_image_text_clean_and_private(self):
        seen = {}
        for n in sorted(self.EXPECTED):
            texts = set()
            for fr in frames_of(os.path.join(MEDIA, n)):
                texts.add(image_text(fr))
            seen[n] = texts
            for t in texts:
                self.assertEqual(offences(t), [], n)
                check_private(self, t, n)
        self.assertTrue(any("NO CARRIER" in t for t in seen["goodbye.gif"]))
        self.assertTrue(any("CONNECT" in t for t in seen["dialin.gif"]))
        self.assertTrue(any("Command »" in t for t in seen["dialin.gif"]))
        self.assertTrue(any("Page 1 of" in t for t in seen["browse.gif"]))
        self.assertTrue(any("Page 1 of" in t for t in seen["gfiles.png"]))
        self.assertTrue(any("Main Board Command?" in t for t in seen["pcboard.png"]))
        self.assertTrue(any("[Main Menu]" in t for t in seen["telegard.png"]))
        self.assertTrue(any("[Main]" in t for t in seen["renegade.png"]))


class Text(unittest.TestCase):
    def files(self):
        out = [os.path.join(ROOT, "README.md"), os.path.join(ROOT, "tests", "test_media.py")]
        for d in ("tools", "docs"):
            for dp, _, fs in os.walk(os.path.join(ROOT, d)):
                out += [os.path.join(dp, f) for f in fs
                        if f.endswith((".py", ".txt", ".TXT", ".md"))]
        return out

    def test_no_seven_words(self):
        for p in self.files():
            with open(p, encoding="utf-8", errors="replace") as f:
                self.assertEqual(offences(f.read()), [], p)

    def test_no_private_paths_in_tools_or_readme(self):
        for p in [os.path.join(ROOT, "README.md"), SCRIPT]:
            with open(p, encoding="utf-8") as f:
                text = f.read()
            for n in private_needles():
                self.assertNotIn(n, text, p)

    def test_readme(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            text = f.read()
        heads = re.findall(r"(?m)^## .*", text)
        self.assertEqual(heads[:3], ["## Screenshots", "## Install", "## Run"])
        sec = re.search(r"(?ms)^## Screenshots\n(.*?)(?=^## )", text).group(1)
        for n in os.listdir(MEDIA):
            self.assertRegex(sec, r"!\[[^\]]*\]\(docs/media/%s\)" % re.escape(n))
        self.assertIn("pip install '.[media]'", sec)
        self.assertIn("python3 tools/render_media.py --out docs/media", sec)
        self.assertIn("Px437 IBM VGA 8x16 from The Ultimate Oldschool PC Font Pack by VileR "
                      "(int10h.org), CC BY-SA 4.0", sec)

    def test_licence(self):
        with open(os.path.join(ROOT, "tools", "fonts", "LICENSE.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Attribution-ShareAlike 4.0", text)
        self.assertTrue(os.path.getsize(FONT) > 1000)
        with open(FONT, "rb") as f:
            self.assertIn(f.read(4), (b"\x00\x01\x00\x00", b"true", b"OTTO"))

    def test_app_has_no_pillow(self):
        for dp, _, fs in os.walk(os.path.join(ROOT, "courierhst")):
            for f in fs:
                if f.endswith(".py"):
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        self.assertNotRegex(fh.read(), r"(?m)^\s*(import|from)\s+PIL\b", f)
        r = subprocess.run([sys.executable, "-c",
                            "import sys, courierhst.__main__; print('PIL' in sys.modules)"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "False", r.stderr)

    def test_renderer_uses_required_flags(self):
        with open(SCRIPT, encoding="utf-8") as f:
            text = f.read()
        for flag in ("--no-center", "--noise", "--seed", "--warp", "--handle"):
            self.assertIn(flag, text)
        self.assertIn("COLS, ROWS = 80, 26", text)
        self.assertIn("CW, CH = 8, 16", text)


def hack_files():
    return sorted(glob.glob(os.path.join(HACK, "*.TXT")))


def boxes(lines):
    """Yield runs of (lineno, line) that form a box: top, sides, bottom."""
    top = re.compile(r"^( *)([.#])([-#]{10,})([.#])$")
    i = 0
    while i < len(lines):
        m = top.match(lines[i])
        if m and (m.group(2) == "." or set(lines[i].strip()) == {"#"}):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not top.match(lines[j]) \
                    and not lines[j].lstrip().startswith("`"):
                j += 1
            if j < len(lines) and (lines[j].lstrip().startswith("`") or top.match(lines[j])):
                yield [(k + 1, lines[k]) for k in range(i, j + 1)]
                i = j + 1
                continue
        i += 1


class HackphrkBoxes(unittest.TestCase):
    BOXED = {"BOXCOLRS.TXT", "HACKETHC.TXT", "PHRKHIST.TXT", "SYSOPWAR.TXT"}

    def read(self, p):
        with open(p, encoding="utf-8") as f:
            return f.read().split("\n")

    def test_line_length(self):
        for p in hack_files():
            for n, line in enumerate(self.read(p), 1):
                self.assertLessEqual(len(line.rstrip("\r")), 79, f"{os.path.basename(p)}:{n}")

    def test_boxes_found(self):
        found = {os.path.basename(p) for p in hack_files() if list(boxes(self.read(p)))}
        self.assertLessEqual(self.BOXED, found)

    def test_boxes_line_up(self):
        for p in hack_files():
            for box in boxes(self.read(p)):
                where = f"{os.path.basename(p)}:{box[0][0]}"
                left = {len(l) - len(l.lstrip()) for _, l in box}
                right = {len(l.rstrip()) for _, l in box}
                self.assertEqual(len(left), 1, (where, box))
                self.assertEqual(len(right), 1, (where, box))
                for n, l in box[1:-1]:
                    s = l.strip()
                    self.assertTrue(s[0] == s[-1] or s[:2] == s[-2:], (where, n, l))
                    self.assertIn(s[0], "|#", (where, n, l))

    def test_box_self_check(self):
        good = [" .----------.", " | abc      |", " `----------'"]
        bad = [" .----------.", " | abc       |", " `----------'"]
        self.assertEqual(len(list(boxes(good))), 1)
        b = list(boxes(bad))[0]
        self.assertGreater(len({len(l.rstrip()) for _, l in b}), 1)

    def test_diff_vs_main_is_spacing_only(self):
        r = subprocess.run(["git", "diff", "--name-only", "main", "--", HACK], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("no main ref")
        for rel in r.stdout.split():
            old = subprocess.run(["git", "show", "main:" + rel], cwd=ROOT,
                                 capture_output=True, text=True)
            if old.returncode != 0:
                self.fail(f"new file under hackphrk: {rel}")
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                new = f.read().split("\n")
            old = old.stdout.split("\n")
            self.assertEqual(len(old), len(new), rel)
            for a, b in zip(old, new):
                self.assertEqual(a.replace(" ", ""), b.replace(" ", ""), rel)


if __name__ == "__main__":
    unittest.main()
