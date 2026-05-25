"""Start: Community-API (Internet) → Auto-Login wie SPEDV."""

from __future__ import annotations

from client.api_client import ApiClient
from client.auto_auth import ensure_authenticated
from client.config import load_config, save_config
from client.server_connect import ServerInfo, connect_community_server, connect_offline_server


def initialize_client(offline_mode: bool = False) -> tuple[ApiClient, ServerInfo, bool]:
    cfg = load_config()
    offline_mode = offline_mode or cfg.get("offline_mode", False)

    if offline_mode:
        server = connect_offline_server()
    else:
        server = connect_community_server()

    cfg["server_url"] = server.url
    cfg["server_label"] = server.label
    cfg["offline_mode"] = offline_mode
    save_config(cfg)

    api = ApiClient(server.url)
    auth_ok = ensure_authenticated(api)
    return api, server, auth_ok
