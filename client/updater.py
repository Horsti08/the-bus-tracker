"""Auto-Updater – prüft beim Start auf neue Version."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from shared import APP_VERSION, UPDATE_MANIFEST_URL


def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for p in v.strip().lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def check_for_update() -> dict | None:
    try:
        r = httpx.get(UPDATE_MANIFEST_URL, timeout=8.0)
        if r.status_code != 200:
            return None
        data = r.json()
        remote = data.get("version", "")
        if _parse_version(remote) > _parse_version(APP_VERSION):
            return data
    except httpx.HTTPError:
        pass
    return None


def _write_updater_script(new_exe: Path, target: Path) -> Path:
    script = Path(tempfile.gettempdir()) / "but_update.bat"
    script.write_text(
        f"""@echo off
timeout /t 2 /nobreak >nul
copy /Y "{new_exe}" "{target}"
start "" "{target}"
del "{new_exe}"
del "%~f0"
""",
        encoding="utf-8",
    )
    return script


def download_and_apply(update: dict, parent_window=None) -> bool:
    url = (update.get("download_url") or "").strip()
    if not url:
        return False

    if getattr(sys, "frozen", False):
        target = Path(sys.executable)
    else:
        return False

    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
            resp.raise_for_status()
            tmp = Path(tempfile.gettempdir()) / "TheBusTracker_new.exe"
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(65536):
                    f.write(chunk)
    except httpx.HTTPError:
        return False

    script = _write_updater_script(tmp, target)
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=subprocess.CREATE_NO_WINDOW)
    if parent_window:
        try:
            parent_window.destroy()
        except Exception:
            pass
    sys.exit(0)


def prompt_update_if_available(root=None) -> dict | None:
    return check_for_update()
