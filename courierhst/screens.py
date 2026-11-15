"""Switch between the screensavers: BBS sessions and the dialer scan."""

import time

from .modem import KeyPressed, Rotate

BBS, DIALER = "bbs", "dialer"
_OTHER = {BBS: DIALER, DIALER: BBS}
_KEY_SCREEN = {"d": DIALER, "b": BBS}


def run_screens(line, rng, start, rotate_minutes, calls, make_session,
                dialer, warp=1.0):
    """Run BBS / dialer screens until exit. Returns main's exit code (0)."""
    screen = start
    done = 0  # finished BBS calls

    def arm():
        # Fresh --rotate deadline, in warped time like everything else.
        if rotate_minutes:
            line.rotate_at = time.monotonic() + rotate_minutes * 60 / warp

    arm()
    while True:
        try:
            if screen == BBS:
                line.status_text = None
                while not calls or done < calls:
                    make_session().run()
                    done += 1
                    if calls and done >= calls:
                        break
                    line.pause(rng.uniform(2, 5))
                return 0
            dialer.run()
        except Rotate:
            screen = _OTHER[screen]
            arm()
        except KeyPressed as k:
            target = _KEY_SCREEN.get(k.key.lower()) if k.key else None
            if target is None:
                return 0
            if target != screen:
                screen = target
                arm()
            # same screen's key: BBS drops the call and starts anew, the
            # dialer resumes
