"""UDP-Beacon: andere Clients finden den API-Server im LAN ohne IP-Eingabe."""

from __future__ import annotations

import json
import socket
import time

from shared import API_PORT, DISCOVERY_PORT

BEACON_INTERVAL = 3


def run_beacon_loop(lan_ip: str, server_label: str = "LAN"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = json.dumps(
        {
            "type": "but_api",
            "url": f"http://{lan_ip}:{API_PORT}",
            "name": server_label,
            "host": socket.gethostname(),
        }
    ).encode("utf-8")

    while True:
        try:
            sock.sendto(message, ("<broadcast>", DISCOVERY_PORT))
            sock.sendto(message, ("255.255.255.255", DISCOVERY_PORT))
        except OSError:
            pass
        time.sleep(BEACON_INTERVAL)
