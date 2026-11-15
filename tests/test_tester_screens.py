"""Tester: DIAL-2 screen switching (d / b / --rotate), CLI and key reading."""
import contextlib
import io
import os
import random
import re
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from courierhst import __main__ as cli
from courierhst import screens
from courierhst.dialer import Dialer
from courierhst.modem import KeyPressed, Line, Rotate

try:
    import pty
except ImportError:  # pragma: no cover
    pty = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ fakes
class Stop(Exception):
    """Ends a run_screens loop from a fake."""


class FLine:
    def __init__(self):
        self.status_text = None
        self.rotate_at = None
        self.pauses = []
        self.pause_script = []  # exceptions raised by pause(), in order
        self.arms = []          # rotate_at values seen per screen entry

    def pause(self, secs):
        self.pauses.append(secs)
        if self.pause_script:
            exc = self.pause_script.pop(0)
            if exc is not None:
                raise exc


class FRng:
    def uniform(self, a, b):
        return (a + b) / 2


class Log:
    """Records which screen ran, in order."""

    def __init__(self):
        self.events = []


class FDialer:
    def __init__(self, line, log, script):
        self.line, self.log, self.script = line, log, script
        self.position = 0  # scan progress that must survive switches
        self.runs = 0

    def run(self):
        self.runs += 1
        self.position += 10
        self.line.status_text = "GRiDSWEEP scanning"
        self.log.events.append(("dialer", self.line.rotate_at,
                                self.line.status_text))
        if not self.script:
            raise Stop()
        raise self.script.pop(0)


class SessionFactory:
    def __init__(self, line, log, script):
        self.line, self.log, self.script = line, log, script
        self.made = []

    def __call__(self):
        fac = self

        class S:
            def run(self):
                fac.log.events.append(("bbs", fac.line.rotate_at,
                                       fac.line.status_text, id(self)))
                if not fac.script:
                    raise Stop()
                exc = fac.script.pop(0)
                if exc is not None:
                    raise exc
        s = S()
        self.made.append(s)
        return s


def drive(start, bbs=(), dial=(), calls=0, rotate=None, warp=1.0,
          pauses=()):
    line, log = FLine(), Log()
    line.pause_script = list(pauses)
    fac = SessionFactory(line, log, list(bbs))
    d = FDialer(line, log, list(dial))
    try:
        rc = screens.run_screens(line, FRng(), start, rotate, calls, fac, d,
                                 warp)
    except Stop:
        rc = "stopped"
    return rc, line, log, fac, d


def screens_seen(log):
    return [e[0] for e in log.events]


