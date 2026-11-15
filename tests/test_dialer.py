import io
import random
import re
import time
import unittest
from pathlib import Path

from courierhst import ansi, dialer
from courierhst.dialer import Dialer, Scan
from courierhst.modem import Line


class Stop(Exception):
    pass


class FakeLine:
    """Records what the dialer asks for; never sleeps."""
    height = 25

    def __init__(self):
        self.ops = []
        self.status_text = None
        self.hook = None

    def cls_local(self):
        self.ops.append(("cls",))

    def at(self, row, col, text):
        self.ops.append(("at", row, col, text))

    def pause(self, secs):
        if self.hook:
            self.hook(self)

    def send(self, *a, **k):
        raise AssertionError("dialer must not use Line.send")

    def texts(self):
        return [o for o in self.ops if o[0] == "at"]


def run_until(d, line, cond):
    def hook(_):
        if cond():
            raise Stop()
    line.hook = hook
    with unittest.TestCase().assertRaises(Stop):
        d.run()


class ScanTests(unittest.TestCase):
    def test_order_is_permutation(self):
        s = Scan(random.Random(3), 212)
        self.assertEqual(sorted(s.order), list(range(100)))

    def test_numbers(self):
        s = Scan(random.Random(3), 415)
        for n in range(100):
            self.assertRegex(s.number(n), r"^\(\d{3}\) 555-01\d\d$")
        self.assertEqual(s.number(7), "(415) 555-0107")

    def test_counts_add_up(self):
        s = Scan(random.Random(5), 212)
        self.assertEqual(s.counts()["left"], 100)
        for n in s.order[:60]:
            s.results[n] = s.plan[n]
        c = s.counts()
        self.assertEqual(c["dialed"], 60)
        self.assertEqual(c["left"], 40)
        self.assertEqual(sum(c[r] for r in dialer.RESULTS), 60)
        self.assertFalse(s.done())
        for n in s.order:
            s.results[n] = s.plan[n]
        self.assertTrue(s.done())

    def test_seed(self):
        a, b = Scan(random.Random(1), 300), Scan(random.Random(1), 300)
        self.assertEqual((a.order, a.plan), (b.order, b.plan))
        c = Scan(random.Random(2), 300)
        self.assertNotEqual((a.order, a.plan), (c.order, c.plan))
        self.assertTrue(set(a.plan.values()) <= set(dialer.RESULTS))

    def test_area_codes(self):
        rng = random.Random(9)
        for _ in range(3000):
            a = dialer.new_area(rng)
            self.assertTrue(200 <= a <= 989, a)
            self.assertNotEqual(a % 100, 11, a)


