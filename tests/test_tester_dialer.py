"""Tester acceptance checks for the GRiDSWEEP dial-scan module (DIAL-1)."""
import io
import random
import re
import time
import unittest
from collections import Counter
from pathlib import Path

from courierhst import ansi, dialer
from courierhst.dialer import RESULTS, Dialer, Scan
from courierhst.modem import Line

ROOT = Path(__file__).resolve().parent.parent
LABELS = {"BUSY": "busy", "VOICE": "voice", "NO ANSWER": "noanswer",
          "CARRIER": "carrier", "TONE": "tone"}
PHONE_RE = re.compile(r"\d{3}[-. ]?\d{4}")


class Stop(Exception):
    pass


class FakeOut(io.StringIO):
    def fileno(self):
        raise OSError("not a tty")


class RecLine:
    """Fake Line: records calls in order, keeps simulated time, models the
    80x25 window as a character grid (pipe codes stripped)."""
    height = 25

    def __init__(self):
        self.ev = []
        self.status_text = None
        self.status_seen = []
        self.t = 0.0
        self.grid = [[" "] * 80 for _ in range(26)]
        self.hook = None

    def cls_local(self):
        self.ev.append(("cls", self.t))
        self.grid = [[" "] * 80 for _ in range(26)]

    def at(self, row, col, text):
        self.ev.append(("at", row, col, text, self.t))
        if self.status_text is not None:
            self.status_seen.append(self.status_text)
        if self.hook and self.hook(self, ("at", row, col, text)):
            raise Stop()
        vis = ansi.strip(text)
        for i, ch in enumerate(vis):
            c = col - 1 + i
            if 1 <= row <= 25 and 0 <= c < 80:
                self.grid[row][c] = ch

    def pause(self, secs):
        assert secs >= 0
        self.ev.append(("pause", secs, self.t))
        self.t += secs
        if self.hook and self.hook(self, ("pause", secs)):
            raise Stop()

    def send(self, *a, **k):
        raise AssertionError("dialer must not call Line.send")

    def row(self, r):
        return "".join(self.grid[r])

    def texts(self):
        return [e[3] for e in self.ev if e[0] == "at"]


def run_scans(seed, stop):
    """Run a Dialer on a RecLine until stop(line, dialer, event) is true."""
    line = RecLine()
    d = Dialer(line, random.Random(seed))
    line.hook = lambda ln, ev: stop(ln, d, ev)
    try:
        d.run()
    except Stop:
        pass
    else:
        raise AssertionError("run() returned")
    return line, d


def into_next_scan(first_holder):
    def stop(ln, d, ev):
        if first_holder[0] is None:
            first_holder[0] = d.scan
        return d.scan is not first_holder[0] and len(d.scan.results) >= 2
    return stop


def number_events(line):
    """Per number: (number, dial secs, total secs, ring numbers, result)."""
    out = []
    cur = None
    for e in line.ev:
        if e[0] == "pause" and cur is not None:
            cur["t"] += e[1]
            if cur["ring0"] is None:
                cur["dial"] += e[1]
        if e[0] != "at" or e[1] not in (14, 15) or e[2] != 3:
            continue
        vis = ansi.strip(e[3]).strip()
        if e[1] == 14:
            num = vis
            continue
        if vis == "DIALING":
            cur = {"num": num, "dial": 0.0, "t": 0.0, "rings": [],
                   "ring0": None}
        elif vis.startswith("RINGING") and cur is not None:
            cur["ring0"] = cur["ring0"] if cur["ring0"] is not None else cur["t"]
            cur["rings"].append(int(vis.split()[1]))
        elif vis in LABELS and cur is not None:
            out.append((cur["num"], cur["dial"], cur["t"], cur["rings"],
                        LABELS[vis]))
            cur = None
    return out


