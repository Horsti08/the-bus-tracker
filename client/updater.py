"""Auto-Updater – Community-Server + GitHub-Manifest."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

from shared import APP_VERSION, COMMUNITY_API_ENDPOINTS, UPDATE_MANIFEST_URL


def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for p in str(v).strip().lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def check_for_update(community_url: str | None = None) -> dict | None:
    sources: list[str] = []
    if community_url:
        sources.append(community_url.rstrip("/"))
    for u in COMMUNITY_API_ENDPOINTS:
        if u not in sources:
            sources.append(u.rstrip("/"))

    for base in sources:
        try:
            r = httpx.get(f"{base}/app/version", timeout=6.0)
            if r.status_code == 200:
                data = r.json()
                remote = data.get("version", "")
                if remote and _parse_version(remote) > _parse_version(APP_VERSION):
                    data.setdefault("download_url", data.get("download_url", ""))
                    return data
        except httpx.HTTPError:
            continue

    try:
        r = httpx.get(UPDATE_MANIFEST_URL, timeout=8.0)
        if r.status_code == 200:
            data = r.json()
            remote = data.get("version", "")
            if _parse_version(remote) > _parse_version(APP_VERSION):
                return data
    except httpx.HTTPError:
        pass
    return None


def download_and_apply(update: dict, parent_window=None) -> bool:
    url = (update.get("download_url") or "").strip()
    if not url:
        return False

    if not getattr(sys, "frozen", False):
        return False

    target = Path(sys.executable)
    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
            resp.raise_for_status()
            tmp = Path(tempfile.gettempdir()) / "TheBusTracker_new.exe"
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(65536):
                    f.write(chunk)
    except httpx.HTTPError:
        return False

    script = Path(tempfile.gettempdir()) / "but_update.bat"
    script.write_text(
        f"""@echo off
timeout /t 2 /nobreak >nul
copy /Y "{tmp}" "{target}"
start "" "{target}"
del "{tmp}"
del "%~f0"
""",
        encoding="utf-8",
    )
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=subprocess.CREATE_NO_WINDOW)
    if parent_window:
        try:
            parent_window.destroy()
        except Exception:
            pass
    sys.exit(0)