class DialerTests(unittest.TestCase):
    def one_scan_and_a_bit(self, seed=4):
        line = FakeLine()
        d = Dialer(line, random.Random(seed))
        first = d.scan
        run_until(d, line, lambda: d.scan is not first and d.cur is not None)
        return d, line

    def test_output_rules(self):
        d, line = self.one_scan_and_a_bit()
        self.assertIsNone(line.status_text)
        self.assertEqual(sum(1 for o in line.ops if o[0] == "cls"), 2)
        blob = "\n".join(ansi.strip(o[3]) for o in line.texts())
        self.assertIn("GRiDSWEEP", blob)
        for _, row, col, text in line.texts():
            self.assertTrue(1 <= row <= 25, text)
            self.assertTrue(col >= 1, text)
            self.assertLessEqual(col - 1 + ansi.vlen(text), 79, text)
            self.assertNotIn("\n", text)
        for m in re.findall(r"\d{3}-\d{2,4}", blob):
            self.assertTrue(m.startswith("555-01"), m)
        for m in re.findall(r"\((\d+)\)", blob):
            self.assertTrue(200 <= int(m) <= 989, m)

    def test_status_text_while_running(self):
        line = FakeLine()
        d = Dialer(line, random.Random(1))
        seen = []
        run_until(d, line, lambda: seen.append(line.status_text) or len(seen) > 5)
        self.assertRegex(seen[-1], r"^GRiDSWEEP scanning \(\d{3}\) 555-01xx$")

    def test_full_scan_counts(self):
        d, _ = self.one_scan_and_a_bit()
        self.assertNotEqual(d.scan.counts()["dialed"], 100)  # a new scan began

    def test_resume_keeps_scan(self):
        line = FakeLine()
        d = Dialer(line, random.Random(8))
        scan = d.scan
        run_until(d, line, lambda: len(scan.results) >= 12 and d.cur)
        dialed = len(scan.results)
        line.ops.clear()
        run_until(d, line, lambda: len(scan.results) >= dialed + 3)
        self.assertEqual(line.ops[0], ("cls",))
        self.assertIs(d.scan, scan)
        self.assertGreaterEqual(len(scan.results), dialed + 3)
        blob = " ".join(ansi.strip(o[3]) for o in line.texts())
        self.assertIn("GRiDSWEEP", blob)
        rows = {o[1] for o in line.texts()}
        self.assertTrue(set(range(5, 15)) <= rows)  # whole heatmap redrawn

    def test_resume_in_summary(self):
        line = FakeLine()
        d = Dialer(line, random.Random(2))
        scan = d.scan
        run_until(d, line, lambda: scan.done() and d.sumleft < 5)
        line.ops.clear()
        run_until(d, line, lambda: d.sumleft < 3)
        self.assertIs(d.scan, scan)
        self.assertIn("SCAN COMPLETE", " ".join(o[3] for o in line.texts()))

    def test_real_line_at_warp(self):
        out = io.StringIO()
        out.fileno = lambda: (_ for _ in ()).throw(OSError("not a tty"))
        line = Line(warp=3000, out=out, noise=0, exit_on_key=False)
        line._layout()
        d = Dialer(line, random.Random(6))
        first = d.scan
        orig = line.pause

        def pause(s):
            orig(s)
            if d.scan is not first and d.cur is not None:
                raise Stop()
        line.pause = pause
        t0 = time.monotonic()
        with self.assertRaises(Stop):
            d.run()
        self.assertLess(time.monotonic() - t0, 8)
        text = out.getvalue()
        self.assertIn("GRiDSWEEP", text)
        for m in re.findall(r"\d{3}-\d{4}", text):
            self.assertTrue(m.startswith("555-01"), m)
        self.assertIsNone(line.status_text)


class LineAdditions(unittest.TestCase):
    def make(self):
        out = io.StringIO()
        out.fileno = lambda: (_ for _ in ()).throw(OSError("not a tty"))
        line = Line(out=out, noise=0)
        line.top, line.left, line.height = 4, 10, 25
        return line

    def test_at_position(self):
        line = self.make()
        line.at(3, 5, "hi")
        self.assertEqual(line.out.getvalue(), "\x1b[6;15Hhi")

    def test_at_ignores_bad_rows(self):
        line = self.make()
        for row in (0, -1, 26, 99):
            line.at(row, 1, "x")
        self.assertEqual(line.out.getvalue(), "")
        line.at(25, 1, "x")
        self.assertIn("\x1b[28;11Hx", line.out.getvalue())

    def bar(self, line):
        line.cols, line.rows, line.left, line.status_row = 80, 40, 0, 30
        line._buf.clear()
        line._draw_status(force=True)
        return ansi.strip("".join(line._buf))

    def test_status_text(self):
        line = self.make()
        self.assertIn("Offline", self.bar(line))
        line.status_text = "GRiDSWEEP scanning"
        raw = self.bar(line)
        self.assertIn(" GRiDSWEEP scanning", raw)
        self.assertNotIn("Offline", raw)
        line.status_text = None
        self.assertIn("Offline", self.bar(line))


class Safety(unittest.TestCase):
    def test_no_io_in_dialer(self):
        src = (Path(__file__).resolve().parent.parent
               / "courierhst" / "dialer.py").read_text()
        for mod in ("socket", "serial", "subprocess"):
            self.assertIsNone(re.search(
                rf"^\s*(import|from)\s+{mod}\b", src, re.M), mod)
        self.assertNotIn("/dev/", src)
        self.assertNotRegex(src, r"\bopen\(")


if __name__ == "__main__":
    unittest.main()