class ScanModel(unittest.TestCase):
    def test_permutation_numbers_counts(self):
        s = Scan(random.Random(1), 212)
        self.assertEqual(sorted(s.order), list(range(100)))
        for n in range(100):
            self.assertRegex(s.number(n), r"^\(212\) 555-01\d\d$")
            self.assertEqual(s.number(n)[-2:], f"{n:02d}")
        self.assertEqual(s.results, {})
        self.assertFalse(s.done())
        c = s.counts()
        self.assertEqual(set(c), {"dialed", "left", *RESULTS})
        self.assertEqual((c["dialed"], c["left"]), (0, 100))
        for i, n in enumerate(s.order[:37]):
            s.results[n] = RESULTS[i % 5]
        c = s.counts()
        self.assertEqual(c["dialed"], 37)
        self.assertEqual(c["dialed"] + c["left"], 100)
        self.assertEqual(sum(c[r] for r in RESULTS), 37)
        for n in s.order[37:]:
            s.results[n] = "voice"
        self.assertTrue(s.done())

    def test_seeds(self):
        a, b = Scan(random.Random(9), 312), Scan(random.Random(9), 312)
        self.assertEqual(a.order, b.order)
        self.assertEqual(a.plan, b.plan)
        c = Scan(random.Random(10), 312)
        self.assertTrue(a.order != c.order or a.plan != c.plan)

    def test_weights(self):
        rng = random.Random(3)
        tally = Counter()
        for _ in range(60):
            tally.update(Scan(rng, 415).plan.values())
        total = sum(tally.values())
        self.assertEqual(set(tally), set(RESULTS))
        want = {"voice": 45, "noanswer": 30, "busy": 12, "carrier": 7,
                "tone": 6}
        for r, w in want.items():
            self.assertAlmostEqual(100 * tally[r] / total, w, delta=3.5,
                                   msg=(r, tally))

    def test_area_codes(self):
        rng = random.Random(0)
        seen = set()
        for _ in range(5000):
            a = dialer.new_area(rng)
            self.assertTrue(200 <= a <= 989, a)
            self.assertNotEqual(a % 100, 11, a)
            seen.add(a)
        self.assertGreater(len(seen), 500)


class DialerRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        holder = [None]
        t0 = time.monotonic()
        cls.line, cls.d = run_scans(4, into_next_scan(holder))
        cls.real = time.monotonic() - t0
        cls.first = holder[0]

    def test_fast_and_no_send(self):
        self.assertLess(self.real, 5)
        self.assertTrue(self.first.done())
        self.assertIsNot(self.d.scan, self.first)

    def test_lines_fit(self):
        for e in self.line.ev:
            if e[0] != "at":
                continue
            _, row, col, text, _ = e
            self.assertTrue(1 <= row <= 25, e)
            self.assertGreaterEqual(col, 1, e)
            self.assertNotIn("\n", text)
            self.assertNotIn("\r", text)
            self.assertLessEqual(col - 1 + ansi.vlen(text), 79, e)

    def test_brand_and_numbers(self):
        allt = "\n".join(ansi.strip(t) for t in self.line.texts())
        self.assertIn("GRiDSWEEP", allt)
        self.assertIn("2.1", allt)
        self.assertIn("Crossbar Coders", allt)
        self.assertIn("SCAN COMPLETE", allt)
        for m in PHONE_RE.findall(allt):
            self.assertRegex(m, r"^555-01\d\d$")
        for m in re.findall(r"\((\d{3})\) 555", allt):
            a = int(m)
            self.assertTrue(200 <= a <= 989 and a % 100 != 11, m)

    def test_status_text(self):
        self.assertTrue(self.line.status_seen)
        for s in self.line.status_seen:
            self.assertRegex(s, r"^GRiDSWEEP scanning \(\d{3}\) 555-01xx$")
        self.assertIn(f"({self.first.area})", self.line.status_seen[0])
        self.assertIn(f"({self.d.scan.area})", self.line.status_seen[-1])
        self.assertIsNone(self.line.status_text)

    def test_one_full_paint_per_scan(self):
        cls = [e for e in self.line.ev if e[0] == "cls"]
        self.assertEqual(len(cls), 2)
        self.assertEqual(self.line.ev[0][0], "cls")
        # after the first paint, no burst between waits comes near a
        # whole-screen repaint, and the frame borders are never redrawn
        ev = self.line.ev
        first_pause = next(i for i, e in enumerate(ev) if e[0] == "pause")
        full = sum(1 for e in ev[:first_pause] if e[0] == "at")
        burst, worst = 0, 0
        for e in ev[first_pause:]:
            if e[0] == "pause":
                burst = 0
            elif e[0] == "cls":
                break
            else:
                burst += 1
                worst = max(worst, burst)
                self.assertFalse(e[2] == 1 and ansi.strip(e[3])[:1] in
                                 "┌└", e)
        self.assertLess(worst, full / 2, (worst, full))

    def test_every_number_once_with_plan(self):
        nums = number_events(self.line)
        first = [n for n in nums if n[0].startswith(f"({self.first.area})")]
        self.assertEqual(len(first), 100)
        self.assertEqual(len({n[0] for n in first}), 100)
        order = [int(n[0][-2:]) for n in first]
        self.assertEqual(order, self.first.order)
        for num, _, _, _, res in first:
            n = int(num[-2:])
            self.assertEqual(res, self.first.plan[n])
            self.assertEqual(self.first.results[n], res)

    def test_timing(self):
        nums = number_events(self.line)
        self.assertGreaterEqual(len(nums), 101)
        for num, dial, total, rings, res in nums:
            self.assertTrue(1 <= dial <= 2.01, (num, dial))
            ringing = total - dial
            lo, hi = {"voice": (3, 10), "busy": (3, 10), "carrier": (5, 12),
                      "tone": (5, 12), "noanswer": (25, 25)}[res]
            self.assertTrue(lo - 0.01 <= ringing <= hi + 0.01,
                            (num, res, ringing))
            # ring ticks count up 1, 2, 3 ... about every 3 s
            self.assertEqual(rings, list(range(1, len(rings) + 1)), num)
            self.assertLessEqual(abs(len(rings) - ringing / 3), 1.5,
                                 (num, rings, ringing))

    def test_summary_then_new_scan(self):
        ev = self.line.ev
        i_sum = next(i for i, e in enumerate(ev) if e[0] == "at"
                     and "SCAN COMPLETE" in e[3])
        i_cls = next(i for i, e in enumerate(ev) if e[0] == "cls" and i > 0)
        self.assertLess(i_sum, i_cls)
        shown = sum(e[1] for e in ev[i_sum:i_cls] if e[0] == "pause")
        self.assertAlmostEqual(shown, 8, delta=0.5)
        self.assertNotEqual(self.d.scan.area, self.first.area)
        # fresh grid after the new paint: most cells undialed again
        self.assertLessEqual(len(self.d.scan.results), 3)
        hm = [self.line.row(r)[45:75] for r in range(5, 15)]
        cells = "".join(h[1::3] for h in hm)
        self.assertEqual(len(cells), 100)
        self.assertGreaterEqual(Counter(cells).most_common(1)[0][1], 95)


