"""Versioned registry with content validation and a per-registry cache."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import Definition, fields, name, parse, string


DEFAULT_REGISTRY = "https://monerinngu0.github.io/.menv/"


def atomic_write(path: Path, raw: bytes) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Registry:
    def __init__(self, url: str, cache: Path, offline: bool = False):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("registry must be an HTTPS base URL without query or fragment")
        self.url = url.rstrip("/") + "/"
        self.cache = cache / "registries" / hashlib.sha256(self.url.encode()).hexdigest()
        self.offline = offline
        self._index = None

    def fetch(self, path: str) -> bytes:
        url = urllib.parse.urljoin(self.url, path)
        request = urllib.request.Request(url, headers={"User-Agent": "menv-setup"})
        with urllib.request.urlopen(request, timeout=15) as response:
            if not response.url.startswith(self.url):
                raise ValueError("registry redirected outside its base URL")
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("registry resource exceeds 2 MiB")
            return raw

    @staticmethod
    def validate_index(raw: bytes) -> dict:
        conf = fields(json.loads(raw), {"packages"}, "index")
        packages = conf.get("packages")
        if not isinstance(packages, dict):
            raise ValueError("index.packages must be a table")
        for key, entry in packages.items():
            name(key)
            entry = fields(entry, {"version", "path", "sha256", "description"}, key)
            if type(entry.get("version")) is not int or entry["version"] < 1:
                raise ValueError(f"invalid revision for {key}")
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
                raise ValueError(f"invalid SHA-256 for {key}")
            path = string(entry.get("path"), "package path")
            if not re.fullmatch(r"packages/[a-zA-Z0-9_./-]+\.toml", path) or any(
                p in (".", "..", "") for p in path.split("/")
            ):
                raise ValueError(f"invalid package path: {path}")
            if "description" in entry:
                string(entry["description"], "package description")
        return packages

    def index(self) -> dict:
        if self._index is not None:
            return self._index
        target = self.cache / "index.json"
        if self.offline:
            raw = target.read_bytes()
            print("setup: using offline registry cache", file=sys.stderr)
        else:
            try:
                raw = self.fetch("index.json")
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if not target.is_file():
                    raise ValueError(f"registry unavailable, no cached index: {error}") from error
                print(f"setup: registry unavailable; using cached definitions: {error}", file=sys.stderr)
                raw = target.read_bytes()
            # Validation errors never trigger fallback to an older definition.
        packages = self.validate_index(raw)
        if not self.offline:
            atomic_write(target, raw)
        self._index = packages
        return packages

    def load(self, key: str) -> Definition:
        entries = self.index()
        if key not in entries:
            raise ValueError(f"remote definition not found: {key}")
        entry = entries[key]
        target = self.cache / "packages" / f"{entry['sha256']}.toml"
        if target.is_file():
            raw = target.read_bytes()
        elif self.offline:
            raise ValueError(f"definition not cached: {key}")
        else:
            try:
                raw = self.fetch(entry["path"])
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ValueError(f"definition unavailable and not cached: {key}: {error}") from error
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {key}")
        definition = parse(raw, key)
        if definition.version != entry["version"]:
            raise ValueError(f"definition revision disagrees with index: {key}")
        atomic_write(target, raw)
        return definition
