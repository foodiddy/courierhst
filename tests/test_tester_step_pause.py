"""Tester acceptance checks for --step-pause (task mwfxa7rtx8kggo)."""
import os
import random
import re
import subprocess
import sys
import time
import unittest
from unittest import mock

from courierhst import bbs, doors
from courierhst.modem import Line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONPATH=ROOT)
STYLES = ["renegade", "telegard", "mystic", "pcboard"]
MARK = 7.25  # distinctive step value so step pauses can't be confused


class RecLine:
    """Fake Line that records an ordered event log."""

    def __init__(self):
        self.ev = []
        self.online_since = None
        self.status_name = ""
        self.connect_speed = ""
        self.dialing = False
        self.warp = 1.0
        self.cps = 1e9

    def pause(self, seconds):
        self.ev.append(("pause", seconds))

    def rpause(self, lo, hi):
        self.ev.append(("rpause", (lo, hi)))

    def send(self, s, cps=None):
        self.ev.append(("send", s))

    def sendln(self, s="", cps=None):
        self.ev.append(("send", s + "\n"))

    def local(self, s):
        self.ev.append(("local", s))

    def type(self, s, fast=False):
        self.ev.append(("type", s))

    def type_hidden(self, s, mask="*"):
        self.ev.append(("type", s))

    def enter(self):
        self.ev.append(("enter", None))

    def cls_local(self):
        pass

    def __getattr__(self, name):  # tolerate any extra Line helper
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def pauses(self, value):
        return [e for e in self.ev if e == ("pause", value)]


def make(style, seed, step_pause=bbs.DEFAULT_STEP_PAUSE):
    line = RecLine()
    s = bbs.Session(line, random.Random(seed), "Tester", xfer_speedup=1e9,
                    style=style, step_pause=step_pause)
    return s, line


def run_logged(s, line):
    """Run a full call, logging a marker each time a main-menu command
    key is chosen (key_for is only called for main-menu commands)."""
    real = bbs.key_for

    def spy(b, act):
        line.ev.append(("MAIN", act))
        return real(b, act)

    # dial() has its own fixed pause(5) redial wait; skip it so it can't
    # be mistaken for a step pause.
    with mock.patch.object(bbs, "key_for", spy), \
            mock.patch.object(s, "dial", lambda: True):
        s.run()


class Defaults(unittest.TestCase):
    def test_constant_and_session_default(self):
        self.assertEqual(bbs.DEFAULT_STEP_PAUSE, 5.0)
        s = bbs.Session(RecLine(), random.Random(1), "T")
        self.assertEqual(s.step_pause, 5.0)

    def test_step_calls_line_pause(self):
        s, line = make("renegade", 1, step_pause=5.0)
        line.ev.clear()
        s.step()
        self.assertEqual(line.ev, [("pause", 5.0)])


class MainMenu(unittest.TestCase):
    def test_five_second_pause_before_each_main_command(self):
        for style in STYLES:
            for seed in range(6):
                with self.subTest(style=style, seed=seed):
                    s, line = make(style, seed, step_pause=5.0)
                    run_logged(s, line)
                    idx = [i for i, e in enumerate(line.ev) if e[0] == "MAIN"]
                    self.assertGreaterEqual(len(idx), 5)  # 4..8 + bye
                    self.assertEqual(line.ev[idx[-1]], ("MAIN", "bye"))
                    for i in idx:
                        self.assertEqual(line.ev[i - 1], ("pause", 5.0),
                                         f"no step before {line.ev[i]}")

    def test_zero_disables(self):
        for style in STYLES:
            for seed in range(4):
                with self.subTest(style=style, seed=seed):
                    s, line = make(style, seed, step_pause=0)
                    run_logged(s, line)
                    self.assertEqual(line.pauses(5.0), [])
                    idx = [i for i, e in enumerate(line.ev) if e[0] == "MAIN"]
                    for i in idx:
                        prev = line.ev[i - 1]
                        self.assertFalse(prev[0] == "pause" and prev[1] > 0,
                                         f"extra pause {prev}")

    def test_zero_vs_default_only_adds_step_pauses(self):
        # Same seed: the only difference in the event log is the step pause.
        for style in STYLES:
            with self.subTest(style=style):
                a, la = make(style, 3, step_pause=MARK)
                b, lb = make(style, 3, step_pause=0)
                run_logged(a, la)
                run_logged(b, lb)
                self.assertGreater(len(la.pauses(MARK)), 0)
                # send/local text can contain wall-clock times; compare
                # the timing/answer skeleton only.
                keep = ("pause", "rpause", "type", "MAIN")
                self.assertEqual(
                    [e for e in la.ev if e[0] in keep and e != ("pause", MARK)],
                    [e for e in lb.ev if e[0] in keep and e != ("pause", 0)])


class NotDuringLogin(unittest.TestCase):
    def test_no_step_in_dial_or_login(self):
        for style in STYLES:
            for seed in range(5):
                with self.subTest(style=style, seed=seed):
                    s, line = make(style, seed, step_pause=MARK)
                    s.dial()
                    s.login()
                    self.assertEqual(line.pauses(MARK), [])


