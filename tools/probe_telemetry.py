"""Zeigt alle Telemetrie-Felder – zum Finden von Linie/Haltestelle (The Bus muss laufen)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.telemetry.client import TelemetryClient
from client.telemetry.route_info import collect_umg_paths, extract_from_buttons, extract_from_json


def main():
    c = TelemetryClient()
    if not c.is_connected():
        print("Keine Verbindung zu Port 37337. The Bus starten + Telemetrie aktivieren.")
        return 1

    snap = c.fetch_snapshot()
    vehicle = c._get_json("vehicles/Current") or {}

    print("=== Fahrzeug (Auszug) ===")
    print(f"Modell: {snap.vehicle_model}")
    print(f"Karte:  {snap.level_name}")
    print(f"Linie:  {snap.line_name or '(leer)'}")
    print(f"Route:  {snap.route_name or '(leer)'}")
    print(f"Aktuell:{snap.current_stop or '(leer)'}")
    print(f"Nächste:{snap.next_stop or '(leer)'}")
    print(f"Sitze:  {snap.num_occupied_seats}/{snap.num_seats}")
    print(f"Tickets:{snap.tickets_session}")
    print(f"An Hst: {snap.is_at_stop}")

    buttons = vehicle.get("Buttons") or []
    print(f"\n=== Buttons ({len(buttons)}) – relevante Namen ===")
    for btn in buttons:
        name = btn.get("Name", "")
        state = btn.get("State", "")
        value = btn.get("Value", "")
        low = name.lower()
        if any(
            x in low
            for x in (
                "line",
                "linie",
                "route",
                "stop",
                "halt",
                "ibis",
                "fis",
                "display",
                "nav",
                "dest",
                "ziel",
                "kurs",
            )
        ):
            print(f"  {name!r}  State={state!r}  Value={value!r}")

    print("\n=== UMG-Pfade ===")
    for p in collect_umg_paths(vehicle):
        print(f"  {p}")

    print("\n=== UMG-Inhalte (JSON-Suche) ===")
    for path in collect_umg_paths(vehicle)[:10]:
        data = c._get_json(path.lstrip("/"))
        if not data:
            continue
        info = extract_from_json(data, path)
        if info.line_name or info.current_stop:
            print(f"  {path}: Linie={info.line_name!r} Stop={info.current_stop!r} Next={info.next_stop!r}")

    out = Path(__file__).parent / "last_telemetry_dump.json"
    out.write_text(json.dumps(vehicle, indent=2, ensure_ascii=False)[:500000], encoding="utf-8")
    print(f"\nVollständiger Dump: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
