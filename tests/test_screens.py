"""Screen switching (d / b / rotate), CLI options and key reading."""
import contextlib
import io
import os
import time
import unittest
from unittest import mock

from courierhst import __main__ as cli
from courierhst import screens
from courierhst.modem import KeyPressed, Line, Rotate


class FakeLine:
    status_text = None
    rotate_at = None

    def __init__(self):
        self.pauses = []

    def pause(self, secs):
        self.pauses.append(secs)


class FakeRng:
    def uniform(self, a, b):
        return a


class FakeDialer:
    """Counts 'dialed' numbers across runs, like a resumable scan."""

    def __init__(self, script):
        self.script = script  # exceptions to raise, one per run()
        self.dialed = 0
        self.runs = 0

    def run(self):
        self.runs += 1
        self.dialed += 1
        raise self.script.pop(0)


class FakeSession:
    made = 0

    def __init__(self, script):
        FakeSession.made += 1
        self.script = script

    def run(self):
        if self.script:
            raise self.script.pop(0)


def drive(start, bbs_script, dialer_script, calls=0, rotate=None, warp=1.0):
    line, FakeSession.made = FakeLine(), 0
    d = FakeDialer(dialer_script)
    rc = screens.run_screens(
        line, FakeRng(), start, rotate, calls,
        lambda: FakeSession(bbs_script), d, warp)
    return rc, line, d


class SwitchTest(unittest.TestCase):
    def test_d_then_b(self):
        rc, _, d = drive(screens.BBS, [KeyPressed("d"), KeyPressed("d")],
                         [KeyPressed("b"), KeyPressed("d"), KeyPressed("x")],
                         calls=0)
        # BBS -d-> dialer -b-> BBS (new session, ends via 'd') -> dialer -x
        self.assertEqual(rc, 0)
        self.assertEqual(d.dialed, d.runs)
        self.assertGreaterEqual(d.dialed, 2)
        self.assertGreaterEqual(FakeSession.made, 2)

    def test_same_key_does_not_switch(self):
        rc, _, d = drive(screens.DIALER, [],
                         [KeyPressed("D"), KeyPressed("x")])
        self.assertEqual(rc, 0)
        self.assertEqual(d.runs, 2)
        self.assertEqual(FakeSession.made, 0)

    def test_same_key_on_bbs_starts_new_call(self):
        rc, _, _ = drive(screens.BBS, [KeyPressed("b"), KeyPressed("q")], [])
        self.assertEqual(rc, 0)
        self.assertEqual(FakeSession.made, 2)

    def test_other_key_exits(self):
        rc, _, d = drive(screens.BBS, [KeyPressed("q")], [])
        self.assertEqual((rc, d.runs), (0, 0))
        rc, _, d = drive(screens.DIALER, [], [KeyPressed("")])
        self.assertEqual((rc, d.runs), (0, 1))

    def test_calls_limit(self):
        rc, line, _ = drive(screens.BBS, [], [], calls=3)
        self.assertEqual((rc, FakeSession.made), (0, 3))
        self.assertEqual(len(line.pauses), 2)


class RotateTest(unittest.TestCase):
    def test_rotate_swaps_and_rearms(self):
        stamps = []
        orig = FakeDialer.run

        def run(self):
            stamps.append(self.line.rotate_at)
            return orig(self)

        line = FakeLine()
        d = FakeDialer([KeyPressed("q")])
        d.line = line
        with mock.patch.object(FakeDialer, "run", run), \
                mock.patch.object(screens.time, "monotonic",
                                  side_effect=[100.0, 200.0]):
            rc = screens.run_screens(
                line, FakeRng(), screens.BBS, 2, 0,
                lambda: FakeSession([Rotate()]), d, warp=60.0)
        self.assertEqual(rc, 0)
        # armed at 100 (+2 s: 2 min / 60); BBS rotates; re-armed at 200
        self.assertEqual(stamps, [202.0])
        self.assertEqual(line.rotate_at, 202.0)

    def test_key_switch_rearms(self):
        line = FakeLine()
        d = FakeDialer([KeyPressed("q")])
        with mock.patch.object(screens.time, "monotonic",
                               side_effect=[10.0, 50.0]):
            screens.run_screens(line, FakeRng(), screens.BBS, 1, 0,
                                lambda: FakeSession([KeyPressed("d")]), d)
        self.assertEqual(line.rotate_at, 110.0)

    def test_no_rotate_leaves_deadline_unset(self):
        _, line, _ = drive(screens.BBS, [], [], calls=1)
        self.assertIsNone(line.rotate_at)


class CliTest(unittest.TestCase):
    def parse_error(self, args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as cm:
            cli.main(args)
        return cm.exception.code, err.getvalue()

    def test_bbs_and_dialer_conflict(self):
        code, _ = self.parse_error(["--bbs", "--dialer"])
        self.assertEqual(code, 2)

    def test_rotate_rejects(self):
        for bad in ["0", "-1", "abc", "nan", "inf"]:
            code, _ = self.parse_error(["--rotate=" + bad])
            self.assertEqual(code, 2, bad)

    def test_rotate_accepts(self):
        for good, want in [("0.5", 0.5), ("10", 10.0)]:
            seen = {}

            def fake(line, rng, start, rot, *a):
                seen.update(start=start, rot=rot)

            class L:
                def __init__(self, **kw):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, *e):
                    return False

            with mock.patch.object(cli, "Line", L), \
                    mock.patch.object(cli, "run_screens", fake), \
                    mock.patch.object(cli.sys.stdout, "isatty",
                                      return_value=True):
                cli.main(["--dialer", "--rotate", good])
            self.assertEqual(seen, {"start": screens.DIALER, "rot": want})

    def test_help_text(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["--help"])
        text = " ".join(buf.getvalue().split())
        self.assertIn("d = dialer", text)
        self.assertIn("b = BBS", text)
        self.assertNotIn("Courier HST. Any key exits.", text)


class KeyReadTest(unittest.TestCase):
    def make_line(self, exit_on_key=True):
        r, w = os.pipe()
        self.addCleanup(os.close, r)
        self.addCleanup(os.close, w)
        line = Line.__new__(Line)
        line.fd_in, line.exit_on_key = r, exit_on_key
        return line, w

    def test_key_attribute(self):
        self.assertEqual(KeyPressed("x").key, "x")
        self.assertEqual(KeyPressed().key, "")

    def test_check_key_reads_byte(self):
        line, w = self.make_line()
        os.write(w, b"dq")
        with self.assertRaises(KeyPressed) as cm:
            line._check_key(0.5)
        self.assertEqual(cm.exception.key, "d")
        with self.assertRaises(KeyPressed) as cm:
            line._check_key(0.5)
        self.assertEqual(cm.exception.key, "q")

    def test_no_exit_on_key_only_d_and_b(self):
        line, w = self.make_line(exit_on_key=False)
        os.write(w, b"qB")
        line._check_key(0.5)  # 'q' ignored
        with self.assertRaises(KeyPressed) as cm:
            line._check_key(0.5)
        self.assertEqual(cm.exception.key, "B")

    def test_rotate_deadline_raises(self):
        line = Line.__new__(Line)
        line.fd_in, line.exit_on_key = None, True
        line._resized = False
        line._last_status = time.monotonic()
        line.rotate_at = time.monotonic() - 1
        with self.assertRaises(Rotate):
            line._wait_until(time.monotonic() + 5)


if __name__ == "__main__":
    unittest.main()
