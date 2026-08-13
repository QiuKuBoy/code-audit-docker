"""Project ingestion — import code from uploaded zip archives or remote git repos.

Solves the "local path must exist on the server" limitation: code is uploaded /
cloned into UPLOADS_DIR (persistent volume in Docker), so the web UI works the
same on Windows, macOS and Linux regardless of where the backend runs.
"""

import io
import os
import re
import shutil
import subprocess
import uuid
import zipfile

from app.core.config import settings


def _uploads_root() -> str:
    root = os.path.abspath(settings.UPLOADS_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def _flatten_single_root(target_dir: str) -> str:
    """If the archive/repo contains exactly one top-level directory (and no
    top-level files), use it as the project root."""
    entries = [e for e in os.listdir(target_dir) if e not in (".git",)]
    if len(entries) == 1:
        only = os.path.join(target_dir, entries[0])
        if os.path.isdir(only):
            return only
    return target_dir


def ingest_zip(data: bytes, original_filename: str = "") -> tuple[str, str]:
    """Extract an uploaded zip into UPLOADS_DIR.

    Returns (project_root_path, suggested_project_name).
    Raises ValueError on invalid / unsafe / oversized archives.
    """
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"Archive too large: {len(data) // 1024 // 1024}MB (max {settings.MAX_UPLOAD_MB}MB)")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("Invalid zip archive")

    dest = os.path.join(_uploads_root(), f"zip_{uuid.uuid4().hex[:12]}")
    os.makedirs(dest, exist_ok=True)

    try:
        dest_real = os.path.realpath(dest)
        for info in zf.infolist():
            # Zip-slip protection: resolved path must stay inside dest
            member_dest = os.path.realpath(os.path.join(dest, info.filename))
            if not (member_dest == dest_real or member_dest.startswith(dest_real + os.sep)):
                raise ValueError(f"Unsafe path in archive: {info.filename}")
            if info.is_dir():
                os.makedirs(member_dest, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(member_dest), exist_ok=True)
            with zf.open(info) as src, open(member_dest, "wb") as out:
                shutil.copyfileobj(src, out, length=1024 * 256)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    root = _flatten_single_root(dest)
    suggested = os.path.splitext(os.path.basename(original_filename or ""))[0].strip() or "uploaded-project"
    return root, suggested


_GIT_URL_RE = re.compile(
    r"^(https?://[^\s]+|git@[\w.\-]+:[^\s]+|ssh://[^\s]+)$", re.IGNORECASE
)


def ingest_git(url: str) -> tuple[str, str]:
    """Shallow-clone a remote git repository into UPLOADS_DIR.

    Returns (project_root_path, suggested_project_name).
    Raises ValueError on invalid URL or clone failure.
    """
    url = (url or "").strip()
    if not _GIT_URL_RE.match(url):
        raise ValueError(f"Invalid git URL: {url!r} (expect https://... or git@...)")

    if not shutil.which("git"):
        raise ValueError("git is not installed on the server (rebuild the Docker image with git)")

    dest = os.path.join(_uploads_root(), f"git_{uuid.uuid4().hex[:12]}")
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", url, dest],
            capture_output=True, text=True, timeout=settings.GIT_CLONE_TIMEOUT,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()
            raise ValueError(f"git clone failed: {err[:300]}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        raise ValueError(f"git clone timed out after {settings.GIT_CLONE_TIMEOUT}s")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    root = _flatten_single_root(dest)
    base = url.rstrip("/")
    if base.lower().endswith(".git"):
        base = base[:-4]
    base = base.split("/")[-1].split(":")[-1]
    suggested = base or "cloned-repo"
    return root, suggested
