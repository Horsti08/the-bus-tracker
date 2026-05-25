"""Findet API-Server im Netzwerk per UDP (ohne IP-Eingabe)."""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass

from shared import DISCOVERY_PORT


@dataclass
class DiscoveredServer:
    url: str
    name: str
    host: str


class ServerDiscovery:
    def __init__(self, listen_seconds: float = 2.5):
        self.listen_seconds = listen_seconds
        self.found: dict[str, DiscoveredServer] = {}
        self._stop = threading.Event()

    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                data, _ = sock.recvfrom(4096)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("type") == "but_api" and msg.get("url"):
                    url = msg["url"].rstrip("/")
                    self.found[url] = DiscoveredServer(
                        url=url,
                        name=msg.get("name", "LAN"),
                        host=msg.get("host", "?"),
                    )
            except (socket.timeout, json.JSONDecodeError, OSError):
                continue
        sock.close()

    def scan(self) -> list[DiscoveredServer]:
        self.found.clear()
        self._stop.clear()
        t = threading.Thread(target=self._listen, daemon=True)
        t.start()
        self._stop.wait(self.listen_seconds)
        self._stop.set()
        t.join(timeout=1)
        return list(self.found.values())