class Screen(unittest.TestCase):
    def snap(self, seed, when):
        snaps = {}

        def stop(ln, d, ev):
            if "mid" not in snaps and len(d.scan.results) == 50 \
                    and d.cur is not None and ev[0] == "pause":
                snaps["mid"] = ([ln.row(r) for r in range(26)],
                                d.cur["n"], dict(d.scan.results),
                                d.scan.counts())
            if ev[0] == "at" and "SCAN COMPLETE" in ev[3] \
                    and "end" not in snaps:
                snaps["end"] = ([ln.row(r) for r in range(26)], None,
                                dict(d.scan.results), d.scan.counts())
                return True
            return False
        run_scans(seed, stop)
        return snaps[when]

    def heat(self, rows):
        """Locate the 10x10 heatmap via its row labels; returns cells[n]."""
        cells = {}
        lab = [i for i in range(26) if re.search(r"\b0_", rows[i])]
        self.assertTrue(lab, "no heatmap row label 0_")
        top = lab[0]
        header = rows[top - 1]
        # cell characters sit under the column digits of the header row
        cols = [m.start() for m in re.finditer(r"\d", header)][-10:]
        self.assertEqual([header[c] for c in cols],
                         [str(i) for i in range(10)])
        for t in range(10):
            row = rows[top + t]
            self.assertIn(f"{t}_", row)
            for o in range(10):
                cells[t * 10 + o] = row[cols[o]]
        return cells, header

    def test_heatmap_mid_scan(self):
        rows, cur, results, counts = self.snap(5, "mid")
        cells, header = self.heat(rows)
        by_res = {}
        for n, res in results.items():
            by_res.setdefault(res, set()).add(cells[n])
        for res, chars in by_res.items():
            self.assertEqual(len(chars), 1, (res, chars))
        used = [next(iter(c)) for c in by_res.values()]
        self.assertEqual(len(set(used)), len(used), by_res)
        undialed = {cells[n] for n in range(100)
                    if n not in results and n != cur}
        self.assertEqual(len(undialed), 1)
        self.assertNotIn(next(iter(undialed)), used)
        self.assertNotIn(cells[cur], used + list(undialed))
        # legend names every result type
        text = "\n".join(rows).lower()
        for word in ("busy", "voice", "no answer", "carrier", "tone"):
            self.assertIn(word, text)
        # current number panel shows the number in progress
        area = re.search(r"\((\d{3})\) 555-0100", text)
        self.assertTrue(area)
        self.assertIn(f"555-01{cur:02d}", text)
        # stats values match the scan
        for name, key in (("dialed", "dialed"), ("left", "left")):
            row = next(r for r in rows if re.search(rf"\b{name}\b", r.lower()))
            self.assertIn(str(counts[key]), row, (name, row))
        self.assertTrue(re.search(r"\d\d:\d\d:\d\d", text))

    def test_full_scan_screen(self):
        rows, _, results, counts = self.snap(8, "end")
        self.assertEqual(len(results), 100)
        self.assertEqual(counts["left"], 0)
        text = "\n".join(rows)
        self.assertIn("GRiDSWEEP", rows[1])
        # log shows finished numbers with results
        log = re.findall(r"\(\d{3}\) 555-01(\d\d)\s+(BUSY|VOICE|NO ANSWER|"
                         r"CARRIER|TONE)", text)
        self.assertGreaterEqual(len(log), 3)
        for nn, lab in log:
            self.assertEqual(results[int(nn)], LABELS[lab])


