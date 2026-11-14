"""Independent acceptance checks (Tester, round 1).

These complement test_ansi / test_modem / test_session_pty: CLI smoke tests,
real-tty metering, terminal restore of the *real program* after Ctrl-C and a
keypress, the Zmodem box at short terminal sizes, narrow terminals and resize.
Tests that need a VT emulator skip cleanly when pyte is missing.
"""
import fcntl
import inspect
import io
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import unittest

try:
    import pyte
except ImportError:  # pragma: no cover
    pyte = None

from courierhst import doors
from courierhst.modem import Line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
FAST = ["--warp", "60", "--xfer-speedup", "2000", "--no-exit-on-key",
        "--noise", "0"]
NEEDS_PYTE = unittest.skipIf(pyte is None,
                             "pyte not installed (pip install '.[test]')")


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


class Pty:
    """Spawn a command on a pty; parent keeps the slave open to inspect it."""

    def __init__(self, argv, cols=80, rows=26):
        self.master, self.slave = pty.openpty()
        set_size(self.slave, cols, rows)
        self.before = termios.tcgetattr(self.slave)
        self.proc = subprocess.Popen(
            argv, stdin=self.slave, stdout=self.slave, stderr=self.slave,
            env=ENV, cwd=ROOT, close_fds=True, start_new_session=True)
        self.raw = bytearray()
        self.chunks = []  # (time, nbytes)
        self.screen = None
        if pyte is not None:
            self.screen = pyte.Screen(cols, rows)
            self.stream = pyte.ByteStream(self.screen)

    def pump(self, seconds, on_chunk=None):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            r, _, _ = select.select([self.master], [], [], 0.05)
            if r:
                try:
                    d = os.read(self.master, 65536)
                except OSError:
                    return
                if not d:
                    return
                self.raw += d
                self.chunks.append((time.monotonic(), len(d)))
                if self.screen is not None:
                    self.stream.feed(d)
                    if on_chunk:
                        on_chunk(self.screen)
            elif self.proc.poll() is not None:
                return

    def finish(self, timeout=120, on_chunk=None):
        end = time.monotonic() + timeout
        while self.proc.poll() is None and time.monotonic() < end:
            self.pump(0.5, on_chunk)
        self.pump(0.3, on_chunk)  # drain
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
            raise AssertionError("timed out")
        return self.proc.returncode

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        for fd in (self.master, self.slave):
            try:
                os.close(fd)
            except OSError:
                pass

    @property
    def text(self):
        return bytes(self.raw).decode("utf-8", "replace")


def prog(*args):
    return [sys.executable, "-m", "courierhst", *args]


