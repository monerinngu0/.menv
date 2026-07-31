from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from http import HTTPStatus
from pathlib import Path


MENV_ROOT = Path(os.environ.get("MENV_ROOT", Path.home() / ".menv"))
SONG_ROOT = MENV_ROOT / "envs" / "song"
SONG_BIN = SONG_ROOT / ".bin"
WEB_DIR = SONG_ROOT / ".lib" / "server" / "web"

sys.path.insert(0, str(MENV_ROOT / ".lib"))
sys.path.insert(0, str(SONG_ROOT / ".lib"))

from core import RequestContext, Router, safe_join, send_json  # noqa: E402
from song import read_json, write_json, song_id_from_rel  # noqa: E402


def safe_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith(".")
        and "/" not in value
        and "\\" not in value
    )


def normalize_song_file(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"invalid file path: {value}")

    rel = Path(value.replace("\\", "/"))

    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe file path: {value}")

    if rel.parts and rel.parts[0] == "song":
        return rel.as_posix()

    return (Path("song") / rel).as_posix()


def read_request_json(ctx: RequestContext) -> dict | None:
    try:
        body = ctx.read_body()
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid json: {e}"})
        return None

    if not isinstance(data, dict):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "json root must be object"})
        return None

    return data


def category_info(root: Path, path: Path) -> dict | None:
    song_dir = path / "song"
    song_json = path / ".config" / "song.json"

    if not song_dir.is_dir() or not song_json.is_file():
        return None

    data = read_json(song_json, {})
    count = data.get("count", 0)

    if not isinstance(count, int):
        count = 0

    return {
        "name": path.name,
        "path": str(path.relative_to(root)),
        "count": count,
    }


def refresh_category(root: Path, category: str) -> None:
    if not safe_name(category):
        return

    if not (root / category / "song").is_dir():
        return

    subprocess.run(
        [str(SONG_BIN / "slist"), category],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def song_entries(root: Path, category: str) -> list[dict]:
    refresh_category(root, category)

    song_json = root / category / ".config" / "song.json"
    data = read_json(song_json, {})
    songs = data.get("songs", [])

    if not isinstance(songs, list):
        return []

    return [song for song in songs if isinstance(song, dict)]


def song_files(root: Path, category: str) -> list[str]:
    entries = song_entries(root, category)
    files = []

    for song in entries:
        file_value = song.get("file")

        if isinstance(file_value, str):
            try:
                files.append(normalize_song_file(file_value))
            except ValueError:
                pass

    return sorted(files)


def validate_song_file(root: Path, category: str, file_name: str) -> Path:
    if not safe_name(category):
        raise ValueError("invalid category")

    normalized = normalize_song_file(file_name)
    rel = Path(normalized)

    song_dir = (root / category / "song").resolve()
    target = (root / category / rel).resolve()

    try:
        target.relative_to(song_dir)
    except ValueError:
        raise ValueError(f"file is outside category: {file_name}")

    if not target.is_file():
        raise ValueError(f"file not found: {file_name}")

    return target


def job_root(root: Path) -> Path:
    path = root / ".temp" / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_job(root: Path, job_type: str) -> tuple[str, Path, dict]:
    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    path = job_root(root) / job_id
    path.mkdir(parents=True, exist_ok=True)

    job = {
        "id": job_id,
        "type": job_type,
        "status": "running",
        "outputs": [],
        "created": int(time.time()),
    }

    write_json(path / "job.json", job)
    return job_id, path, job


def finish_job(path: Path, job: dict, outputs: list[dict]) -> dict:
    job["status"] = "finished"
    job["outputs"] = outputs
    job["finished"] = int(time.time())

    write_json(path / "job.json", job)
    return job


def fail_job(path: Path, job: dict, message: str) -> dict:
    job["status"] = "failed"
    job["error"] = message
    job["finished"] = int(time.time())

    write_json(path / "job.json", job)
    return job


def run_command(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def handle_categories(ctx: RequestContext) -> None:
    categories = []

    for child in sorted(ctx.root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("."):
            continue

        item = category_info(ctx.root, child)

        if item is not None:
            categories.append(item)

    send_json(ctx, HTTPStatus.OK, {"ok": True, "categories": categories})


def send_web_file(ctx: RequestContext, path: Path) -> None:
    if not path.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "file not found"})
        return

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    if path.suffix == ".html":
        content_type = "text/html; charset=utf-8"
    elif path.suffix == ".js":
        content_type = "text/javascript; charset=utf-8"
    elif path.suffix == ".css":
        content_type = "text/css; charset=utf-8"

    ctx.handler.send_bytes(HTTPStatus.OK, path.read_bytes(), content_type)


def handle_song_index(ctx: RequestContext) -> None:
    send_web_file(ctx, WEB_DIR / "index.html")


def handle_song_static(ctx: RequestContext) -> None:
    filename = ctx.params.get("filename", "")

    if not filename or filename.startswith(".") or "/" in filename or "\\" in filename:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid filename"})
        return

    send_web_file(ctx, WEB_DIR / filename)


def handle_library(ctx: RequestContext) -> None:
    category = ctx.query_one("category")

    if category:
        if not safe_name(category):
            send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid category"})
            return

        send_json(
            ctx,
            HTTPStatus.OK,
            {
                "ok": True,
                "category": category,
                "files": song_files(ctx.root, category),
                "songs": song_entries(ctx.root, category),
            },
        )
        return

    categories = []

    for child in sorted(ctx.root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and not child.name.startswith(".") and (child / "song").is_dir():
            categories.append(
                {
                    "category": child.name,
                    "files": song_files(ctx.root, child.name),
                    "songs": song_entries(ctx.root, child.name),
                }
            )

    send_json(ctx, HTTPStatus.OK, {"ok": True, "categories": categories})


def handle_create_job(ctx: RequestContext) -> None:
    req = read_request_json(ctx)

    if req is None:
        return

    job_type = req.get("type")

    if not isinstance(job_type, str):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "job type is required"})
        return

    _, path, job = new_job(ctx.root, job_type)

    try:
        if job_type == "song_add":
            job = run_song_add(ctx.root, path, job, req)
        elif job_type == "song_pack_all":
            job = run_song_pack_all(ctx.root, path, job, req)
        elif job_type == "song_pack_diff":
            job = run_song_pack_diff(ctx.root, path, job, req)
        elif job_type == "song_pack_select":
            job = run_song_pack_select(ctx.root, path, job, req)
        else:
            job = fail_job(path, job, f"unknown job type: {job_type}")
    except Exception as e:
        job = fail_job(path, job, str(e))

    status = HTTPStatus.OK if job.get("status") == "finished" else HTTPStatus.BAD_REQUEST
    send_json(ctx, status, job)


