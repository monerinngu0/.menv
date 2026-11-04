#!/usr/bin/env bash
# Stage 0: acquire a compatible interpreter. Does not run setup definitions.
set -euo pipefail
MENV_ROOT="${MENV_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
export MENV_ROOT
source "$MENV_ROOT/.lib/python.sh"

bootstrap_yes=0
bootstrap_managed=0
for argument in "$@"; do
    case "$argument" in
        -y|--yes) bootstrap_yes=1 ;;
        --managed) bootstrap_managed=1 ;;
        --help)
            echo 'Usage: bash bootstrap.sh [--managed] [-y|--yes]'
            echo '--managed: install/refresh the dedicated Python 3.13 runtime using uv'
            exit 0 ;;
        *) echo "bootstrap: unknown argument: $argument" >&2; exit 2 ;;
    esac
done

bootstrap_runtime="${XDG_DATA_HOME:-$HOME/.local/share}/menv/runtime"
if [ "$bootstrap_managed" = 0 ] && [ -n "${MENV_PYTHON:-}" ]; then
    bootstrap_python="$(menv_python)"
    echo "Python available: $bootstrap_python"
elif [ "$bootstrap_managed" = 0 ] && bootstrap_python="$(menv_python 2>/dev/null)"; then
    echo "Python available: $bootstrap_python"
else
    cat <<EOF
Download the uv installer from https://astral.sh/uv/install.sh.
Install uv under $bootstrap_runtime/uv and managed Python 3.13 under $bootstrap_runtime/python.
Create $bootstrap_runtime/bin/python3 pointing to that managed interpreter.
Existing system Python and shell profiles are not changed.
EOF
    if [ "$bootstrap_yes" != 1 ]; then
        read -r -p 'Proceed? [y/N] ' bootstrap_answer || bootstrap_answer=''
        case "$bootstrap_answer" in y|Y|yes|YES) ;; *) exit 1 ;; esac
    fi
    case "$bootstrap_runtime" in /*) ;; *) echo 'bootstrap: XDG_DATA_HOME must be absolute' >&2; exit 1 ;; esac
    command -v curl >/dev/null || { echo 'bootstrap: curl is required to download uv' >&2; exit 1; }
    bootstrap_tmp="$(mktemp -d)"
    trap 'rm -rf -- "$bootstrap_tmp"' EXIT
    if [ ! -x "$bootstrap_runtime/uv/uv" ] || [ "$bootstrap_managed" = 1 ]; then
        curl -fsSL https://astral.sh/uv/install.sh -o "$bootstrap_tmp/install.sh"
        UV_UNMANAGED_INSTALL="$bootstrap_runtime/uv" sh "$bootstrap_tmp/install.sh"
    fi
    export UV_PYTHON_INSTALL_DIR="$bootstrap_runtime/python"
    export UV_PYTHON_BIN_DIR="$bootstrap_runtime/bin"
    export UV_PYTHON_INSTALL_BIN=0
    "$bootstrap_runtime/uv/uv" --no-config python install --upgrade 3.13
    bootstrap_python="$("$bootstrap_runtime/uv/uv" --no-config python find --managed-python 3.13)"
    "$bootstrap_python" -I -c 'import sys, tomllib, venv, ensurepip; assert sys.version_info >= (3, 11)'
    mkdir -p "$bootstrap_runtime/bin"
    ln -sfn -- "$bootstrap_python" "$bootstrap_runtime/bin/python3"
fi

cat <<'EOF'
Ready. Add this to ~/.bashrc, adjusting MENV_ROOT to your clone location:
export MENV_ROOT="$HOME/.menv"
export PATH="${XDG_DATA_HOME:-$HOME/.local/share}/menv/runtime/bin:$MENV_ROOT/.bin:$PATH"
me() { source "$MENV_ROOT/.bin/me" "$@"; }

Then open a new Bash and run: setup init kyopro
EOF
