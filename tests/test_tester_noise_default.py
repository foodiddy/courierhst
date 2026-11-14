"""Tester acceptance tests for the lowered default line-noise rate (0.0007)."""

import inspect
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from courierhst import __main__ as cli
from courierhst.modem import KeyPressed, Line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_main_capture(argv):
    """Run main() with Line replaced; return the kwargs Line was built with."""
    seen = {}

    class FakeLine:
        def __init__(self, **kw):
            seen.update(kw)

        def __enter__(self):
            raise KeyPressed()

        def __exit__(self, *exc):
            return False

    with mock.patch.object(cli, "Line", FakeLine), \
            mock.patch.object(sys.stdout, "isatty", return_value=True):
        rc = cli.main(argv)
    return rc, seen


class LineDefaultTest(unittest.TestCase):
    def test_signature_default(self):
        self.assertEqual(
            inspect.signature(Line.__init__).parameters["noise"].default,
            0.0007)

    def test_instance_default(self):
        line = Line(out=io.StringIO())
        self.assertEqual(line.noise, 0.0007)

    def test_other_defaults_unchanged(self):
        params = inspect.signature(Line.__init__).parameters
        self.assertEqual(params["bps"].default, 14400)
        self.assertIs(params["center"].default, True)
        self.assertIs(params["status"].default, True)
        self.assertIs(params["exit_on_key"].default, True)
        self.assertIsNone(params["out"].default)
        self.assertEqual(params["warp"].default, 1.0)


class CliDefaultTest(unittest.TestCase):
    def test_main_passes_default_noise(self):
        rc, kw = run_main_capture([])
        self.assertEqual(rc, 0)
        self.assertEqual(kw["noise"], 0.0007)

    def test_explicit_noise_still_honoured(self):
        _, kw = run_main_capture(["--noise", "0.0015"])
        self.assertEqual(kw["noise"], 0.0015)
        _, kw = run_main_capture(["--noise", "0"])
        self.assertEqual(kw["noise"], 0.0)

    def test_other_cli_defaults_unchanged(self):
        _, kw = run_main_capture([])
        self.assertEqual(kw["bps"], 14400)
        self.assertEqual(kw["warp"], 1.0)
        self.assertIs(kw["center"], True)
        self.assertIs(kw["status"], True)
        self.assertIs(kw["exit_on_key"], True)

    def test_help_text_unchanged(self):
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["--help"])
        out = " ".join(buf.getvalue().split())
        self.assertIn("line-noise probability per character (0 disables)", out)
        self.assertNotIn("0.0015", out)

    def test_help_subprocess(self):
        r = subprocess.run([sys.executable, "-m", "courierhst", "--help"],
                           cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("--noise", r.stdout)
        self.assertNotIn("0.0015", r.stdout)


class ReadmeTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "README.md")) as f:
            self.text = f.read()

    def test_noise_row(self):
        rows = [l for l in self.text.splitlines()
                if l.startswith("| `--noise P`")]
        self.assertEqual(len(rows), 1)
        self.assertIn("default 0.0007", rows[0])
        self.assertIn("0 = off", rows[0])

    def test_old_value_gone(self):
        self.assertEqual(self.text.count("default 0.0007"), 1)
        self.assertNotIn("0.0015", self.text)


class SourceTest(unittest.TestCase):
    def test_no_stale_defaults_in_package(self):
        for name in ("__main__.py", "modem.py"):
            with open(os.path.join(ROOT, "courierhst", name)) as f:
                src = f.read()
            self.assertNotIn("0.0015", src, name)
            self.assertNotIn("noise=0.002", src, name)


if __name__ == "__main__":
    unittest.main()