# ------------------------------------------------------- run_screens tests
class SwitchTest(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((screens.BBS, screens.DIALER), ("bbs", "dialer"))

    def test_d_then_b_then_d(self):
        rc, _, log, fac, d = drive(
            screens.BBS, bbs=[KeyPressed("d"), KeyPressed("d")],
            dial=[KeyPressed("b"), KeyPressed("q")])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log),
                         ["bbs", "dialer", "bbs", "dialer"])
        # one Dialer object reused, its state carried on
        self.assertEqual(d.runs, 2)
        self.assertEqual(d.position, 20)
        # a fresh Session per BBS visit
        self.assertEqual(len(fac.made), 2)
        self.assertIsNot(fac.made[0], fac.made[1])

    def test_uppercase_keys(self):
        rc, _, log, _, _ = drive(screens.BBS, bbs=[KeyPressed("D")],
                                 dial=[KeyPressed("B")])
        self.assertEqual(rc, "stopped")
        self.assertEqual(screens_seen(log), ["bbs", "dialer", "bbs"])

    def test_same_key_on_bbs_starts_new_call(self):
        rc, _, log, fac, d = drive(
            screens.BBS, bbs=[KeyPressed("b"), KeyPressed("B"),
                              KeyPressed("x")])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["bbs", "bbs", "bbs"])
        self.assertEqual(len(fac.made), 3)
        self.assertEqual(d.runs, 0)

    def test_same_key_on_dialer_resumes(self):
        rc, _, log, fac, d = drive(
            screens.DIALER, dial=[KeyPressed("d"), KeyPressed("D"),
                                  KeyPressed("z")])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["dialer"] * 3)
        self.assertEqual(d.position, 30)
        self.assertEqual(fac.made, [])

    def test_other_keys_exit(self):
        for key in ["q", "x", " ", "\n", "\x1b", "1", "", "\xff"]:
            with self.subTest(key=key):
                rc, *_ = drive(screens.BBS, bbs=[KeyPressed(key)])
                self.assertEqual(rc, 0)
                rc, *_ = drive(screens.DIALER, dial=[KeyPressed(key)])
                self.assertEqual(rc, 0)

    def test_bare_keypressed_exits(self):
        rc, *_ = drive(screens.BBS, bbs=[KeyPressed()])
        self.assertEqual(rc, 0)

    def test_status_text_cleared_on_bbs(self):
        _, _, log, _, _ = drive(screens.DIALER, dial=[KeyPressed("b")])
        dialer_ev, bbs_ev = log.events
        self.assertEqual(dialer_ev[2], "GRiDSWEEP scanning")
        self.assertIsNone(bbs_ev[2])

    def test_key_during_pause_between_calls(self):
        # call finishes, then 'd' during the 2-5 s pause
        rc, line, log, fac, d = drive(
            screens.BBS, bbs=[None], dial=[KeyPressed("q")],
            pauses=[KeyPressed("d")])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["bbs", "dialer"])
        self.assertTrue(2 <= line.pauses[0] <= 5)

    def test_start_dialer(self):
        rc, _, log, fac, _ = drive(screens.DIALER, dial=[KeyPressed("q")])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["dialer"])
        self.assertEqual(fac.made, [])

    def test_keyboardinterrupt_propagates(self):
        # main() catches it; run_screens must not swallow it
        with self.assertRaises(KeyboardInterrupt):
            drive(screens.BBS, bbs=[KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):
            drive(screens.DIALER, dial=[KeyboardInterrupt()])


class RotateTest(unittest.TestCase):
    def test_no_rotate_leaves_deadline_unset(self):
        _, line, log, _, _ = drive(screens.BBS, bbs=[KeyPressed("d")],
                                   dial=[KeyPressed("b")])
        self.assertIsNone(line.rotate_at)
        self.assertTrue(all(e[1] is None for e in log.events))

    def test_rotate_swaps_and_rearms(self):
        clock = iter([100.0, 200.0, 300.0, 400.0])
        with mock.patch.object(screens.time, "monotonic",
                               lambda: next(clock)):
            rc, line, log, fac, d = drive(
                screens.BBS, bbs=[Rotate()], dial=[Rotate()],
                rotate=2, warp=1.0)
        self.assertEqual(rc, "stopped")
        self.assertEqual(screens_seen(log), ["bbs", "dialer", "bbs"])
        self.assertEqual([e[1] for e in log.events], [220.0, 320.0, 420.0])
        self.assertEqual(len(fac.made), 2)
        self.assertEqual(d.position, 10)

    def test_rotate_from_dialer(self):
        with mock.patch.object(screens.time, "monotonic", lambda: 0.0):
            _, _, log, _, _ = drive(screens.DIALER, dial=[Rotate()],
                                    rotate=1)
        self.assertEqual(screens_seen(log), ["dialer", "bbs"])

    def test_rotate_uses_warp(self):
        with mock.patch.object(screens.time, "monotonic", lambda: 50.0):
            _, line, log, _, _ = drive(screens.BBS, rotate=10, warp=4.0)
        self.assertAlmostEqual(log.events[0][1], 50.0 + 10 * 60 / 4.0)

    def test_fractional_minutes(self):
        with mock.patch.object(screens.time, "monotonic", lambda: 0.0):
            _, _, log, _, _ = drive(screens.BBS, rotate=0.5, warp=1.0)
        self.assertAlmostEqual(log.events[0][1], 30.0)

    def test_key_switch_rearms(self):
        clock = iter([0.0, 7.0, 13.0])
        with mock.patch.object(screens.time, "monotonic",
                               lambda: next(clock)):
            _, _, log, _, _ = drive(screens.BBS, bbs=[KeyPressed("d")],
                                    dial=[KeyPressed("b")], rotate=1)
        self.assertEqual([e[1] for e in log.events], [60.0, 67.0, 73.0])

    def test_rotate_during_pause(self):
        with mock.patch.object(screens.time, "monotonic", lambda: 0.0):
            _, _, log, _, _ = drive(screens.BBS, bbs=[None],
                                    pauses=[Rotate()], rotate=1)
        self.assertEqual(screens_seen(log), ["bbs", "dialer"])


class CallsTest(unittest.TestCase):
    def test_calls_n(self):
        for n in (1, 2, 3):
            with self.subTest(n=n):
                rc, line, log, fac, _ = drive(screens.BBS, bbs=[None] * 10,
                                              calls=n)
                self.assertEqual(rc, 0)
                self.assertEqual(len(fac.made), n)

    def test_dialer_does_not_count(self):
        # 1 finished call, rotate to dialer, rotate back, 1 more call: exit
        with mock.patch.object(screens.time, "monotonic", lambda: 0.0):
            rc, _, log, fac, d = drive(
                screens.BBS, bbs=[None, None, None], dial=[Rotate()],
                calls=2, rotate=1, pauses=[Rotate()])
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["bbs", "dialer", "bbs"])
        self.assertEqual(d.runs, 1)

    def test_dropped_call_not_counted(self):
        rc, _, log, fac, _ = drive(
            screens.BBS, bbs=[KeyPressed("b"), None], calls=1)
        self.assertEqual(rc, 0)
        self.assertEqual(len(fac.made), 2)

    def test_start_dialer_with_calls(self):
        rc, _, log, fac, _ = drive(screens.DIALER, bbs=[None],
                                   dial=[KeyPressed("b")], calls=1)
        self.assertEqual(rc, 0)
        self.assertEqual(screens_seen(log), ["dialer", "bbs"])