class Resume(unittest.TestCase):
    def test_resume_mid_ringing(self):
        line = RecLine()
        d = Dialer(line, random.Random(11))
        state = {"n": 0}

        def stop(ln, ev):
            if ev[0] == "pause" and len(d.scan.results) == 30 and d.cur \
                    and d.cur.get("stage") == 1 and state["n"] == 0:
                state["n"] = 1
                return True
            return False
        line.hook = stop
        with self.assertRaises(Stop):
            d.run()
        self.assertIsNone(line.status_text)
        scan, cur_n = d.scan, d.cur["n"]
        mark = len(line.ev)

        holder = [scan]
        line.hook = lambda ln, ev: (d.scan is not holder[0]
                                    and len(d.scan.results) >= 1)
        with self.assertRaises(Stop):
            d.run()
        after = line.ev[mark:]
        self.assertEqual(after[0][0], "cls")
        # the whole screen is redrawn before any waiting
        first_pause = next(i for i, e in enumerate(after) if e[0] == "pause")
        rows = {e[1] for e in after[:first_pause] if e[0] == "at"}
        self.assertTrue(set(range(1, 25)) <= rows, sorted(rows))
        painted = "\n".join(ansi.strip(e[3]) for e in after[:first_pause]
                            if e[0] == "at")
        self.assertIn("GRiDSWEEP", painted)
        self.assertIn(f"555-01{cur_n:02d}", painted)
        self.assertIn("30", painted)
        # the same scan carried on and finished with all 100 numbers
        self.assertTrue(scan.done())
        self.assertEqual(scan.results, scan.plan)
        dialed = [int(n[0][-2:]) for n in number_events(line)
                  if n[0].startswith(f"({scan.area})")]
        self.assertEqual(sorted(set(dialed)), list(range(100)))
        self.assertEqual(len(dialed), 100)

    def test_resume_during_summary(self):
        line = RecLine()
        d = Dialer(line, random.Random(12))
        seen = {"sum": 0}

        def stop(ln, ev):
            if ev[0] == "at" and "SCAN COMPLETE" in ev[3]:
                seen["sum"] += 1
            return ev[0] == "pause" and seen["sum"] == 3
        line.hook = stop
        with self.assertRaises(Stop):
            d.run()
        scan = d.scan
        self.assertTrue(scan.done())
        mark = len(line.ev)
        t_mark = line.t
        line.hook = lambda ln, ev: d.scan is not scan
        with self.assertRaises(Stop):
            d.run()
        after = line.ev[mark:]
        self.assertEqual(after[0][0], "cls")
        first_pause = next(i for i, e in enumerate(after) if e[0] == "pause")
        self.assertTrue(any("SCAN COMPLETE" in e[3]
                            for e in after[:first_pause] if e[0] == "at"))
        self.assertEqual(len(scan.results), 100)
        # summary did not restart from 8 s: total summary time stays ~8 s
        self.assertLess(line.t - t_mark, 8)