class Cli(unittest.TestCase):
    def test_help(self):
        p = subprocess.run(prog("--help"), capture_output=True, text=True,
                           cwd=ROOT, env=ENV, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        for flag in ("--bps", "--handle", "--seed", "--no-center",
                     "--no-status", "--noise", "--xfer-speedup",
                     "--no-exit-on-key", "--calls", "--warp"):
            self.assertIn(flag, p.stdout)

    def test_non_tty_stdout_is_clean_error(self):
        p = subprocess.run(prog("--calls", "1"), capture_output=True, text=True,
                           cwd=ROOT, env=ENV, timeout=30, stdin=subprocess.DEVNULL)
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("Traceback", p.stderr)
        self.assertIn("terminal", p.stderr)

    def test_trade_has_no_credits_arg(self):
        self.assertNotIn("credits", inspect.signature(doors.trade).parameters)


class NonTtyLine(unittest.TestCase):
    def test_non_tty_stdin_pause_and_send(self):
        class Out(io.StringIO):
            def fileno(self):
                raise OSError

        old = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            line = Line(out=Out(), noise=0, warp=100)
            self.assertIsNone(line.fd_in)
            with line:
                line.pause(1)       # must sleep, not select on None
                line.sendln("|15hello")
        finally:
            sys.stdin = old
        self.assertIn("hello", line.out.getvalue())
        self.assertTrue(line.out.getvalue().endswith("\x1b[?25h"))

    def test_multibyte_glyphs_cost_one_char(self):
        class Out(io.StringIO):
            def fileno(self):
                raise OSError
        line = Line(out=Out(), noise=0, bps=14400)
        t0 = time.monotonic()
        line.send("█▓░─" * 360)  # 1440 glyphs
        self.assertAlmostEqual(time.monotonic() - t0, 1.0, delta=0.1)


class RealTtyStreaming(unittest.TestCase):
    """Metering through an actual pty: output trickles, it doesn't burst."""

    def test_line_streams_at_14400_on_a_pty(self):
        code = ("from courierhst.modem import Line\n"
                "import time\n"
                "with Line(noise=0, status=False) as l:\n"
                "    l.pause(0.3)\n"
                "    l.send('x' * 2880)\n")
        p = Pty([sys.executable, "-c", code], 80, 26)
        try:
            self.assertEqual(p.finish(30), 0, p.text[-500:])
            xs = [(t, n) for t, n in p.chunks]
            # find the payload window: from first to last chunk carrying 'x'
            self.assertIn("x" * 50, p.text)
        finally:
            p.close()
        # bytes arrive spread over ~2s, in many chunks
        span = xs[-1][0] - xs[0][0]
        self.assertGreater(span, 1.7, span)
        self.assertLess(span, 3.0, span)
        self.assertGreater(len(xs), 20, "output came in a burst")

    def test_default_program_trickles(self):
        """Real-time default run: never more than ~14.4k worth in any second
        beyond local UI redraws, and it keeps producing output."""
        p = Pty(prog("--seed", "3", "--no-exit-on-key"), 80, 26)
        try:
            p.pump(12)
        finally:
            p.proc.send_signal(signal.SIGINT)
            try:
                p.finish(10)
            finally:
                p.close()
        chunks = [c for c in p.chunks]
        self.assertTrue(chunks)
        t0 = chunks[0][0]
        buckets = {}
        for t, n in chunks:
            buckets[int(t - t0)] = buckets.get(int(t - t0), 0) + n
        self.assertGreaterEqual(len(buckets), 8, buckets)  # keeps streaming
        # 1440 cps of BBS text (UTF-8 box glyphs can be 3 bytes each) plus
        # local terminal-program UI; a burst of a whole screen would be >>.
        self.assertLess(max(buckets.values()), 1440 * 3 + 3000, buckets)


class Restore(unittest.TestCase):
    """The real program must leave the tty as it found it."""

    def check_restored(self, p):
        after = termios.tcgetattr(p.slave)
        self.assertEqual(after[3] & (termios.ECHO | termios.ICANON),
                         p.before[3] & (termios.ECHO | termios.ICANON))
        self.assertEqual(after, p.before)
        self.assertNotIn("Traceback", p.text)
        tail = p.text.rsplit("\x1b[r", 1)
        self.assertEqual(len(tail), 2, "scroll region never reset")
        self.assertIn("\x1b[0m", tail[1])
        self.assertIn("\x1b[?25h", tail[1])
        self.assertNotIn("\x1b[?25l", tail[1])

    def test_ctrl_c_at_various_points(self):
        # warp 60 + slow xfer so later delays tend to land mid-transfer
        for delay in (0.3, 1.5, 4, 8):
            with self.subTest(delay=delay):
                p = Pty(prog("--seed", "5", "--warp", "60", "--xfer-speedup",
                             "5", "--no-exit-on-key", "--noise", "0"))
                try:
                    p.pump(delay)
                    p.proc.send_signal(signal.SIGINT)
                    self.assertEqual(p.finish(20), 0, p.text[-800:])
                    self.check_restored(p)
                finally:
                    p.close()

    def test_ctrl_c_mid_zmodem(self):
        p = Pty(prog("--seed", "5", "--warp", "60", "--xfer-speedup", "1",
                     "--no-exit-on-key", "--noise", "0"))
        try:
            end = time.monotonic() + 90
            while "Zmodem download" not in p.text and time.monotonic() < end:
                if p.proc.poll() is not None:
                    break
                p.pump(0.2)
            self.assertIn("Zmodem download", p.text, "no transfer reached")
            p.pump(0.5)
            p.proc.send_signal(signal.SIGINT)
            self.assertEqual(p.finish(20), 0, p.text[-800:])
            self.check_restored(p)
        finally:
            p.close()

    def test_keypress_exits_and_restores(self):
        p = Pty(prog("--seed", "2", "--warp", "20", "--noise", "0"))
        try:
            p.pump(2)
            self.assertIsNone(p.proc.poll(), "exited before the key")
            os.write(p.master, b"q")
            self.assertEqual(p.finish(10), 0, p.text[-800:])
            self.check_restored(p)
        finally:
            p.close()


def window_geometry(cols, rows):
    top = max(0, (rows - 26) // 2) + 1
    left = max(0, (cols - 80) // 2)
    height = max(3, min(25, rows - top))
    return left, top, top + height - 1


@NEEDS_PYTE
class ZmodemBox(unittest.TestCase):
    """The transfer window must stay intact when the BBS window is full and
    sits at the bottom of a short terminal (each '\\n' scrolls)."""

    SCRIPT = (
        "import random, sys\n"
        "from courierhst.modem import Line\n"
        "from courierhst.bbs import Session\n"
        "with Line(noise=0, warp=200, exit_on_key=False) as l:\n"
        "    s = Session(l, random.Random(1), 'tester', xfer_speedup=400)\n"
        "    for i in range(40):\n"
        "        l.local('|07line %d\\n' % i)\n"
        "    s.transfer([('ONE.ZIP', 40), ('TWO.ZIP', 80)])\n"
        "    l._flush()\n"
        "    sys.stdin.read(1)\n"   # hold the screen until the parent looks
    )

    def snapshot(self, cols, rows):
        p = Pty([sys.executable, "-c", self.SCRIPT], cols, rows)
        bad = []

        def check(screen):
            # frame must never be torn while the transfer animates
            lines = ["".join(screen.buffer[y][x].data for x in range(cols))
                     for y in range(rows)]
            tops = [y for y, s in enumerate(lines) if "╔" in s]
            if tops:
                y0 = tops[-1]
                if y0 + 6 < rows and "╚" in lines[y0 + 6]:
                    for k in range(1, 6):
                        if lines[y0 + k].count("║") != 2:
                            bad.append((y0, k, lines[y0 + k]))
        try:
            end = time.monotonic() + 60
            while time.monotonic() < end and "100%" not in p.text:
                p.pump(0.2, check)
            p.pump(0.6, check)
            lines = ["".join(p.screen.buffer[y][x].data for x in range(cols))
                     for y in range(rows)]
            os.write(p.master, b"\n")
            p.finish(10)
        finally:
            p.close()
        return lines, bad, p.text

    def test_box_at_short_sizes(self):
        for cols, rows in ((80, 26), (80, 24), (80, 20), (120, 40), (100, 22)):
            with self.subTest(size=f"{cols}x{rows}"):
                lines, bad, text = self.snapshot(cols, rows)
                self.assertNotIn("Traceback", text)
                left, top, bottom = window_geometry(cols, rows)
                tops = [y for y, s in enumerate(lines) if "╔" in s]
                bots = [y for y, s in enumerate(lines) if "╚" in s]
                self.assertEqual(len(tops), 1, "\n".join(lines))
                self.assertEqual(len(bots), 1, "\n".join(lines))
                y0, y1 = tops[0], bots[0]
                self.assertEqual(y1 - y0, 6, "\n".join(lines))
                self.assertGreaterEqual(y0, top - 1)
                self.assertLessEqual(y1, bottom - 1)
                for y in range(y0 + 1, y1):
                    self.assertEqual(lines[y].count("║"), 2,
                                     f"row {y}:\n" + "\n".join(lines))
                    a, b = lines[y].index("║"), lines[y].rindex("║")
                    self.assertEqual(a, lines[y0].index("╔"))
                    self.assertEqual(b, lines[y0].index("╗"))
                box = "\n".join(lines[y0:y1 + 1])
                self.assertIn("Zmodem download", box)
                self.assertIn("TWO.ZIP", box)
                self.assertIn("100%", box)
                self.assertEqual(bad, [], bad[:3])


@NEEDS_PYTE
class OddTerminals(unittest.TestCase):
    def run_one(self, cols, rows, seed=1, resize_to=None):
        p = Pty(prog("--seed", str(seed), "--calls", "1", *FAST), cols, rows)
        try:
            if resize_to:
                p.pump(2)
                set_size(p.slave, *resize_to)
                os.killpg(p.proc.pid, signal.SIGWINCH)
            code = p.finish(120)
        finally:
            p.close()
        return code, p.text

    def test_narrow_and_short(self):
        for cols, rows in ((40, 20), (60, 15), (79, 25), (80, 10)):
            with self.subTest(size=f"{cols}x{rows}"):
                code, text = self.run_one(cols, rows)
                self.assertNotIn("Traceback", text, text[-1500:])
                self.assertEqual(code, 0)

    def test_resize_mid_run(self):
        for a, b in (((120, 40), (80, 24)), ((80, 24), (132, 50))):
            with self.subTest(frm=a, to=b):
                code, text = self.run_one(*a, resize_to=b)
                self.assertNotIn("Traceback", text, text[-1500:])
                self.assertEqual(code, 0)


@NEEDS_PYTE
class StatusRowOwnership(unittest.TestCase):
    """Only the status bar is ever drawn on the status row, and it stays
    within min(80, cols) - 1 columns of the window's left edge."""

    def test_status_row(self):
        for cols, rows, seed in ((80, 24, 4), (120, 40, 7), (90, 26, 9)):
            with self.subTest(size=f"{cols}x{rows}"):
                left, top, bottom = window_geometry(cols, rows)
                srow = bottom  # 0-based index of the row after the window
                seen = set()
                errs = []

                def check(screen):
                    s = "".join(screen.buffer[srow][x].data
                                for x in range(cols))
                    if s.strip():
                        seen.add(s.strip()[:12])
                        last = max(i for i, ch in enumerate(s) if ch != " ")
                        if last >= left + 79 or s[:left].strip():
                            errs.append(s)
                        if "ALT-Z" not in s:
                            errs.append(s)
                p = Pty(prog("--seed", str(seed), "--calls", "1", *FAST),
                        cols, rows)
                try:
                    self.assertEqual(p.finish(120, check), 0)
                finally:
                    p.close()
                self.assertTrue(seen, "status bar never drawn")
                self.assertEqual(errs[:3], [])


if __name__ == "__main__":
    unittest.main()