class RealDialerTest(unittest.TestCase):
    def test_real_dialer_resumes_across_switch(self):
        out = io.StringIO()
        line = Line(warp=3000, out=out, noise=0, exit_on_key=False)
        line._layout()
        dialer = Dialer(line, random.Random(3))
        first_scan = dialer.scan
        orig = line.pause
        n = [0]

        def pause(s):
            orig(s)
            n[0] += 1
            if n[0] == 40:
                raise KeyPressed("b")
            if n[0] == 80:
                raise KeyPressed("q")
        line.pause = pause

        class Sess:
            def run(self):
                raise KeyPressed("d")

        rc = screens.run_screens(line, random.Random(1), screens.DIALER,
                                 None, 0, Sess, dialer, 3000)
        self.assertEqual(rc, 0)
        self.assertIs(dialer.scan, first_scan)
        self.assertIn("GRiDSWEEP", out.getvalue())


# ------------------------------------------------------------ Line tests
class KeyPressedTest(unittest.TestCase):
    def test_key_attr(self):
        self.assertEqual(KeyPressed().key, "")
        self.assertEqual(KeyPressed("d").key, "d")
        self.assertTrue(issubclass(Rotate, Exception))
        self.assertFalse(issubclass(Rotate, KeyPressed))
        self.assertFalse(issubclass(KeyPressed, Rotate))


