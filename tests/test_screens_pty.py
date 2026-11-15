"""d / b / other keys in a real pty."""
import os
import select
import subprocess
import sys
import time
import unittest

try:
    import pty
except ImportError:  # pragma: no cover
    pty = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipIf(pty is None, "pty unavailable")
class SwitchPtyTest(unittest.TestCase):
    def test_d_b_q(self):
        master, slave = pty.openpty()
        env = dict(os.environ, TERM="linux", PYTHONPATH=ROOT)
        proc = subprocess.Popen(
            [sys.executable, "-m", "courierhst", "--warp", "50",
             "--seed", "1"],
            stdin=slave, stdout=slave, stderr=slave, env=env, cwd=ROOT,
            close_fds=True)
        os.close(slave)
        seen = bytearray()

        def wait_for(text, secs=15):
            end = time.monotonic() + secs
            while time.monotonic() < end:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    try:
                        seen.extend(os.read(master, 65536))
                    except OSError:
                        break
                if text in seen:
                    return True
            return False

        try:
            self.assertTrue(wait_for(b"ATDT"), "BBS dialing never started")
            seen.clear()
            os.write(master, b"d")
            self.assertTrue(wait_for(b"GRiDSWEEP"))
            seen.clear()
            os.write(master, b"b")
            self.assertTrue(wait_for(b"ATDT"), "no BBS output after b")
            self.assertNotIn(b"GRiDSWEEP", seen)
            os.write(master, b"q")
            self.assertEqual(proc.wait(timeout=10), 0)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            os.close(master)


if __name__ == "__main__":
    unittest.main()
