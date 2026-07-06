from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


SERVER_STARTED = time.time()


def json_bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_join(root: Path, raw_path: str) -> Path:
    if not raw_path:
        raise ValueError("path is required")

    if raw_path.startswith("/") or raw_path.startswith("\\"):
        raise ValueError("absolute path is not allowed")

    raw_path = unquote(raw_path).replace("\\", "/")
    raw_parts = [part for part in raw_path.split("/") if part]

    if any(part == ".." for part in raw_parts):
        raise ValueError("path is outside root")

    raw_path = posixpath.normpath("/" + raw_path).lstrip("/")

    if raw_path in {"", "."}:
        raise ValueError("path is required")

    target = (root / raw_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("path is outside root")

    return target


@dataclass
class RequestContext:
    handler: "MenvHandler"
    root: Path
    method: str
    path: str
    query: dict[str, list[str]]
    params: dict[str, str]

    def query_one(self, name: str, default: str = "") -> str:
        values = self.query.get(name)
        return values[0] if values else default

    def safe_path(self, name: str = "path") -> Path:
        return safe_join(self.root, self.query_one(name))

    def read_body(self) -> bytes:
        length = self.handler.headers.get("Content-Length")
        if length is None:
            raise ValueError("Content-Length is required")
        try:
            size = int(length)
        except ValueError:
            raise ValueError("invalid Content-Length")
        return self.handler.rfile.read(size)


class Router:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], object] = {}
        self.pattern_routes: list[tuple[str, re.Pattern[str], object]] = []

    def add(self, method: str, path: str, func: object) -> None:
        if not path.startswith("/"):
            raise ValueError(f"route path must start with /: {path}")
        if "<" in path and ">" in path:
            pattern = re.sub(r"<([A-Za-z_][A-Za-z0-9_]*)>", r"(?P<\1>[^/]+)", path)
            self.pattern_routes.append((method.upper(), re.compile("^" + pattern + "$"), func))
            return
        self.routes[(method.upper(), path)] = func

    def get(self, path: str, func: object) -> None:
        self.add("GET", path, func)

    def post(self, path: str, func: object) -> None:
        self.add("POST", path, func)

    def match(self, method: str, path: str):
        method = method.upper()
        func = self.routes.get((method, path))
        if func is not None:
            return func, {}

        for route_method, pattern, route_func in self.pattern_routes:
            if route_method != method:
                continue
            match = pattern.match(path)
            if match:
                return route_func, match.groupdict()

        return None, {}


def send_json(ctx: RequestContext, status: HTTPStatus, data: dict) -> None:
    ctx.handler.send_bytes(status, json_bytes(data), "application/json; charset=utf-8")


def handle_ping(ctx: RequestContext) -> None:
    send_json(ctx, HTTPStatus.OK, {"ok": True, "pong": True})


def handle_status(ctx: RequestContext) -> None:
    send_json(
        ctx,
        HTTPStatus.OK,
        {
            "ok": True,
            "root": str(ctx.root),
            "uptime_sec": round(time.time() - SERVER_STARTED, 3),
            "pid": os.getpid(),
        },
    )


def handle_upload(ctx: RequestContext) -> None:
    try:
        target = ctx.safe_path()
        data = ctx.read_body()
    except ValueError as e:
        status = HTTPStatus.LENGTH_REQUIRED if str(e) == "Content-Length is required" else HTTPStatus.BAD_REQUEST
        send_json(ctx, status, {"ok": False, "error": str(e)})
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    send_json(ctx, HTTPStatus.OK, {"ok": True, "path": str(target.relative_to(ctx.root)), "size": len(data)})


def handle_download(ctx: RequestContext) -> None:
    try:
        target = ctx.safe_path()
    except ValueError as e:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})
        return

    if not target.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "file not found"})
        return

    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    ctx.handler.send_bytes(
        HTTPStatus.OK,
        target.read_bytes(),
        content_type,
        {"Content-Disposition": f'attachment; filename="{target.name}"'},
    )


def handle_files(ctx: RequestContext) -> None:
    raw_path = ctx.query_one("path", ".")

    if raw_path in {"", "."}:
        target = ctx.root
    else:
        try:
            target = safe_join(ctx.root, raw_path)
        except ValueError as e:
            send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(e)})
            return

    if not target.exists():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "path not found"})
        return

    if target.is_file():
        stat = target.stat()
        send_json(
            ctx,
            HTTPStatus.OK,
            {
                "ok": True,
                "path": str(target.relative_to(ctx.root)),
                "type": "file",
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            },
        )
        return

    items = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = child.stat()
        items.append(
            {
                "name": child.name,
                "path": str(child.relative_to(ctx.root)),
                "type": "directory" if child.is_dir() else "file",
                "size": None if child.is_dir() else stat.st_size,
                "mtime": int(stat.st_mtime),
            }
        )

    send_json(ctx, HTTPStatus.OK, {"ok": True, "path": str(target.relative_to(ctx.root)), "type": "directory", "files": items})


def register_core_routes(router: Router) -> None:
    router.get("/ping", handle_ping)
    router.get("/status", handle_status)
    router.post("/upload", handle_upload)
    router.get("/download", handle_download)
    router.get("/files", handle_files)


class MenvHandler(BaseHTTPRequestHandler):
    server_version = "menv-http/1.0"

    @property
    def root(self) -> Path:
        return self.server.root  # type: ignore[attr-defined]

    @property
    def router(self) -> Router:
        return self.server.router  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str = "application/octet-stream",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)
        func, params = self.router.match(method, path)

        if func is None:
            self.send_bytes(HTTPStatus.NOT_FOUND, json_bytes({"ok": False, "error": "not found"}), "application/json; charset=utf-8")
            return

        ctx = RequestContext(self, self.root, method, path, query, params)
        func(ctx)

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")
