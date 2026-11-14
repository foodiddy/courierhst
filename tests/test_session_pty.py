"""Run the whole program in a pty and check the screen with a VT emulator."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import os
import pty
import select
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZES = [(80, 26), (80, 24), (120, 40)]
SEEDS = range(1, 21)
BBS_COLS, BBS_ROWS = 80, 25


def geometry(cols, rows):
    """Mirror of Line._layout for the default (centered, status) mode."""
    top = max(0, (rows - 26) // 2) + 1
    left = max(0, (cols - BBS_COLS) // 2)
    height = max(3, min(BBS_ROWS, rows - top + 1 - 1))
    bottom = top + height - 1
    return left, top, bottom, bottom + 1


def run_session(seed, cols, rows, check, timeout=180):
    """Run courierhst in a pty; call check(screen) after every chunk."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "courierhst", "--seed", str(seed), "--warp", "60",
         "--xfer-speedup", "2000", "--calls", "2", "--no-exit-on-key",
         "--noise", "0"],
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


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class SessionPty(unittest.TestCase):
    def one(self, seed, cols, rows):
        left, top, bottom, status = geometry(cols, rows)

        def check(screen):
            for y in range(rows):
                line = screen.buffer[y]
                for x in range(cols):
                    if line[x].data.strip() == "":
                        continue
                    in_window = (top - 1 <= y <= bottom - 1
                                 and left <= x < left + BBS_COLS)
                    in_status = (y == status - 1
                                 and left <= x < left + BBS_COLS - 1)
                    if not (in_window or in_status):
                        raise AssertionError(
                            f"glyph outside window at x={x} y={y}: {line[x].data!r}")
        code, text = run_session(seed, cols, rows, check)
        if "Traceback" in text:
            raise AssertionError("traceback:\n" + text[-1500:])
        if code != 0:
            raise AssertionError(f"exit code {code}\n{text[-800:]}")
        # terminal left sane: scroll region reset, SGR reset, cursor shown
        if not text.endswith("\x1b[r\x1b[0m\x1b[2J\x1b[H\x1b[?25h"):
            raise AssertionError(f"bad restore: {text[-60:]!r}")

    def test_sessions(self):
        cases = [(s, c, r) for c, r in SIZES for s in SEEDS]
        with ThreadPoolExecutor(max_workers=min(16, os.cpu_count() or 4)) as ex:
            futs = [(case, ex.submit(self.one, *case)) for case in cases]
        for (seed, cols, rows), f in futs:
            with self.subTest(seed=seed, size=f"{cols}x{rows}"):
                f.result()


@unittest.skipIf(pyte is None, "pyte not installed (pip install '.[test]')")
class Restore(unittest.TestCase):
    def run_py(self, code):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        p = subprocess.Popen([sys.executable, "-c", code], stdin=slave,
                             stdout=slave, stderr=slave, cwd=ROOT,
                             env=dict(os.environ, PYTHONPATH=ROOT))
        os.close(slave)
        out = b""
        while True:
            try:
                d = os.read(master, 65536)
            except OSError:
                break
            if not d:
                break
            out += d
        os.close(master)
        p.wait()
        return out.decode("utf-8", "replace")

    def test_restored_after_exception_and_keypress(self):
        for exc in ("RuntimeError('x')", "KeyPressed()", "KeyboardInterrupt()"):
            code = (
                "import sys,termios\n"
                "from courierhst.modem import Line, KeyPressed\n"
                "before=termios.tcgetattr(0)\n"
                "try:\n"
                "  with Line() as l:\n"
                f"    l.send('hi'); raise {exc}\n"
                "except BaseException: pass\n"
                "print('TC_OK' if termios.tcgetattr(0)==before else 'TC_BAD')\n")
            out = self.run_py(code)
            self.assertIn("TC_OK", out, exc)
            tail = out.split("\x1b[r", 1)
            self.assertEqual(len(tail), 2, exc)
            self.assertIn("\x1b[0m", tail[1])
            self.assertIn("\x1b[?25h", tail[1])


if __name__ == "__main__":
    unittest.main()
