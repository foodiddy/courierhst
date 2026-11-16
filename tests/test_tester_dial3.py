"""Tester acceptance checks for DIAL-3: dialer footer fix, dialer media, README."""
import fcntl
import os
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
from unittest import mock

from courierhst import ansi, modem
from courierhst.dialer import Dialer
from courierhst.modem import Line

try:
    import pyte
except ImportError:  # pragma: no cover
    pyte = None
try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None
try:
    import pty
except ImportError:  # pragma: no cover
    pty = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "docs", "media")
FOOTER = "Simulated scan: every number and result is made up."
NEED = pyte is None or Image is None
SKIP = "needs pip install '.[media]'"


class Stop(Exception):
    pass


class Out:
    def __init__(self):
        self.parts = []

    def write(self, s):
        self.parts.append(s)

    def flush(self):
        pass

    def fileno(self):
        return 99

    def value(self):
        return "".join(self.parts)


def first_paint(rows, status=True):
    """Real Line on a fake rows x 80 terminal; stop at the first pause."""
    out = Out()
    with mock.patch.object(modem.os, "get_terminal_size",
                           return_value=os.terminal_size((80, rows))):
        line = Line(warp=1000, out=out, noise=0, exit_on_key=False,
                    status=status, center=False)
        line._layout()
    d = Dialer(line, random.Random(4))

    def pause(s):
        raise Stop()
    line.pause = pause
    line.send = lambda *a, **k: (_ for _ in ()).throw(AssertionError("send"))
    try:
        d.run()
    except Stop:
        pass
    line._flush()
    return line, out.value()


@unittest.skipIf(pyte is None, SKIP)
class FooterRealLine(unittest.TestCase):
    def screen(self, rows, raw):
        sc = pyte.Screen(80, rows)
        pyte.Stream(sc).feed(raw)
        return sc.display

    def test_footer_visible(self):
        for rows, status in ((25, True), (26, True), (30, True), (25, False),
                             (24, False)):
            with self.subTest(rows=rows, status=status):
                line, raw = first_paint(rows, status)
                disp = self.screen(rows, raw)
                frow = min(25, line.height)
                self.assertIn(FOOTER, disp[line.top - 1 + frow - 1])
                self.assertEqual(sum(FOOTER in r for r in disp), 1)
                # log box bottom border on window row 23, under the LOG top
                self.assertIn("LOG", disp[line.top - 1 + 18 - 1])
                bottom = disp[line.top - 1 + 23 - 1]
                self.assertTrue(bottom.startswith(bottom[0]) and
                                bottom[0] not in " ", bottom)
                self.assertNotIn(FOOTER, bottom)
                if status:
                    self.assertEqual(line.status_row, line.bottom + 1)
                    self.assertNotIn(FOOTER, disp[line.status_row - 1])
                    self.assertIn("GRiDSWEEP", disp[line.status_row - 1])

    def test_stock_80x25_height_24(self):
        line, raw = first_paint(25, True)
        self.assertEqual(line.height, 24)
        disp = self.screen(25, raw)
        self.assertIn(FOOTER, disp[23])
        self.assertNotIn(FOOTER, disp[24])

    def test_log_rows_inside_box(self):
        line, raw = first_paint(26, True)
        disp = self.screen(26, raw)
        self.assertIn("LOG", disp[17])
        for r in range(18, 22):          # window rows 19..22: log lines
            self.assertNotEqual(disp[r][0], " ", r)
            self.assertNotEqual(disp[r][78], " ", r)
        self.assertNotEqual(disp[22][0], disp[18][0], "row 23 not a border")
        self.assertEqual(disp[23].strip(), "", "row 24 should be blank")


@unittest.skipIf(pyte is None or pty is None, SKIP)
class FooterPty(unittest.TestCase):
    """The whole app, --dialer, in a stock 80x25 pty with the status bar."""

    def test_footer_on_80x25(self):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 25, 80, 0, 0))
        env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
        proc = subprocess.Popen(
            [sys.executable, "-m", "courierhst", "--dialer", "--warp", "20",
             "--seed", "3", "--noise", "0", "--no-exit-on-key"],
            stdin=slave, stdout=slave, stderr=slave, env=env, cwd=ROOT,
            close_fds=True)
        os.close(slave)
        sc = pyte.Screen(80, 25)
        st = pyte.ByteStream(sc)
        try:
            end = time.monotonic() + 20
            ok = False
            while time.monotonic() < end and not ok:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    try:
                        st.feed(os.read(master, 65536))
                    except OSError:
                        break
                ok = any(FOOTER in row for row in sc.display) and \
                    "GRiDSWEEP" in sc.display[0] + sc.display[1]
            self.assertTrue(ok, "\n".join(sc.display))
            fr = [i for i, row in enumerate(sc.display) if FOOTER in row]
            self.assertEqual(fr, [23])
            self.assertIn("GRiDSWEEP", sc.display[24])
        finally:
            proc.kill()
            proc.wait()
            os.close(master)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True)


@unittest.skipIf(NEED, SKIP)
class Media(unittest.TestCase):
    def test_png(self):
        with Image.open(os.path.join(MEDIA, "dialer.png")) as im:
            self.assertEqual(im.size, (640, 416))

    def test_gif(self):
        p = os.path.join(MEDIA, "dialer.gif")
        self.assertLess(os.path.getsize(p), 3 * 1024 * 1024)
        with Image.open(p) as im:
            self.assertEqual(im.size[0], 640)
            self.assertTrue(im.is_animated)
            total, frames = 0, set()
            for i in range(im.n_frames):
                im.seek(i)
                total += im.info.get("duration", 0)
                frames.add(im.convert("RGB").tobytes())
        self.assertGreaterEqual(total, 8000)
        self.assertLessEqual(total, 15500)
        self.assertGreaterEqual(len(frames), 5)

    def test_no_scratch_files(self):
        r = git("ls-files")
        bad = [f for f in r.stdout.split() if re.search(
            r"(scratch|\.orig$|\.rej$|\.tmp$|~$|\.pyc$|header-src)", f)]
        self.assertEqual(bad, [])