class PipeLineTest(unittest.TestCase):
    def setUp(self):
        self.r, self.w = os.pipe()
        self.out = io.StringIO()

    def tearDown(self):
        for fd in (self.r, self.w):
            try:
                os.close(fd)
            except OSError:
                pass

    def line(self, exit_on_key=True):
        ln = Line(out=self.out, noise=0, exit_on_key=exit_on_key,
                  status=False)
        ln.fd_in = self.r
        return ln

    def pending(self):
        return bool(select.select([self.r], [], [], 0)[0])

    def test_reads_one_byte(self):
        ln = self.line()
        os.write(self.w, b"dq")
        with self.assertRaises(KeyPressed) as cm:
            ln._check_key(0.5)
        self.assertEqual(cm.exception.key, "d")
        with self.assertRaises(KeyPressed) as cm:
            ln._check_key(0.5)
        self.assertEqual(cm.exception.key, "q")
        self.assertFalse(self.pending())

    def test_latin1(self):
        ln = self.line()
        os.write(self.w, b"\xe9")
        with self.assertRaises(KeyPressed) as cm:
            ln._check_key(0.5)
        self.assertEqual(cm.exception.key, "\xe9")

    def test_no_input_times_out(self):
        ln = self.line()
        t0 = time.monotonic()
        ln._check_key(0.05)
        self.assertLess(time.monotonic() - t0, 1)

    def test_no_exit_on_key_filters(self):
        ln = self.line(exit_on_key=False)
        os.write(self.w, b"xq \x1b")
        for _ in range(4):
            ln._check_key(0.05)  # consumed, ignored
        self.assertFalse(self.pending())
        for ch in "dDbB":
            os.write(self.w, ch.encode())
            with self.assertRaises(KeyPressed) as cm:
                ln._check_key(0.5)
            self.assertEqual(cm.exception.key, ch)

    def test_eof_does_not_raise(self):
        ln = self.line()
        os.close(self.w)
        t0 = time.monotonic()
        ln._check_key(0.05)
        self.assertLess(time.monotonic() - t0, 1)

    def test_wait_until_raises_keypressed(self):
        ln = self.line()
        os.write(self.w, b"b")
        with self.assertRaises(KeyPressed) as cm:
            ln.pause(5)
        self.assertEqual(cm.exception.key, "b")


class RotateLineTest(unittest.TestCase):
    def line(self, **kw):
        ln = Line(out=io.StringIO(), noise=0, status=False, **kw)
        ln.fd_in = None
        return ln

    def test_rotate_no_tty(self):
        for eok in (True, False):
            with self.subTest(exit_on_key=eok):
                ln = self.line(exit_on_key=eok)
                ln.rotate_at = time.monotonic() + 0.1
                t0 = time.monotonic()
                with self.assertRaises(Rotate):
                    ln.pause(30)
                el = time.monotonic() - t0
                self.assertGreaterEqual(el, 0.05)
                self.assertLess(el, 1.0)

    def test_rotate_past_deadline_immediate(self):
        ln = self.line()
        ln.rotate_at = time.monotonic() - 1
        with self.assertRaises(Rotate):
            ln.pause(30)

    def test_rotate_during_send(self):
        ln = self.line(bps=300)
        ln._layout()
        ln.rotate_at = time.monotonic() + 0.1
        t0 = time.monotonic()
        with self.assertRaises(Rotate):
            ln.send("x" * 2000)
        self.assertLess(time.monotonic() - t0, 2)

    def test_no_rotate_when_unset(self):
        ln = self.line()
        self.assertIsNone(ln.rotate_at)
        ln.pause(0.05)  # returns normally

    def test_rotate_with_pipe(self):
        r, w = os.pipe()
        try:
            ln = self.line()
            ln.fd_in = r
            ln.rotate_at = time.monotonic() + 0.1
            with self.assertRaises(Rotate):
                ln.pause(30)
        finally:
            os.close(r)
            os.close(w)


# -------------------------------------------------------------- CLI tests
def run_main(argv):
    """Run main() with Line faked and run_screens captured."""
    got = {}

    class FakeLine:
        def __init__(self, **kw):
            got["line_kw"] = kw

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_run(line, rng, start, rotate_minutes, calls, make_session,
                 dialer, warp=1.0):
        got.update(start=start, rotate=rotate_minutes, calls=calls,
                   warp=warp, dialer=dialer, make_session=make_session)
        return 0

    with mock.patch.object(cli, "Line", FakeLine), \
            mock.patch.object(cli, "run_screens", fake_run), \
            mock.patch.object(sys.stdout, "isatty", return_value=True):
        rc = cli.main(argv)
    return rc, got


def parse_error(argv):
    err = io.StringIO()
    with contextlib.redirect_stderr(err), \
            mock.patch.object(sys.stdout, "isatty", return_value=True), \
            mock.patch.object(cli, "Line") as L:
        with unittest.TestCase().assertRaises(SystemExit) as cm:
            cli.main(argv)
    return cm.exception.code, err.getvalue(), L


def help_text():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            cli.main(["--help"])
        except SystemExit:
            pass
    return re.sub(r"\s+", " ", out.getvalue())


