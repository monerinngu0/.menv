#!/usr/bin/env bash

MENV_ROOT="${MENV_ROOT:-$HOME/.menv}"

GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
BLUE='\033[34m'
RESET='\033[0m'

ok()   { printf "${GREEN}[OK]${RESET}   %s\n" "$1"; }
ng()   { printf "${RED}[NG]${RESET}   %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${RESET} %s\n" "$1"; }
info() { printf "${BLUE}[INFO]${RESET} %s\n" "$1"; }
skip() { printf "${YELLOW}[SKIP]${RESET} %s\n" "$1"; }

ask() {
    read -rp "$1 [Y/n]: " ans
    case "$ans" in
        ""|y|Y|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

run_quiet() {
    local message="$1"
    shift

    local tmp
    tmp="$(mktemp)"

    printf "%s" "$message"

    "$@" >"$tmp" 2>&1 &
    local pid=$!

    local dots=0

    while kill -0 "$pid" 2>/dev/null; do
        sleep 0.5
        printf "."
        dots=$((dots + 1))

        if [ "$dots" -ge 6 ]; then
            printf "\r%s      \r%s" "$message" "$message"
            dots=0
        fi
    done

    local status=0
    wait "$pid" || status=$?

    if [ "$status" -eq 0 ]; then
        printf "\r%s done\n" "$message"
        rm -f "$tmp"
        return 0
    fi

    printf "\r%s failed\n" "$message"
    ng "command failed"
    echo "---- log ----"
    cat "$tmp"
    echo "-------------"
    rm -f "$tmp"
    return "$status"
}