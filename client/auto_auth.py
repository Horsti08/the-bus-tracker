"""Automatisches Konto – öffnen und loslegen, ohne Registrierungsformular."""

from __future__ import annotations

import secrets
import uuid

from client.api_client import ApiClient
from client.config import load_config, save_config


def _device_id(cfg: dict) -> str:
    did = cfg.get("device_id")
    if not did:
        did = str(uuid.uuid4())
        cfg["device_id"] = did
        save_config(cfg)
    return did


def ensure_authenticated(api: ApiClient) -> bool:
    """Stellt sicher, dass ein Token existiert (gespeichert oder Auto-Konto)."""
    cfg = load_config()
    if cfg.get("access_token") and cfg.get("username"):
        api.token = cfg["access_token"]
        api.user_id = cfg.get("user_id")
        api.username = cfg["username"]
        api.display_name = cfg.get("display_name", api.username)
        if api.health():
            return True

    device_id = _device_id(cfg)
    username = f"driver_{device_id[:8]}"
    password = cfg.get("device_password")
    if not password:
        password = secrets.token_urlsafe(16)
        cfg["device_password"] = password

    try:
        data = api.register(username, password, display_name=f"Fahrer {username[-4:]}")
    except Exception:
        try:
            data = api.login(username, password)
        except Exception:
            return False

    cfg["access_token"] = data["access_token"]
    cfg["user_id"] = data["user_id"]
    cfg["username"] = data["username"]
    cfg["display_name"] = data["display_name"]
    save_config(cfg)
    return True