class RealLine(unittest.TestCase):
    def test_full_warp(self):
        out = FakeOut()
        line = Line(warp=3000, out=out, noise=0, exit_on_key=False)
        line._layout()
        d = Dialer(line, random.Random(21))
        first = d.scan
        orig = line.pause

        def pause(s):
            orig(s)
            if d.scan is not first and len(d.scan.results) >= 1:
                raise Stop()
        line.pause = pause
        line.send = lambda *a, **k: self.fail("send called")
        t0 = time.monotonic()
        with self.assertRaises(Stop):
            d.run()
        self.assertLess(time.monotonic() - t0, 6)
        raw = out.getvalue()
        self.assertIn("GRiDSWEEP", raw)
        self.assertIn(" GRiDSWEEP scanning (", ansi.strip(raw))
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b[78]", "\n", raw)
        for m in PHONE_RE.findall(plain):
            self.assertRegex(m, r"^555-01\d\d$")
        # every cursor jump lands inside the window or on the status row
        for r, c in re.findall(r"\x1b\[(\d+);(\d+)H", raw):
            self.assertTrue(line.top <= int(r) <= line.status_row, r)
            self.assertTrue(1 <= int(c) <= 80, c)
        self.assertIsNone(line.status_text)


class LineAt(unittest.TestCase):
    def make(self, top, left):
        line = Line(out=FakeOut(), noise=0)
        line._layout()
        line.top, line.left, line.height = top, left, 25
        line._buf.clear()
        line.out.seek(0)
        line.out.truncate(0)
        return line

    def test_positions(self):
        for top, left in ((1, 0), (5, 20), (3, 7)):
            line = self.make(top, left)
            line.at(1, 1, "|15A")
            line.at(25, 80, "Z")
            line.at(12, 40, "mid")
            raw = line.out.getvalue()
            self.assertIn(f"\x1b[{top};{left + 1}H", raw)
            self.assertIn(f"\x1b[{top + 24};{left + 80}HZ", raw)
            self.assertIn(f"\x1b[{top + 11};{left + 40}Hmid", raw)
            self.assertIn("A", ansi.strip(raw))
            self.assertNotIn("|15", raw)

    def test_out_of_range(self):
        line = self.make(2, 10)
        for r in (0, -1, line.height + 1, 100):
            line.at(r, 5, "nope")
        self.assertEqual(line.out.getvalue() + "".join(line._buf), "")

    def bar(self, line):
        line._buf.clear()
        line._draw_status(force=True)
        return ansi.strip("".join(line._buf))

    def test_status_text(self):
        line = self.make(1, 0)
        old = self.bar(line)
        self.assertIn(" Offline", old)
        line.status_text = "GRiDSWEEP scanning (212) 555-01xx"
        new = self.bar(line)
        self.assertIn(" GRiDSWEEP scanning (212) 555-01xx", new)
        self.assertNotIn("Offline", new)
        line.status_text = "x" * 200
        self.assertLessEqual(len(self.bar(line).rstrip("\n")),
                             len(old) + 0)
        line.status_text = None
        self.assertEqual(self.bar(line), old)
        line.dialing, line.status_name = True, "The Board"
        self.assertIn("Dialing The Board", self.bar(line))
        line.status_text = "GRiDSWEEP scanning (212) 555-01xx"
        self.assertNotIn("Dialing", self.bar(line))


class Safety(unittest.TestCase):
    def test_no_device_io(self):
        src = (ROOT / "courierhst" / "dialer.py").read_text(encoding="utf-8")
        for mod in ("socket", "serial", "subprocess", "os", "pty", "tty",
                    "termios", "fcntl", "select"):
            self.assertNotRegex(src, rf"(?m)^\s*(import|from)\s+{mod}\b", mod)
        self.assertNotIn("/dev/", src)
        self.assertNotRegex(src, r"\bopen\s*\(")
        self.assertNotRegex(src, r"\.send\s*\(")
        self.assertNotRegex(src, r"\btime\.sleep\b")


if __name__ == "__main__":
    unittest.main()
