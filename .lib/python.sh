#!/usr/bin/env bash
# Select a setup-capable interpreter without modifying PATH or system Python.
menv_python() {
    local candidate
    for candidate in "${MENV_PYTHON:-}" \
        "${XDG_DATA_HOME:-$HOME/.local/share}/menv/runtime/bin/python3" python3; do
        [ -n "$candidate" ] || continue
        if "$candidate" -I -c 'import sys, tomllib, venv, ensurepip; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
            "$candidate" -I -c 'import sys; print(sys.executable)'
            return
        fi
        if [ -n "${MENV_PYTHON:-}" ] && [ "$candidate" = "$MENV_PYTHON" ]; then
            echo 'menv: MENV_PYTHON must support Python 3.11+, tomllib, venv and ensurepip' >&2
            return 1
        fi
    done
    echo 'menv: compatible Python missing; run bash "$MENV_ROOT/bootstrap.sh"' >&2
    return 1
}
