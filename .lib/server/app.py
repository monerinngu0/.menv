#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

from core import MenvHandler, Router, register_core_routes
from route_loader import load_env_routes


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mserver")

    parser.add_argument(
        "--root",
        default=".",
        help="root directory to serve",
    )

    parser.add_argument(
        "--port",
        default=8000,
        type=int,
        help="port to listen on",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="host to listen on",
    )

    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    menv_root = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))

    if not root.is_dir():
        print(f"mserver: root is not a directory: {root}", file=sys.stderr)
        return 1

    router = Router()

    register_core_routes(router)
    load_env_routes(menv_root, router)

    httpd = ThreadingHTTPServer((args.host, args.port), MenvHandler)
    httpd.root = root  # type: ignore[attr-defined]
    httpd.router = router  # type: ignore[attr-defined]

    print(
        f"mserver: serving {root} on http://{args.host}:{args.port}",
        flush=True,
    )

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nmserver: stopped", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))