def run_song_add(root: Path, path: Path, job: dict, req: dict) -> dict:
    url = req.get("url")
    category = req.get("category")
    playlist = bool(req.get("playlist", False))
    force = bool(req.get("force", False))

    if not isinstance(url, str) or not url:
        return fail_job(path, job, "url is required")

    if not safe_name(category):
        return fail_job(path, job, "invalid category")

    args = [str(SONG_BIN / "sadd"), "-c", category]

    if playlist:
        args.append("--playlist")

    if force:
        args.append("--force")

    args.append(url)

    result = run_command(root, args)
    job["log"] = result.stdout

    if result.returncode != 0:
        return fail_job(path, job, "sadd failed")

    return finish_job(path, job, [])


def run_song_pack_all(root: Path, path: Path, job: dict, req: dict) -> dict:
    category = req.get("category")

    args = [str(SONG_BIN / "spack"), "--all-music-no-json"]
    output_name = "all.zip"

    if isinstance(category, str) and category:
        if not safe_name(category):
            return fail_job(path, job, "invalid category")

        args += ["-c", category]
        output_name = f"{category}_all.zip"
    else:
        args.append("-a")

    output = path / output_name
    args += ["-o", str(output)]

    result = run_command(root, args)
    job["log"] = result.stdout

    if result.returncode != 0:
        return fail_job(path, job, "spack failed")

    return finish_job(
        path,
        job,
        [{"name": output_name, "url": f"/api/files/{job['id']}/{output_name}"}],
    )


def snapshot_from_client_files(root: Path, category: str, client_files: list) -> dict:
    server_by_file = {
        normalize_song_file(song.get("file")): song
        for song in song_entries(root, category)
        if isinstance(song.get("file"), str)
    }

    songs = []

    for file_name in client_files:
        if not isinstance(file_name, str):
            continue

        try:
            normalized = normalize_song_file(file_name)
        except ValueError:
            continue

        server_song = server_by_file.get(normalized)

        if server_song is not None:
            songs.append(server_song)
        else:
            rel = Path(normalized)
            songs.append(
                {
                    "id": song_id_from_rel(rel),
                    "file": normalized,
                    "size": 0,
                    "mtime": 0,
                }
            )

    return {
        "version": 1,
        "category": category,
        "count": len(songs),
        "songs": songs,
    }


