"""Tester acceptance tests for install.sh and the README Install section.

Most checks run install.sh with a hermetic PATH: a shim dir holding only the
tools the script needs (sh, grep, cat, a python3) plus, where wanted, a fake
pipx that logs its calls. That way the pipx and pip branches, the old-python
and no-pip errors, and the PATH hint are all tested without the network. Two
real tests do a pip --user install into a temp HOME (one from a venv, one with
the system python3, which also checks --uninstall really removes it) and skip
if the network or pip is unavailable.
"""

import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "install.sh")
REAL_PY = os.path.realpath(sys.executable)


def write_exe(path, text):
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o755)


def snapshot(top):
    out = []
    for dirpath, dirnames, filenames in os.walk(top):
        for n in dirnames + filenames:
            out.append(os.path.relpath(os.path.join(dirpath, n), top))
    return sorted(out)


class Sandbox:
    """Temp HOME plus a shim bin dir that is the whole PATH."""

    def __init__(self, tmp, python="real", pipx=False, pipx_list="",
                 pipx_bindir=None):
        self.tmp = tmp
        self.home = os.path.join(tmp, "home")
        self.shim = os.path.join(tmp, "shim")
        self.log = os.path.join(tmp, "pipx.log")
        os.mkdir(self.home)
        os.mkdir(self.shim)
        for tool in ("sh", "grep", "cat"):
            src = shutil.which(tool)
            if src:
                os.symlink(src, os.path.join(self.shim, tool))
        py = os.path.join(self.shim, "python3")
        if python == "real":
            os.symlink(REAL_PY, py)
        elif python == "old":
            write_exe(py, '#!/bin/sh\ncase "$*" in *print*) echo 3.6 ;; esac\nexit 1\n')
        elif python == "nopip":
            write_exe(py, '#!/bin/sh\n'
                          'if [ "$1" = -m ] && [ "$2" = pip ]; then exit 1; fi\n'
                          'exec "%s" "$@"\n' % REAL_PY)
        if pipx:
            bindir = pipx_bindir or os.path.join(self.home, "pipxbin")
            write_exe(os.path.join(self.shim, "pipx"),
                      '#!/bin/sh\n'
                      'echo "$PWD|$*" >> "%s"\n'
                      'case "$1" in\n'
                      '  environment) echo "%s" ;;\n'
                      '  list) printf "%%s" "%s" ;;\n'
                      'esac\n'
                      'exit 0\n' % (self.log, bindir, pipx_list))
        self.env = {
            "HOME": self.home,
            "PYTHONUSERBASE": self.home,
            "PATH": self.shim,
            "SHELL": "/bin/bash",
            "LANG": "C.UTF-8",
        }

    def run(self, *args, cwd=None):
        return subprocess.run(["/bin/sh", SCRIPT] + list(args), env=self.env,
                              cwd=cwd or self.tmp, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)

    def pipx_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return [line.rstrip("\n").split("|", 1) for line in f]


class ScriptBasics(unittest.TestCase):
    def test_syntax_ok(self):
        r = subprocess.run(["sh", "-n", SCRIPT], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_executable_and_posix_shebang(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        with open(SCRIPT) as f:
            self.assertEqual(f.readline().strip(), "#!/bin/sh")

    def test_never_calls_sudo(self):
        for args, pipx in (((), True), (("--uninstall",), True),
                           (("--dry-run",), False), (("--dry-run", "--uninstall"), False)):
            with self.subTest(args=args), tempfile.TemporaryDirectory() as tmp:
                sb = Sandbox(tmp, pipx=pipx, pipx_list="courierhst 0.1.0\n")
                flag = os.path.join(tmp, "sudo-called")
                write_exe(os.path.join(sb.shim, "sudo"),
                          '#!/bin/sh\ntouch "%s"\nexit 1\n' % flag)
                sb.run(*args)
                self.assertFalse(os.path.exists(flag))

    def test_never_writes_rc_files(self):
        with open(SCRIPT) as f:
            text = f.read()
        self.assertNotRegex(text, r">>?\s*[\"']?(\$HOME|~|\$\{HOME\})/\.(bashrc|zshrc|profile)")
        self.assertNotRegex(text, r"sed\s+-i")
        self.assertNotRegex(text, r"tee\s+(-a\s+)?[\"']?(\$HOME|~)")
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True)
            sb.run()
            for rc in (".bashrc", ".zshrc", ".profile", ".bash_profile"):
                self.assertFalse(os.path.exists(os.path.join(sb.home, rc)))

    def test_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Sandbox(tmp).run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage", r.stdout)
        for flag in ("--dry-run", "--uninstall", "--help"):
            self.assertIn(flag, r.stdout)

    def test_unknown_option_exits_2_with_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True)
            r = sb.run("--bogus")
            self.assertEqual(r.returncode, 2)
            self.assertIn("Usage", r.stdout + r.stderr)
            self.assertEqual(sb.pipx_calls(), [])
            self.assertEqual(snapshot(sb.home), [])

    def test_unknown_option_after_valid_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Sandbox(tmp).run("--dry-run", "-x")
        self.assertEqual(r.returncode, 2)


