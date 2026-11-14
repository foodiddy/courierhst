#!/bin/sh
# Installs courierhst for the current user. Never uses sudo, never edits rc files.

usage() {
    cat <<'USAGE'
Usage: ./install.sh [--dry-run] [--uninstall] [--help]

Installs courierhst for the current user (no sudo needed).
Prefers pipx; falls back to python3 -m pip install --user.

  --uninstall   remove courierhst with the tool that installed it
  --dry-run     print the commands that would run, change nothing
  --help        show this help
USAGE
}

DRY=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --uninstall) UNINSTALL=1 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "install.sh: unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

case "$0" in
    */*) cd "${0%/*}" || exit 1 ;;
esac

run() {
    if [ "$DRY" = 1 ]; then
        echo "would run: $*"
    else
        echo "+ $*"
        "$@"
    fi
}

have() { command -v "$1" >/dev/null 2>&1; }

if ! have python3; then
    echo "install.sh: python3 not found. Install Python 3.8 or newer first." >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
    ver=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
    echo "install.sh: python3 is version ${ver:-unknown}; courierhst needs 3.8 or newer." >&2
    exit 1
fi

externally_managed() {
    stdlib=${COURIERHST_STDLIB_DIR:-}
    [ -n "$stdlib" ] || stdlib=$(python3 -c "import sysconfig; print(sysconfig.get_path('stdlib'))" 2>/dev/null)
    [ -n "$stdlib" ] && [ -f "$stdlib/EXTERNALLY-MANAGED" ]
}

managed_hint() {
    echo "install.sh: this system's Python is externally managed (Debian 12+/Ubuntu 23.04+)." >&2
    echo "pipx is needed: sudo apt install pipx, then re-run ./install.sh" >&2
}

HAVE_PIPX=0
have pipx && HAVE_PIPX=1
HAVE_PIP=0
python3 -m pip --version >/dev/null 2>&1 && HAVE_PIP=1

if [ "$UNINSTALL" = 1 ]; then
    done_any=0
    if [ "$DRY" = 1 ]; then
        [ "$HAVE_PIPX" = 1 ] && run pipx uninstall courierhst
        run python3 -m pip uninstall -y courierhst
        exit 0
    fi
    if [ "$HAVE_PIPX" = 1 ] && pipx list --short 2>/dev/null | grep -q '^courierhst '; then
        run pipx uninstall courierhst && done_any=1
    fi
    if [ "$HAVE_PIP" = 1 ] && python3 -m pip show courierhst >/dev/null 2>&1; then
        run python3 -m pip uninstall -y courierhst
        python3 -m pip show courierhst >/dev/null 2>&1 || done_any=1
    fi
    [ "$done_any" = 1 ] && echo "courierhst removed."
    exit 0
fi

if [ "$HAVE_PIPX" = 1 ]; then
    run pipx install --force . || exit 1
    BINDIR=
    if [ "$DRY" = 0 ]; then
        BINDIR=$(pipx environment --value PIPX_BIN_DIR 2>/dev/null)
    fi
    [ -n "$BINDIR" ] || BINDIR="$HOME/.local/bin"
elif [ "$HAVE_PIP" = 1 ]; then
    if externally_managed; then
        managed_hint
        exit 3
    fi
    if [ "$DRY" = 1 ]; then
        run python3 -m pip install --user .
    else
        echo "+ python3 -m pip install --user ."
        pip_out=$(python3 -m pip install --user . 2>&1)
        pip_rc=$?
        if [ "$pip_rc" != 0 ] && printf '%s\n' "$pip_out" | grep -q 'externally-managed-environment'; then
            managed_hint
            exit 3
        fi
        printf '%s\n' "$pip_out"
        [ "$pip_rc" = 0 ] || exit 1
    fi
    BASE=$(python3 -m site --user-base 2>/dev/null)
    [ -n "$BASE" ] || BASE="$HOME/.local"
    BINDIR="$BASE/bin"
else
    echo "install.sh: neither pipx nor pip is available." >&2
    echo "Get pip:   python3 -m ensurepip --user" >&2
    echo "Or install pipx or python3-pip with your distro's package manager (e.g. 'apt install pipx')." >&2
    echo "See https://pipx.pypa.io/ and https://pip.pypa.io/en/stable/installation/" >&2
    exit 1
fi

case ":$PATH:" in
    *":$BINDIR:"*) ;;
    *)
        case "${SHELL:-}" in
            */zsh) rc="~/.zshrc" ;;
            */bash) rc="~/.bashrc" ;;
            *) rc="~/.profile" ;;
        esac
        echo
        echo "$BINDIR is not on your PATH. Add this line to $rc (usually) and restart your shell:"
        echo "  export PATH=\"$BINDIR:\$PATH\""
        ;;
esac

echo
if [ "$DRY" = 1 ]; then
    echo "Dry run: nothing was changed."
else
    echo "Done. Run it with:  courierhst"
fi
echo "Tip: use a terminal of at least 80x25 and a VGA/CP437-style font for the best look."
