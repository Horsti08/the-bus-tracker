"""SPEDV-Modell: Immer zentraler Internet-API-Server – kein WLAN nötig."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from shared import (
    COMMUNITY_API_ENDPOINTS,
    COMMUNITY_CONNECT_TIMEOUT,
    COMMUNITY_RETRY_COUNT,
    COMMUNITY_SERVER_NAME,
    LOCAL_API_URL,
    PUBLIC_API_URLS,
    UPDATE_MANIFEST_URL,
)


@dataclass
class ServerInfo:
    url: str
    label: str
    kind: str  # community | offline
    online: bool = True
    players_online: int = 0
    server_version: str = ""


class CommunityServerUnavailable(Exception):
    """Kein Community-Server erreichbar (wie SPEDV ohne Internet)."""


def _health_and_info(url: str, timeout: float = COMMUNITY_CONNECT_TIMEOUT) -> dict | None:
    base = url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            h = client.get(f"{base}/health")
            if h.status_code != 200:
                return None
            info = {}
            try:
                r = client.get(f"{base}/app/info")
                if r.status_code == 200:
                    info = r.json()
            except httpx.HTTPError:
                pass
            return {
                "url": base,
                "version": h.json().get("version", info.get("version", "")),
                "players_online": info.get("players_online", 0),
                "server_name": info.get("server_name", COMMUNITY_SERVER_NAME),
            }
    except httpx.HTTPError:
        return None


def _try_url(url: str) -> dict | None:
    for _ in range(COMMUNITY_RETRY_COUNT):
        data = _health_and_info(url)
        if data:
            return data
        time.sleep(0.4)
    return None


def _collect_candidate_urls() -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []

    def add(u: str):
        u = (u or "").strip().rstrip("/")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)

    # Gespeicherte Community-URL (letzter erfolgreicher Login)
    try:
        from client.config import load_config

        cached = load_config().get("community_api_url")
        add(cached)
    except Exception:
        pass

    for u in COMMUNITY_API_ENDPOINTS:
        add(u)
    for u in PUBLIC_API_URLS:
        add(u)

    # Manifest (GitHub / CDN)
    try:
        r = httpx.get(UPDATE_MANIFEST_URL, timeout=6.0)
        if r.status_code == 200:
            data = r.json() or {}
            add(data.get("community_api_url", ""))
            for u in data.get("community_api_urls", []) or []:
                add(u)
    except httpx.HTTPError:
        pass

    for u in list(urls):
        try:
            r = httpx.get(f"{u}/app/version", timeout=4.0)
            if r.status_code == 200:
                add(r.json().get("community_api_url", ""))
        except httpx.HTTPError:
            pass

    return urls


def connect_community_server() -> ServerInfo:
    """
    Verbindet mit dem zentralen SPEDV-ähnlichen Community-Server.
    Wirft CommunityServerUnavailable wenn keiner erreichbar ist.
    """
    candidates = _collect_candidate_urls()
    if not candidates:
        raise CommunityServerUnavailable(
            "Kein Community-Server konfiguriert. Siehe deploy/community/README.md"
        )

    for url in candidates:
        data = _try_url(url)
        if data:
            from client.config import load_config, save_config

            cfg = load_config()
            cfg["community_api_url"] = data["url"]
            save_config(cfg)
            return ServerInfo(
                url=data["url"],
                label=f"{data.get('server_name', COMMUNITY_SERVER_NAME)} (Online)",
                kind="community",
                players_online=int(data.get("players_online", 0)),
                server_version=data.get("version", ""),
            )

    raise CommunityServerUnavailable(
        "Community-Server nicht erreichbar.\n"
        "Prüfe deine Internetverbindung oder starte den Community-Server neu.\n"
        f"Getestet: {len(candidates)} Adresse(n)"
    )


def connect_offline_server() -> ServerInfo:
    """Nur Solo – lokale Daten, keine Spedition mit Freunden übers Internet."""
    from client.embedded_server import start_embedded_server

    start_embedded_server()
    for _ in range(20):
        if _health_and_info(LOCAL_API_URL, timeout=1.0):
            break
        time.sleep(0.15)

    return ServerInfo(
        url=LOCAL_API_URL,
        label="Offline (nur dieser PC – kein Multiplayer)",
        kind="offline",
        online=True,
    )


def resolve_best_server(offline_mode: bool = False) -> ServerInfo:
    if offline_mode:
        return connect_offline_server()
    return connect_community_server()