class DryRun(unittest.TestCase):
    def test_dry_run_pip_fallback_prints_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            r = sb.run("--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("python3 -m pip install --user .", r.stdout)
            self.assertEqual(snapshot(sb.home), [])

    def test_dry_run_prefers_pipx_and_does_not_call_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True)
            r = sb.run("--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("pipx install --force .", r.stdout)
            self.assertNotIn("pip install --user", r.stdout)
            self.assertEqual(sb.pipx_calls(), [])
            self.assertEqual(snapshot(sb.home), [])

    def test_dry_run_uninstall(self):
        for pipx in (False, True):
            with self.subTest(pipx=pipx), tempfile.TemporaryDirectory() as tmp:
                sb = Sandbox(tmp, pipx=pipx, pipx_list="courierhst 0.1.0\n")
                r = sb.run("--dry-run", "--uninstall")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("uninstall", r.stdout)
                self.assertIn("courierhst", r.stdout)
                if pipx:
                    self.assertIn("pipx uninstall courierhst", r.stdout)
                self.assertEqual(sb.pipx_calls(), [])
                self.assertEqual(snapshot(sb.home), [])

    def test_dry_run_flag_order_does_not_matter(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            r = sb.run("--uninstall", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("uninstall", r.stdout)
            self.assertEqual(snapshot(sb.home), [])

    def test_dry_run_prints_path_hint_and_tip(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            r = sb.run("--dry-run")
            bindir = os.path.join(sb.home, "bin")
            self.assertIn('export PATH="%s:$PATH"' % bindir, r.stdout)
            self.assertIn(".bashrc", r.stdout)
            self.assertIn("80x25", r.stdout)
            self.assertRegex(r.stdout, r"VGA|CP437")

    def test_no_path_hint_when_bindir_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            sb.env["PATH"] = sb.shim + os.pathsep + os.path.join(sb.home, "bin")
            r = sb.run("--dry-run")
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("export PATH", r.stdout)

    def test_rc_file_follows_shell(self):
        for shell, rc in (("/usr/bin/zsh", ".zshrc"), ("/bin/dash", ".profile")):
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp:
                sb = Sandbox(tmp)
                sb.env["SHELL"] = shell
                r = sb.run("--dry-run")
                self.assertIn(rc, r.stdout)

    def test_runs_from_any_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp)
            elsewhere = os.path.join(tmp, "elsewhere")
            os.mkdir(elsewhere)
            r = sb.run("--dry-run", cwd=elsewhere)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(os.listdir(elsewhere), [])


class FakePipx(unittest.TestCase):
    def test_install_uses_pipx_from_repo_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True)
            r = sb.run()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            calls = sb.pipx_calls()
            self.assertIn([ROOT, "install --force ."],
                          [[os.path.realpath(c[0]), c[1]] for c in calls])
            self.assertIn("courierhst", r.stdout)
            bindir = os.path.join(sb.home, "pipxbin")
            self.assertIn('export PATH="%s:$PATH"' % bindir, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(sb.home, "lib")))

    def test_install_twice_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True)
            self.assertEqual(sb.run().returncode, 0)
            self.assertEqual(sb.run().returncode, 0)

    def test_uninstall_with_pipx_install_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True, pipx_list="courierhst 0.1.0\n")
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("uninstall courierhst", [c[1] for c in sb.pipx_calls()])

    def test_uninstall_nothing_installed_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, pipx=True, pipx_list="otherpkg 1.0\n")
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.strip(), "")
            self.assertEqual(r.stderr.strip(), "")
            self.assertNotIn("uninstall courierhst", [c[1] for c in sb.pipx_calls()])


