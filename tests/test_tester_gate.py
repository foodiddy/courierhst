"""Tester acceptance tests for the foundry.json gate and the pyte requirement.

The pyte-requirement checks import the tests package in a fresh venv without
pyte, which is fast. The optional full-gate test runs the suite in a
subprocess; nested runs discover this file too, so the subprocess tests skip
themselves when NESTED is set, to avoid recursion. The env var name is built at runtime so a plain grep for it only
matches foundry.json, tests/__init__.py and README.md.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR = "COURIERHST_" + "REQUIRE_" + "PYTE"
NESTED = "COURIERHST_TESTER_GATE_NESTED"
GATE = (
    'python3 -m venv "$TMPDIR/v" && "$TMPDIR/v"/bin/pip install -q \'.[test]\' '
    '&& ' + VAR + '=1 "$TMPDIR/v"/bin/python -m unittest discover -s tests -t .'
)
PYTE_SKIP = re.compile(r"skipped .*pyte", re.IGNORECASE)

not_nested = unittest.skipIf(os.environ.get(NESTED) == "1",
                             "nested run of the suite")


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k != VAR and not k.startswith("PYTHON")}
    env[NESTED] = "1"
    env.update(extra)
    return env


class FoundryJsonTest(unittest.TestCase):
    def test_exact_gate(self):
        with open(os.path.join(ROOT, "foundry.json")) as f:
            data = json.load(f)
        self.assertEqual(list(data.keys()), ["gates"])
        self.assertEqual(data["gates"], [GATE])


class ReadmeTest(unittest.TestCase):
    def test_development_section(self):
        with open(os.path.join(ROOT, "README.md")) as f:
            text = f.read()
        idx = text.find("## Development")
        self.assertNotEqual(idx, -1)
        nxt = text.find("\n## ", idx + 1)
        section = text[idx:nxt if nxt != -1 else len(text)]
        self.assertIn("pip install '.[test]'", section)
        self.assertIn(GATE, section)
        self.assertIn(VAR, section)


@not_nested
class GrepTest(unittest.TestCase):
    def test_var_only_in_allowed_files(self):
        try:
            r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            self.skipTest("git not available")
        if r.returncode != 0:
            self.skipTest("not a git checkout")
        files = []
        for rel in r.stdout.decode("utf-8", "replace").split("\0"):
            path = os.path.join(ROOT, rel)
            if not rel or not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                if VAR.encode() in f.read():
                    files.append(rel)
        self.assertEqual(sorted(files),
                         ["README.md", "foundry.json", "tests/__init__.py"])


@not_nested
class RequirePyteTest(unittest.TestCase):
    """Fresh venv without pyte."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        venv = os.path.join(cls.tmp, "v")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", venv],
                       check=True)
        cls.py = os.path.join(venv, "bin", "python")
        r = subprocess.run([cls.py, "-c", "import pyte"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert r.returncode != 0, "pyte unexpectedly importable in fresh venv"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def import_tests(self, value):
        extra = {} if value is None else {VAR: value}
        return subprocess.run(
            [self.py, "-c", "import tests"],
            cwd=ROOT, env=clean_env(**extra), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, timeout=60)

    def test_required_and_missing_fails(self):
        r = self.import_tests("1")
        self.assertNotEqual(r.returncode, 0, r.stdout[-2000:])
        self.assertIn("pyte", r.stdout)
        self.assertIn(VAR, r.stdout)
        self.assertIn("ImportError", r.stdout)

    def test_not_required_skips(self):
        for value in (None, "0", "", "true", "yes", " 1"):
            with self.subTest(value=value):
                r = self.import_tests(value)
                self.assertEqual(r.returncode, 0, r.stdout[-2000:])
                self.assertNotIn(VAR + "=1 but", r.stdout)


@unittest.skipUnless(os.environ.get("COURIERHST_TEST_GATE") == "1",
                     "set COURIERHST_TEST_GATE=1 to re-run the full gate")
@not_nested
class GateCommandTest(unittest.TestCase):
    def test_gate_runs_full_suite_with_pyte(self):
        tmp = tempfile.mkdtemp()
        try:
            r = subprocess.run(
                ["bash", "-c", GATE.replace(" discover ", " discover -v ")],
                cwd=ROOT, env=clean_env(TMPDIR=tmp), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, universal_newlines=True,
                timeout=1200)
            out = r.stdout
            self.assertEqual(r.returncode, 0, out[-3000:])
            self.assertRegex(out, r"\nOK")
            self.assertTrue(os.path.exists(os.path.join(tmp, "v", "bin",
                                                        "python")))
            self.assertEqual(PYTE_SKIP.findall(out), [], "pty tests skipped")
            m = re.search(r"Ran (\d+) tests?", out)
            self.assertTrue(m and int(m.group(1)) > 0, out[-1000:])
            # pyte really installed in the gate's venv
            v = subprocess.run([os.path.join(tmp, "v", "bin", "python"), "-c",
                                "import pyte"])
            self.assertEqual(v.returncode, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_gate_command_text_matches_foundry_json(self):
        # The -v variant above differs only by the verbosity flag.
        with open(os.path.join(ROOT, "foundry.json")) as f:
            self.assertEqual(json.load(f)["gates"][0], GATE)


if __name__ == "__main__":
    unittest.main()
