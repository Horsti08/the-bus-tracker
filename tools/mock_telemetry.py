"""Mock-Telemetrie-Server zum Testen ohne The Bus (Port 37337)."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SAMPLE = Path(__file__).resolve().parent.parent / "tools" / "sample_vehicle.json"


def load_sample() -> dict:
    if SAMPLE.exists():
        return json.loads(SAMPLE.read_text(encoding="utf-8"))
    return {
        "ActorName": "BP_MAN_LionsCoach_C_0",
        "VehicleModel": "Lions City (Demo)",
        "Speed": 32.5,
        "AllowedSpeed": 50.0,
        "EngineStarted": "true",
        "IgnitionEnabled": "true",
        "IsAtStop": "false",
        "NumOccupiedSeats": 12,
        "NumSeats": 83,
        "Location": {"X": 165000, "Y": 76800, "Z": 4700},
        "BusLogic": {"Sales": {"TotalRevenue": 45.5, "TicketCount": 8}},
        "Buttons": [],
        "UMG": {},
    }


class Handler(BaseHTTPRequestHandler):
    sample = load_sample()
    tick = 0

    def log_message(self, *_):
        pass

    def do_GET(self):
        path = self.path.lower().rstrip("/")
        Handler.tick += 1
        data = None
        if path in ("/vehicles", "/vehicles/current"):
            s = dict(Handler.sample)
            s["Speed"] = 20 + (Handler.tick % 30)
            s["BusLogic"] = {
                "Sales": {
                    "TotalRevenue": 10.0 + Handler.tick * 0.5,
                    "TicketCount": Handler.tick // 5,
                }
            }
            data = s
        elif path == "/world":
            data = {
                "LevelName": "Berlin (Mock)",
                "DateTime": "2026-05-25T12:00:00",
                "TimeFactor": 1.0,
            }
        elif path == "/player":
            data = {"Mode": "Vehicle", "CurrentVehicle": Handler.sample["ActorName"]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main():
    port = 37337
    print(f"Mock-Telemetrie auf http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