class Errors(unittest.TestCase):
    def test_old_python_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, python="old", pipx=True)
            r = sb.run()
            self.assertEqual(r.returncode, 1)
            self.assertIn("3.8", r.stdout + r.stderr)
            self.assertEqual(sb.pipx_calls(), [])

    def test_missing_python_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, python="none")
            r = sb.run()
            self.assertEqual(r.returncode, 1)
            self.assertIn("python3", r.stdout + r.stderr)

    def test_no_pip_no_pipx_exits_1_with_advice(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb = Sandbox(tmp, python="nopip")
            r = sb.run()
            self.assertEqual(r.returncode, 1)
            msg = r.stdout + r.stderr
            self.assertIn("pip", msg)
            self.assertIn("pipx", msg)
            self.assertEqual(snapshot(sb.home), [])


NET_ERR = re.compile(r"network|connection|resolve|Could not find a version|"
                     r"No matching distribution|Temporary failure", re.I)


class RealInstall(unittest.TestCase):
    def install(self, tmp, pybin, extra_env=None):
        sb = Sandbox(tmp, python="none")
        userbin = os.path.join(sb.home, "bin")
        sb.env["PATH"] = os.pathsep.join([pybin, userbin, sb.shim])
        sb.env.update(extra_env or {})
        self.assertIsNone(shutil.which("pipx", path=sb.env["PATH"]))
        r = sb.run()
        out = r.stdout + r.stderr
        if r.returncode != 0:
            if NET_ERR.search(out):
                self.skipTest("no network for pip: " + out[-300:])
            if "externally-managed" in out:
                self.skipTest("system python refuses user installs")
            self.fail(out)
        self.assertIn("pip install --user .", out)
        exe = os.path.join(userbin, "courierhst")
        self.assertTrue(os.path.exists(exe), out)
        h = subprocess.run(["courierhst", "--help"], env=sb.env, cwd=tmp,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True)
        self.assertEqual(h.returncode, 0, h.stdout)
        self.assertIn("14.4 USR Courier HST", h.stdout)
        return sb, exe

    def test_venv_pip_user_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv = os.path.join(tmp, "v")
            r = subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", venv],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if r.returncode != 0:
                self.skipTest("cannot create a venv")
            vbin = os.path.join(venv, "bin")
            if subprocess.run([os.path.join(vbin, "python"), "-m", "pip", "--version"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode != 0:
                self.skipTest("pip not available in the venv")
            sb, exe = self.install(tmp, vbin)
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_system_python_user_install_and_uninstall(self):
        if subprocess.run([REAL_PY, "-m", "pip", "--version"], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode != 0:
            self.skipTest("system python has no pip")
        with tempfile.TemporaryDirectory() as tmp:
            pybin = os.path.join(tmp, "py")
            os.mkdir(pybin)
            os.symlink(REAL_PY, os.path.join(pybin, "python3"))
            sb, exe = self.install(tmp, pybin, {"PIP_BREAK_SYSTEM_PACKAGES": "1"})
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(os.path.exists(exe), r.stdout + r.stderr)
            r = sb.run("--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual((r.stdout + r.stderr).strip(), "")


class Packaging(unittest.TestCase):
    def test_entry_point_target_callable(self):
        mod = importlib.import_module("courierhst.__main__")
        self.assertTrue(callable(getattr(mod, "main", None)))

    def test_pyproject_declares_script(self):
        with open(os.path.join(ROOT, "pyproject.toml")) as f:
            text = f.read()
        self.assertIn("[project.scripts]", text)
        self.assertRegex(text, r'(?m)^courierhst\s*=\s*"courierhst\.__main__:main"')
        self.assertIn('requires-python = ">=3.8"', text)
        self.assertRegex(text, r'test\s*=\s*\[\s*"pyte"\s*\]')


class Readme(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.text = f.read()

    def section(self, heading):
        m = re.search(r"(?ms)^%s\n(.*?)(?=^## |\Z)" % re.escape(heading), self.text)
        self.assertIsNotNone(m, heading)
        return m.group(1)

    def test_install_before_run_after_intro(self):
        i = self.text.index("\n## Install\n")
        self.assertLess(i, self.text.index("\n## Run\n"))
        headings = re.findall(r"(?m)^## .*", self.text)
        self.assertEqual(headings[0], "## Install")
        self.assertEqual(headings[1], "## Run")

    def test_install_section_contents(self):
        s = self.section("## Install")
        for needle in ("./install.sh", "--dry-run", "--uninstall", "pipx install .",
                       "pip install --user .", "python3 -m courierhst",
                       "pip install '.[test]'", "3.8", "80x25", "CP437",
                       "pipx uninstall courierhst", "pip uninstall courierhst"):
            self.assertIn(needle, s)

    def test_run_section_has_no_install_steps(self):
        s = self.section("## Run")
        self.assertNotIn("pip install", s)
        self.assertNotIn("pipx", s)
        self.assertNotIn("install.sh", s)


if __name__ == "__main__":
    unittest.main()