@unittest.skipIf(NEED, SKIP)
class Render(unittest.TestCase):
    """render_media --only dialer.* writes only into --out."""

    def render(self, name):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        before = git("status", "--porcelain", "--", "docs").stdout
        r = subprocess.run([sys.executable, "tools/render_media.py", "--out",
                            tmp, "--only", name], cwd=ROOT,
                           capture_output=True, text=True, timeout=400)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.listdir(tmp), [name])
        self.assertEqual(git("status", "--porcelain", "--", "docs").stdout,
                         before)
        return os.path.join(tmp, name)

    def screen_of(self, path):
        with Image.open(path) as im:
            return im.convert("RGB")

    def test_png_renders(self):
        p = self.render("dialer.png")
        with Image.open(p) as im:
            self.assertEqual(im.size, (640, 416))
        # cyan carrier colour present (CARRIER cell / log entry)
        with Image.open(p) as im:
            cols = {c for _, c in im.convert("RGB").getcolors(1 << 16)}
        self.assertTrue(any(r < 0x60 and g > 0xC0 and b > 0xC0
                            for r, g, b in cols), "no bright cyan")
        with open(p, "rb") as a, open(os.path.join(MEDIA, "dialer.png"),
                                       "rb") as b:
            self.assertEqual(a.read(), b.read(), "committed PNG is stale")

    def test_gif_renders(self):
        p = self.render("dialer.gif")
        self.assertLess(os.path.getsize(p), 3 * 1024 * 1024)
        with Image.open(p) as im:
            self.assertTrue(im.is_animated)
            self.assertEqual(im.size[0], 640)


@unittest.skipIf(NEED, SKIP)
class DialerScreenContent(unittest.TestCase):
    """The PNG job's screen text: mid scan, CARRIER, several log results."""

    def test_capture_text(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        self.addCleanup(sys.path.remove, os.path.join(ROOT, "tools"))
        import render_media as rm
        chunks = rm.capture(rm.DIALER_SEED, "renegade", 50,
                            stop=rm.has("CARRIER", "Dialed       10"),
                            idle=0.9, extra=rm.DIALER_ARGS)
        sc = rm.last_screen(chunks)
        text = "\n".join(sc.display)
        self.assertIn("GRiDSWEEP", text)
        self.assertIn("CARRIER", text)
        self.assertIn(FOOTER, sc.display[24])
        log = [r for r in sc.display[18:22] if re.search(r"555-01\d\d", r)]
        self.assertGreaterEqual(len(log), 3, text)
        self.assertNotIn("SCAN COMPLETE", text)
        for m in re.findall(r"\d{3}-\d{4}", text):
            self.assertRegex(m, r"^555-01\d\d$")


class Readme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            cls.text = f.read()

    def test_header_first_line(self):
        self.assertIn("docs/media/header.jpg", self.text.splitlines()[0])

    def test_flags_and_keys(self):
        for flag in ("--dialer", "--bbs", "--rotate"):
            self.assertIn(flag, self.text)
        self.assertRegex(self.text, r"`courierhst --dialer --rotate \d+`")
        self.assertRegex(self.text, r"`courierhst --bbs`")
        self.assertRegex(self.text, r"`courierhst --dialer`")
        self.assertIn("--rotate MINUTES", self.text)
        self.assertRegex(self.text, r"`d`[^\n]*dialer")
        self.assertRegex(self.text, r"`b`[^\n]*BBS")
        self.assertRegex(self.text, r"--no-exit-on-key[^\n]*`d` and `b`")

    def test_dialer_section(self):
        m = re.search(r"^## Dialer screensaver\n(.*?)(?=^## )", self.text,
                      re.S | re.M)
        self.assertTrue(m)
        sec = m.group(1)
        self.assertIn("GRiDSWEEP", sec)
        self.assertIn("1993", sec)
        self.assertIn("555-01xx", sec)
        self.assertRegex(sec, r"no real calls|never .*call")

    def test_media_under_screenshots(self):
        m = re.search(r"^## Screenshots\n(.*?)(?=^## )", self.text,
                      re.S | re.M)
        self.assertTrue(m)
        for n in ("dialer.png", "dialer.gif"):
            self.assertRegex(m.group(1), r"!\[[^\]]+\]\(docs/media/" +
                             re.escape(n) + r"\)")

    def test_install_kept(self):
        self.assertIn("pip install", self.text)
        self.assertIn("python3 -m courierhst", self.text)

    def test_no_real_dialer_names(self):
        tracked = git("ls-files").stdout.split()
        names = re.compile(r"tone\s*loc|thc[-\s]*scan|phone\s*tag|"
                           r"a-?dial|blue\s*beep|warvox|ipkiss|"
                           r"demon\s*dialer|super\s*dialer", re.I)
        for f in ["README.md", "courierhst/dialer.py", "tools/render_media.py"]:
            if f not in tracked:
                continue
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                self.assertIsNone(names.search(fh.read()), f)


if __name__ == "__main__":
    unittest.main()
