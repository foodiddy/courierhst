"""Entry point: python3 -m courierhst"""

import argparse
import random
import sys

from . import __version__, content
from .bbs import DEFAULT_STEP_PAUSE, Session
from .modem import KeyPressed, Line


def _nonneg_float(text):
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}")
    if not v >= 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return v


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="courierhst",
        description="Screensaver: dial up early-90s warez BBSes on a "
                    "14.4 USR Courier HST. Any key exits.")
    p.add_argument("--bps", type=int, default=14400,
                   help="line speed in bits/sec (default 14400)")
    p.add_argument("--handle", help="your handle (default: random)")
    p.add_argument("--seed", type=int, help="random seed for a repeatable run")
    p.add_argument("--no-center", action="store_true",
                   help="draw at top-left instead of centering 80x25")
    p.add_argument("--no-status", action="store_true",
                   help="hide the terminal-program status bar")
    p.add_argument("--noise", type=float, default=0.0007,
                   help="line-noise probability per character "
                        "(default %(default)s, 0 disables)")
    p.add_argument("--xfer-speedup", type=float, default=40,
                   help="time compression for Zmodem downloads "
                        "(default %(default)s, 1 = real time)")
    p.add_argument("--step-pause", type=_nonneg_float, metavar="SECONDS",
                   default=DEFAULT_STEP_PAUSE,
                   help="seconds to linger before moving on to the next menu "
                        "command, message, file prompt or door move "
                        "(default 5, 0 disables; scaled by --warp)")
    p.add_argument("--no-exit-on-key", action="store_true",
                   help="ignore keypresses (exit with Ctrl-C)")
    p.add_argument("--calls", type=int, default=0,
                   help="number of BBS calls before exiting "
                        "(default %(default)s = forever)")
    p.add_argument("--warp", type=float, default=1.0,
                   help="speed up everything by this factor, for previews "
                        "(default %(default)s)")
    p.add_argument("--board-style", choices=["renegade", "telegard", "mystic", "pcboard"],
                   help="force every board to this BBS software style "
                        "(default: random mix)")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)

    if not sys.stdout.isatty():
        p.error("stdout must be a terminal")

    rng = random.Random(a.seed)
    user = a.handle or content.handle(rng)
    try:
        with Line(bps=a.bps, center=not a.no_center, status=not a.no_status,
                  noise=a.noise, exit_on_key=not a.no_exit_on_key,
                  warp=a.warp) as line:
            n = 0
            while not a.calls or n < a.calls:
                Session(line, rng, user, xfer_speedup=a.xfer_speedup,
                        style=a.board_style,
                        step_pause=a.step_pause).run()
                n += 1
                line.pause(rng.uniform(2, 5))
    except (KeyPressed, KeyboardInterrupt):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
