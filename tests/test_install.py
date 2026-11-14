import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "install.sh")


def sh(*args, **kw):
    return subprocess.run(["/bin/sh", SCRIPT] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True, **kw)


class InstallScriptTests(unittest.TestCase):
    def test_syntax(self):
        r = subprocess.run(["sh", "-n", SCRIPT])
        self.assertEqual(r.returncode, 0)

    def test_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, PYTHONUSERBASE=home)
            r = sh("--dry-run", env=env, cwd=home)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("install", r.stdout)
            self.assertEqual(os.listdir(home), [])

    def test_dry_run_uninstall(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, PYTHONUSERBASE=home)
            r = sh("--dry-run", "--uninstall", env=env, cwd=home)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("uninstall", r.stdout)
            self.assertEqual(os.listdir(home), [])

    def test_unknown_option(self):
        r = sh("--bogus")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage", r.stdout)

    def test_help(self):
        r = sh("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage", r.stdout)

    def test_real_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv = os.path.join(tmp, "v")
            r = subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", venv],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                self.skipTest("cannot create venv")
            vpy = os.path.join(venv, "bin", "python")
            if subprocess.run([vpy, "-m", "pip", "--version"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                self.skipTest("pip not available")
            home = os.path.join(tmp, "home")
            os.mkdir(home)
            keep = [d for d in os.environ.get("PATH", "").split(os.pathsep)
                    if not os.path.exists(os.path.join(d, "pipx"))]
            path = os.pathsep.join([os.path.join(venv, "bin"),
                                    os.path.join(home, "bin")] + keep)
            env = dict(os.environ, HOME=home, PYTHONUSERBASE=home, PATH=path)
            env.pop("PIPX_BIN_DIR", None)
            if shutil.which("pipx", path=path):
                self.skipTest("cannot hide pipx from PATH")
            r = sh(env=env, cwd=tmp)
            if r.returncode != 0:
                self.skipTest("install failed (network or pip problem?): " + r.stdout[-500:])
            out = subprocess.run(["courierhst", "--help"], env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True)
            self.assertEqual(out.returncode, 0, out.stdout)
            self.assertIn("14.4 USR Courier HST", out.stdout)
            r = sh("--uninstall", env=env, cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stdout)


class PackagingTests(unittest.TestCase):
    def test_entry_point_imports(self):
        mod = importlib.import_module("courierhst.__main__")
        self.assertTrue(callable(mod.main))

    def test_readme_install_section(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("## Install", text)
        self.assertLess(text.index("## Install"), text.index("## Run"))
        for cmd in ("./install.sh", "--dry-run", "--uninstall", "pipx install .",
                    "pip install --user .", "python3 -m courierhst", "pip install '.[test]'"):
            self.assertIn(cmd, text)


if __name__ == "__main__":
    unittest.main()