class CliTest(unittest.TestCase):
    def test_default_start_bbs(self):
        rc, got = run_main(["--seed", "1"])
        self.assertEqual(rc, 0)
        self.assertEqual(got["start"], screens.BBS)
        self.assertIsNone(got["rotate"])

    def test_bbs_flag(self):
        self.assertEqual(run_main(["--bbs"])[1]["start"], screens.BBS)

    def test_dialer_flag(self):
        rc, got = run_main(["--dialer"])
        self.assertEqual(rc, 0)
        self.assertEqual(got["start"], screens.DIALER)
        self.assertIsInstance(got["dialer"], Dialer)

    def test_rotate_passed(self):
        for argv, start in ((["--rotate", "0.5"], screens.BBS),
                            (["--rotate", "10", "--dialer"], screens.DIALER),
                            (["--bbs", "--rotate", "3"], screens.BBS)):
            with self.subTest(argv=argv):
                rc, got = run_main(argv + ["--warp", "7"])
                self.assertEqual(rc, 0)
                self.assertEqual(got["start"], start)
                self.assertEqual(got["rotate"], float(argv[argv.index(
                    "--rotate") + 1]))
                self.assertEqual(got["warp"], 7.0)

    def test_calls_passed(self):
        self.assertEqual(run_main(["--calls", "4"])[1]["calls"], 4)
        self.assertEqual(run_main([])[1]["calls"], 0)

    def test_make_session_builds_fresh_sessions(self):
        _, got = run_main(["--seed", "2"])
        a, b = got["make_session"](), got["make_session"]()
        self.assertIsNot(a, b)
        self.assertTrue(hasattr(a, "run"))

    def test_dialer_does_not_shift_bbs_seed(self):
        # --seed N must give the same BBS calls as before DIAL-2: building
        # the Dialer may not draw from the rng the Sessions use.
        class QuietDialer:
            def __init__(self, line, rng):
                pass

        _, got = run_main(["--seed", "7"])
        real = got["make_session"]().rng.getstate()
        with mock.patch.object(cli, "Dialer", QuietDialer):
            _, got = run_main(["--seed", "7"])
        quiet = got["make_session"]().rng.getstate()
        self.assertEqual(real, quiet,
                         "Dialer(...) advanced the BBS rng; --seed output "
                         "changed (media and splash pty tests fail)")

    def test_no_exit_on_key_passed(self):
        _, got = run_main(["--no-exit-on-key"])
        self.assertFalse(got["line_kw"]["exit_on_key"])

    def test_bbs_and_dialer_conflict(self):
        code, err, L = parse_error(["--bbs", "--dialer"])
        self.assertEqual(code, 2)
        self.assertIn("not allowed with", err)
        L.assert_not_called()

    def test_rotate_rejects(self):
        for bad in ["0", "-1", "abc", "nan", "inf", "-inf", "1e999", "",
                    "0.0", "-0"]:
            with self.subTest(bad=bad):
                code, err, L = parse_error(["--rotate", bad])
                self.assertEqual(code, 2)
                self.assertIn("--rotate", err)
                L.assert_not_called()

    def test_rotate_needs_value(self):
        code, _, _ = parse_error(["--rotate"])
        self.assertEqual(code, 2)

    def test_keypressed_or_ctrl_c_from_enter(self):
        for exc in (KeyPressed(), KeyPressed("q"), KeyboardInterrupt()):
            class FL:
                def __init__(self, **kw):
                    pass

                def __enter__(self, exc=exc):
                    raise exc

                def __exit__(self, *a):
                    return False
            with self.subTest(exc=exc), \
                    mock.patch.object(cli, "Line", FL), \
                    mock.patch.object(sys.stdout, "isatty",
                                      return_value=True):
                self.assertEqual(cli.main([]), 0)

    def test_ctrl_c_from_run_screens(self):
        class FL:
            def __init__(self, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def boom(*a, **k):
            raise KeyboardInterrupt
        with mock.patch.object(cli, "Line", FL), \
                mock.patch.object(cli, "run_screens", boom), \
                mock.patch.object(sys.stdout, "isatty", return_value=True):
            self.assertEqual(cli.main([]), 0)


class HelpTest(unittest.TestCase):
    def test_help(self):
        h = help_text()
        self.assertIn("d = dialer", h)
        self.assertIn("b = BBS", h)
        self.assertIn("any other key exits", h)
        self.assertNotIn("HST. Any key exits.", h)
        for opt in ("--bbs", "--dialer", "--rotate MINUTES"):
            self.assertIn(opt, h)

    def test_no_exit_on_key_help(self):
        h = help_text()
        m = re.search(r"--no-exit-on-key (.*?)(?= --)", h)
        self.assertIsNotNone(m)
        self.assertIn("except d and b", m.group(1))
        self.assertIn("Ctrl-C", m.group(1))


# ------------------------------------------------------------- pty tests
@unittest.skipIf(pty is None, "pty unavailable")
class PtyTest(unittest.TestCase):
    def start(self, *args):
        master, slave = pty.openpty()
        env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT,
                   COLUMNS="80", LINES="25")
        proc = subprocess.Popen(
            [sys.executable, "-m", "courierhst", *args],
            stdin=slave, stdout=slave, stderr=slave, env=env, cwd=ROOT,
            close_fds=True)
        os.close(slave)
        self.addCleanup(self.cleanup, proc, master)
        self.master, self.proc, self.seen = master, proc, bytearray()

    @staticmethod
    def cleanup(proc, master):
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(master)

    def wait_for(self, text, secs=15):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            r, _, _ = select.select([self.master], [], [], 0.1)
            if r:
                try:
                    self.seen.extend(os.read(self.master, 65536))
                except OSError:
                    break
            if text in self.seen:
                return True
        return False

    def drain(self, secs):
        self.wait_for(b"\x00never\x00", secs)

    def send(self, b):
        self.seen.clear()
        os.write(self.master, b)

    def test_d_b_q(self):
        self.start("--warp", "50", "--seed", "1")
        self.assertTrue(self.wait_for(b"ATDT"))
        self.send(b"d")
        self.assertTrue(self.wait_for(b"GRiDSWEEP"))
        self.send(b"b")
        self.assertTrue(self.wait_for(b"ATDT"))
        self.assertNotIn(b"GRiDSWEEP", self.seen)
        self.send(b"q")
        self.assertEqual(self.proc.wait(timeout=5), 0)

    def test_dialer_start_then_d_resumes(self):
        self.start("--dialer", "--warp", "50", "--seed", "2")
        self.assertTrue(self.wait_for(b"GRiDSWEEP"))
        self.drain(0.5)
        self.assertNotIn(b"ATDT", self.seen)
        self.send(b"D")
        self.assertTrue(self.wait_for(b"GRiDSWEEP"))
        self.drain(0.3)
        self.assertEqual(self.proc.poll(), None)
        self.send(b"x")
        self.assertEqual(self.proc.wait(timeout=5), 0)

    def test_rotate(self):
        # 0.5 min at warp 50 = 0.6 s per screen
        self.start("--rotate", "0.5", "--warp", "50", "--seed", "3")
        self.assertTrue(self.wait_for(b"ATDT"))
        self.seen.clear()
        self.assertTrue(self.wait_for(b"GRiDSWEEP", 10))
        self.seen.clear()
        self.assertTrue(self.wait_for(b"ATDT", 10))
        self.send(b"q")
        self.assertEqual(self.proc.wait(timeout=5), 0)

    def test_no_exit_on_key(self):
        self.start("--no-exit-on-key", "--warp", "50", "--seed", "4")
        self.assertTrue(self.wait_for(b"ATDT"))
        self.send(b"q")
        self.drain(0.5)
        self.assertIsNone(self.proc.poll(), "q exited with --no-exit-on-key")
        self.send(b"d")
        self.assertTrue(self.wait_for(b"GRiDSWEEP"))
        self.send(b"b")
        self.assertTrue(self.wait_for(b"ATDT"))
        # the pty is not the child's controlling tty, so deliver ^C directly
        self.proc.send_signal(signal.SIGINT)
        self.assertEqual(self.proc.wait(timeout=5), 0)


if __name__ == "__main__":
    unittest.main()
