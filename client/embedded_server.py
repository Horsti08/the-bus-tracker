"""Eingebetteter API-Server – startet automatisch mit der EXE."""

from __future__ import annotations

import socket
import threading

from shared import API_PORT

_server_thread: threading.Thread | None = None
_started = False


def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def start_embedded_server() -> str:
    """Startet API + Discovery-Beacon. Gibt die LAN-URL zurück."""
    global _server_thread, _started
    if _started:
        return f"http://{_get_lan_ip()}:{API_PORT}"

    def run_api():
        import uvicorn

        uvicorn.run(
            "server.main:app",
            host="0.0.0.0",
            port=API_PORT,
            log_level="error",
            access_log=False,
        )

    def run_beacon():
        from server.discovery_beacon import run_beacon_loop

        run_beacon_loop(_get_lan_ip())

    _server_thread = threading.Thread(target=run_api, daemon=True)
    _server_thread.start()
    threading.Thread(target=run_beacon, daemon=True).start()
    _started = True
    return f"http://{_get_lan_ip()}:{API_PORT}"
