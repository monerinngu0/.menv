from __future__ import annotations

import json
import mimetypes
import shutil
import subprocess
import time
import uuid
import zipfile
from http import HTTPStatus
from pathlib import Path

from core import RequestContext, Router, send_json


SONG_BIN = Path.home() / ".menv" / "envs" / "song" / ".bin"
WEB_DIR = Path.home() / ".menv" / "envs" / "song" / ".lib" / "server" / "web"


def safe_name(value: str) -> bool:
    return bool(value) and not value.startswith(".") and "/" not in value


def read_json(ctx: RequestContext) -> dict | None:
    try:
        body = ctx.read_body()
        return json.loads(body.decode("utf-8"))
    except Exception as e:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid json: {e}"})
        return None


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def category_info(root: Path, path: Path) -> dict | None:
    song_dir = path / "song"
    config_dir = path / ".config"
    song_json = config_dir / "song.json"

    if not song_dir.is_dir() or not song_json.is_file():
        return None

    count = 0
    try:
        data = json.loads(song_json.read_text(encoding="utf-8"))
        count = int(data.get("count", 0))
    except Exception:
        pass

    return {
        "name": path.name,
        "path": str(path.relative_to(root)),
        "count": count,
    }


def song_files(root: Path, category: str) -> list[str]:
    cat_dir = root / category
    song_json = cat_dir / ".config" / "song.json"
    song_dir = cat_dir / "song"

    if not song_dir.is_dir():
        return []

    try:
        data = json.loads(song_json.read_text(encoding="utf-8"))
        files = [song["file"] for song in data.get("songs", []) if isinstance(song.get("file"), str)]
        return sorted(files)
    except Exception:
        return sorted(path.relative_to(song_dir).as_posix() for path in song_dir.rglob("*") if path.is_file())


def song_entries(root: Path, category: str) -> list[dict]:
    song_json = root / category / ".config" / "song.json"

    try:
        data = json.loads(song_json.read_text(encoding="utf-8"))
        return [song for song in data.get("songs", []) if isinstance(song, dict)]
    except Exception:
        return []


def validate_song_file(root: Path, category: str, file_name: str) -> Path:
    if not file_name or "\\" in file_name or ":" in file_name:
        raise ValueError(f"invalid file path: {file_name}")

    rel = Path(file_name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe file path: {file_name}")

    song_dir = (root / category / "song").resolve()
    target = (song_dir / rel).resolve()

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
    return subprocess.run(args, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


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

    if not filename or filename.startswith(".") or "/" in filename:
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid filename"})
        return

    send_web_file(ctx, WEB_DIR / filename)


def handle_library(ctx: RequestContext) -> None:
    category = ctx.query_one("category")

    if category:
        if not safe_name(category):
            send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid category"})
            return
        send_json(ctx, HTTPStatus.OK, {"ok": True, "category": category, "files": song_files(ctx.root, category)})
        return

    categories = []
    for child in sorted(ctx.root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir() and not child.name.startswith(".") and (child / "song").is_dir():
            categories.append({"category": child.name, "files": song_files(ctx.root, child.name)})

    send_json(ctx, HTTPStatus.OK, {"ok": True, "categories": categories})


def handle_create_job(ctx: RequestContext) -> None:
    req = read_json(ctx)
    if req is None:
        return

    job_type = req.get("type")
    if not isinstance(job_type, str):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "job type is required"})
        return

    job_id, path, job = new_job(ctx.root, job_type)

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

    if not isinstance(url, str) or not url:
        return fail_job(path, job, "url is required")
    if not isinstance(category, str) or not safe_name(category):
        return fail_job(path, job, "invalid category")

    args = [str(SONG_BIN / "sadd"), "-c", category]
    if playlist:
        args.append("--playlist")
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

    return finish_job(path, job, [{"name": output_name, "url": f"/api/files/{job['id']}/{output_name}"}])


def run_song_pack_diff(root: Path, path: Path, job: dict, req: dict) -> dict:
    category = req.get("category")
    client_files = req.get("client_files")

    if not isinstance(category, str) or not safe_name(category):
        return fail_job(path, job, "invalid category")
    if not isinstance(client_files, list):
        return fail_job(path, job, "client_files is required")

    server_by_file = {
        song.get("file"): song
        for song in song_entries(root, category)
        if isinstance(song.get("file"), str)
    }
    songs = []

    for file_name in client_files:
        if not isinstance(file_name, str):
            continue

        server_song = server_by_file.get(file_name)
        if server_song is not None:
            songs.append(server_song)
        else:
            songs.append({"id": file_name, "file": file_name, "size": 0, "mtime": 0})

    receive = {
        "version": 1,
        "category": category,
        "count": len(songs),
        "songs": songs,
    }
    receive_path = path / "receive.json"
    output = path / f"{category}_diff.zip"
    write_json(receive_path, receive)

    args = [str(SONG_BIN / "spack"), str(receive_path), "-o", str(output)]
    result = run_command(root, args)
    job["log"] = result.stdout

    if result.returncode != 0:
        return fail_job(path, job, "spack failed")

    return finish_job(path, job, [{"name": output.name, "url": f"/api/files/{job['id']}/{output.name}"}])


def run_song_pack_select(root: Path, path: Path, job: dict, req: dict) -> dict:
    category = req.get("category")
    files = req.get("files")

    if not isinstance(category, str) or not safe_name(category):
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
            arcname = target.relative_to((root / category / "song").resolve()).as_posix()
            entries.append((target, arcname))
    except ValueError as e:
        return fail_job(path, job, str(e))

    if not entries:
        return fail_job(path, job, "no files selected")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as zf:
        for target, arcname in entries:
            zf.write(target, arcname)

    return finish_job(path, job, [{"name": output_name, "url": f"/api/files/{job['id']}/{output_name}"}])


def handle_get_job(ctx: RequestContext) -> None:
    job_id = ctx.params.get("job_id", "")
    path = job_root(ctx.root) / job_id / "job.json"

    if not path.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "job not found"})
        return

    send_json(ctx, HTTPStatus.OK, json.loads(path.read_text(encoding="utf-8")))


def handle_get_file(ctx: RequestContext) -> None:
    job_id = ctx.params.get("job_id", "")
    filename = ctx.params.get("filename", "")

    if "/" in filename or filename.startswith("."):
        send_json(ctx, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid filename"})
        return

    path = job_root(ctx.root) / job_id / filename
    if not path.is_file():
        send_json(ctx, HTTPStatus.NOT_FOUND, {"ok": False, "error": "file not found"})
        return

    ctx.handler.send_bytes(HTTPStatus.OK, path.read_bytes(), "application/zip")


def register(router: Router) -> None:
    router.get("/song/", handle_song_index)
    router.get("/song/static/<filename>", handle_song_static)
    router.get("/song/categories", handle_categories)
    router.get("/api/library", handle_library)
    router.post("/api/jobs", handle_create_job)
    router.get("/api/jobs/<job_id>", handle_get_job)
    router.get("/api/files/<job_id>/<filename>", handle_get_file)