def run_song_pack_diff(root: Path, path: Path, job: dict, req: dict) -> dict:
    snapshot = req.get("snapshot")
    snapshot_path_raw = req.get("snapshot_path")
    category = req.get("category")
    client_files = req.get("client_files")

    receive_path = path / "receive.json"

    if isinstance(snapshot, dict):
        write_json(receive_path, snapshot)
        category_value = snapshot.get("category")
        output_category = category_value if isinstance(category_value, str) else "diff"
    elif isinstance(snapshot_path_raw, str) and snapshot_path_raw:
        try:
            snapshot_path = safe_join(root, snapshot_path_raw)
        except ValueError as e:
            return fail_job(path, job, str(e))

        if not snapshot_path.is_file():
            return fail_job(path, job, "snapshot file not found")

        shutil.copy2(snapshot_path, receive_path)

        data = read_json(receive_path, {})
        category_value = data.get("category")
        output_category = category_value if isinstance(category_value, str) else "diff"
    elif safe_name(category) and isinstance(client_files, list):
        snapshot = snapshot_from_client_files(root, category, client_files)
        write_json(receive_path, snapshot)
        output_category = category
    else:
        return fail_job(path, job, "snapshot, snapshot_path, or category + client_files is required")

    output_name = f"{output_category}_diff.zip"
    output = path / output_name

    args = [str(SONG_BIN / "spack"), str(receive_path), "-o", str(output)]

    result = run_command(root, args)
    job["log"] = result.stdout

    if result.returncode != 0:
        return fail_job(path, job, "spack failed")

    return finish_job(
        path,
        job,
        [{"name": output_name, "url": f"/api/files/{job['id']}/{output_name}"}],
    )


def run_song_pack_select(root: Path, path: Path, job: dict, req: dict) -> dict:
    category = req.get("category")
    files = req.get("files")

    if not safe_name(category):
        return fail_job(path, job, "invalid category")

    if not isinstance(files, list):
        return fail_job(path, job, "files is required")

    output_name = f"{category}_select.zip"
    output = path / output_name

    entries = []

    try:
        for file_name in files:
            if not isinstance(file_name, str):
                raise ValueError("files must be strings")

            target = validate_song_file(root, category, file_name)

            song_dir = (root / category / "song").resolve()
            arcname = target.relative_to(song_dir).as_posix()

            entries.append((target, arcname))
    except ValueError as e:
        return fail_job(path, job, str(e))

    if not entries:
        return fail_job(path, job, "no files selected")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
        for target, arcname in entries:
            zf.write(target, arcname)

    return finish_job(
        path,
        job,
        [{"name": output_name, "url": f"/api/files/{job['id']}/{output_name}"}],
    )


def handle_get_job(ctx: RequestContext) -> None:
    job_id = ctx.params.get("job_id", "")

    if not job_id or "/" in job_id or job_id.startswith("."):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid job id"})
        return

    path = job_root(ctx.root) / job_id / "job.json"

    if not path.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "job not found"})
        return

    send_json(ctx, HTTPStatus.OK, read_json(path, {}))


def handle_get_file(ctx: RequestContext) -> None:
    job_id = ctx.params.get("job_id", "")
    filename = ctx.params.get("filename", "")

    if not job_id or "/" in job_id or job_id.startswith("."):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid job id"})
        return

    if not filename or "/" in filename or filename.startswith(".") or "\\" in filename:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid filename"})
        return

    path = job_root(ctx.root) / job_id / filename

    if not path.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "file not found"})
        return

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    ctx.handler.send_bytes(
        HTTPStatus.OK,
        path.read_bytes(),
        content_type,
        {"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


def register(router: Router) -> None:
    router.get("/song/", handle_song_index)
    router.get("/song/static/<filename>", handle_song_static)
    router.get("/song/categories", handle_categories)

    router.get("/api/library", handle_library)
    router.post("/api/jobs", handle_create_job)
    router.get("/api/jobs/<job_id>", handle_get_job)
    router.get("/api/files/<job_id>/<filename>", handle_get_file)
