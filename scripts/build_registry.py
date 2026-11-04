#!/usr/bin/env python3
"""Generate deterministic registry metadata, or check it in CI with --check."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "envs/setup/.lib"))
from config import parse

packages = {}
for path in sorted((ROOT / "registry/packages").rglob("*.toml")):
    key = path.relative_to(ROOT / "registry/packages").with_suffix("").as_posix()
    raw = path.read_bytes()
    definition = parse(raw, key)
    packages[key] = {"version": definition.version,
                     "path": path.relative_to(ROOT / "registry").as_posix(),
                     "sha256": hashlib.sha256(raw).hexdigest(),
                     "description": definition.description}
raw = json.dumps({"packages": packages}, ensure_ascii=False, indent=2) + "\n"
target = ROOT / "registry/index.json"
if "--check" in sys.argv:
    if not target.is_file() or target.read_text() != raw:
        raise SystemExit("registry/index.json is stale: run python3 scripts/build_registry.py")
else:
    target.write_text(raw)