def prompt_for(ev, i):
    """Text sent since the previous answer, i.e. the prompt answered at i."""
    out = []
    for j in range(i - 1, -1, -1):
        if ev[j][0] in ("type", "enter"):
            break
        if ev[j][0] == "send":
            out.append(ev[j][1])
    return "".join(reversed(out))


def _preceded_by_step(ev, i):
    """True if a MARK pause occurs after the last typed answer before i."""
    for j in range(i - 1, -1, -1):
        if ev[j] == ("pause", MARK):
            return True
        if ev[j][0] in ("type", "enter"):
            return False
    return False


class SubMenus(unittest.TestCase):
    def _check_prompts(self, style, method, needle, seeds=range(8)):
        found = 0
        for seed in seeds:
            s, line = make(style, seed, step_pause=MARK)
            getattr(s, method)()
            for i, e in enumerate(line.ev):
                if e[0] == "type" and isinstance(e[1], str):
                    # find the prompt this answer belongs to
                    if needle(re.sub(r"\|\d\d", "", prompt_for(line.ev, i)).lower(),
                              e[1]):
                        found += 1
                        self.assertTrue(_preceded_by_step(line.ev, i),
                                        f"{style}/{method} seed {seed}: no "
                                        f"step before answer {e[1]!r}")
        return found

    def test_message_reader_next_quit(self):
        for style in STYLES:
            with self.subTest(style=style):
                method = "do_msgs_pcb" if style == "pcboard" else "do_msgs"
                n = self._check_prompts(
                    style, method,
                    lambda sent, ans: ans in ("N", "Q") and "ext" in sent)
                self.assertGreater(n, 0)

    def test_file_list_flag_download_quit(self):
        for style in STYLES:
            with self.subTest(style=style):
                method = "do_files_pcb" if style == "pcboard" else "do_files"
                n = self._check_prompts(
                    style, method,
                    lambda sent, ans: ans in ("F", "D", "Q")
                    and "ownload" in sent)
                self.assertGreater(n, 0)


class Doors(unittest.TestCase):
    def _door(self, fn, seed):
        s, line = make("renegade", seed, step_pause=MARK)
        fn(s)
        return line

    def test_shadowmire_each_plan_step(self):
        for seed in range(6):
            line = self._door(doors.shadowmire, seed)
            answers = [i for i, e in enumerate(line.ev)
                       if e[0] == "type" and "Your command" in prompt_for(line.ev, i)]
            self.assertGreater(len(answers), 3)
            for i in answers:
                self.assertTrue(_preceded_by_step(line.ev, i), seed)

    def test_starlane_each_move(self):
        for seed in range(6):
            line = self._door(doors.starlane, seed)
            answers = [i for i, e in enumerate(line.ev)
                       if e[0] == "type" and "Command [" in prompt_for(line.ev, i)]
            self.assertGreaterEqual(len(answers), 3)  # >=2 moves + Q
            for i in answers:
                self.assertTrue(_preceded_by_step(line.ev, i), seed)


class Cli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "courierhst", *args],
                              cwd=ROOT, env=ENV, capture_output=True,
                              text=True, timeout=20)

    def test_help_lists_step_pause(self):
        r = self.cli("--help")
        self.assertEqual(r.returncode, 0)
        out = " ".join(r.stdout.split())
        self.assertIn("--step-pause", out)
        self.assertRegex(out, r"--step-pause SECONDS.*default 5\b")

    def test_negative_rejected(self):
        r = self.cli("--step-pause", "-1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage:", r.stderr)
        self.assertIn("--step-pause", r.stderr)

    def test_non_number_and_nan_rejected(self):
        for v in ("abc", "nan"):
            with self.subTest(v=v):
                self.assertEqual(self.cli("--step-pause", v).returncode, 2)

    def test_value_passed_to_session(self):
        from courierhst import __main__ as m
        seen = []

        class FakeSession:
            def __init__(self, *a, **k):
                seen.append(k.get("step_pause"))

            def run(self):
                raise KeyboardInterrupt

        for argv, want in ((["--step-pause", "2.5"], 2.5), ([], 5.0),
                           (["--step-pause", "0"], 0.0)):
            with mock.patch.object(m, "Session", FakeSession), \
                    mock.patch.object(m.sys.stdout, "isatty", lambda: True), \
                    mock.patch.object(m, "Line") as FL:
                FL.return_value.__enter__.return_value = RecLine()
                m.main(argv)
            self.assertEqual(seen[-1], want)

    def test_readme_documents_flag(self):
        with open(os.path.join(ROOT, "README.md")) as f:
            self.assertIn("--step-pause", f.read())


class Timing(unittest.TestCase):
    def test_warp_scales_step(self):
        line = Line(noise=0, out=open(os.devnull, "w"), warp=50,
                    exit_on_key=False, status=False)
        line.fd_in = None
        s = bbs.Session(line, random.Random(1), "T", step_pause=5.0)
        t0 = time.monotonic()
        s.step()
        dt = time.monotonic() - t0
        line.out.close()
        self.assertGreaterEqual(dt, 0.05)
        self.assertLessEqual(dt, 0.15)


if __name__ == "__main__":
    unittest.main()
