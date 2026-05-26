"""HTTP-Client für The Bus Telemetrie (Port 37337)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from client.telemetry.route_info import (
    RouteInfo,
    collect_umg_paths,
    extract_from_buttons,
    extract_from_json,
)
from shared import DEFAULT_TELEMETRY_HOST, DEFAULT_TELEMETRY_PORT

# Max. UMG-Subrequests pro Snapshot (Performance)
_MAX_UMG_FETCHES = 10


@dataclass
class TelemetryConfig:
    host: str = DEFAULT_TELEMETRY_HOST
    port: int = DEFAULT_TELEMETRY_PORT
    timeout: float = 0.6

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class VehicleSnapshot:
    connected: bool = False
    actor_name: str = ""
    vehicle_model: str = ""
    speed_kmh: float = 0.0
    allowed_speed_kmh: float = 0.0
    engine_started: bool = False
    ignition_enabled: bool = False
    passenger_doors_open: bool = False
    is_at_stop: bool = False
    num_occupied_seats: int = 0
    num_seats: int = 0
    location_x: float = 0.0
    location_y: float = 0.0
    location_z: float = 0.0
    level_name: str = ""
    line_name: str = ""
    route_name: str = ""
    current_stop: str = ""
    next_stop: str = ""
    revenue_eur: float = 0.0
    tickets_session: int = 0
    bus_logic_sales: dict[str, Any] = field(default_factory=dict)
    raw_buttons: list[dict[str, Any]] = field(default_factory=list)
    extra_paths: dict[str, str] = field(default_factory=dict)
    route_sources: list[str] = field(default_factory=list)

    @property
    def passengers_display(self) -> str:
        """Anzeige für Fahrgäste – Tickets oft zuverlässiger als Sitz-Sensor."""
        if self.num_occupied_seats > 0:
            return f"{self.num_occupied_seats} im Bus (Sitzplätze)"
        if self.tickets_session > 0:
            return f"ca. {self.tickets_session} (laut Ticketverkauf)"
        return "keine erkannt"

    @property
    def line_display(self) -> str:
        if self.line_name and self.route_name and self.route_name != self.line_name:
            return f"Linie {self.line_name} · {self.route_name}"
        if self.line_name:
            return f"Linie {self.line_name}"
        if self.route_name:
            return self.route_name
        return "– (Route im Spiel wählen / IBIS)"

    @property
    def stop_display(self) -> str:
        if self.is_at_stop and self.current_stop:
            return f"An Haltestelle: {self.current_stop}"
        if self.is_at_stop:
            return "An Haltestelle"
        if self.current_stop:
            return self.current_stop
        return "–"


def _bool_str(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


class TelemetryClient:
    def __init__(self, config: TelemetryConfig | None = None):
        self.config = config or TelemetryConfig()
        self._client = httpx.Client(timeout=self.config.timeout)
        self._umg_rotate = 0

    def close(self):
        self._client.close()

    def _get_json(self, path: str) -> Any | None:
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        try:
            r = self._client.get(url)
            if r.status_code == 200:
                return r.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            pass
        return None

    def is_connected(self) -> bool:
        data = self._get_json("vehicles/Current")
        return data is not None

    def fetch_snapshot(self) -> VehicleSnapshot:
        snap = VehicleSnapshot()
        vehicle = self._get_json("vehicles/Current")
        world = self._get_json("world")
        player = self._get_json("player")

        if vehicle is None:
            return snap

        snap.connected = True
        snap.actor_name = vehicle.get("ActorName", "")
        snap.vehicle_model = vehicle.get("VehicleModel", "")
        snap.speed_kmh = float(vehicle.get("Speed", 0) or 0)
        snap.allowed_speed_kmh = float(vehicle.get("AllowedSpeed", 0) or 0)
        snap.engine_started = _bool_str(vehicle.get("EngineStarted", "false"))
        snap.ignition_enabled = _bool_str(vehicle.get("IgnitionEnabled", "false"))
        snap.passenger_doors_open = _bool_str(vehicle.get("PassengerDoorsOpen", "false"))
        snap.is_at_stop = _bool_str(vehicle.get("IsAtStop", "false"))
        snap.num_occupied_seats = int(vehicle.get("NumOccupiedSeats", 0) or 0)
        snap.num_seats = int(vehicle.get("NumSeats", 0) or 0)

        loc = vehicle.get("Location") or {}
        snap.location_x = float(loc.get("X", 0) or 0)
        snap.location_y = float(loc.get("Y", 0) or 0)
        snap.location_z = float(loc.get("Z", 0) or 0)

        if world:
            snap.level_name = world.get("LevelName", "")

        route = RouteInfo()
        route.merge(extract_from_json(vehicle, "vehicle"))

        umg = vehicle.get("UMG") or {}
        if isinstance(umg, dict):
            for key, rel_path in umg.items():
                if isinstance(rel_path, str):
                    snap.extra_paths[key] = rel_path

        bus_logic = vehicle.get("BusLogic") or {}
        sales = bus_logic.get("Sales") or {}
        if isinstance(sales, dict):
            snap.bus_logic_sales = sales
            snap.revenue_eur = _extract_revenue_from_sales(sales)
            snap.tickets_session = int(
                sales.get("TicketCount", sales.get("Tickets", sales.get("NumTickets", 0))) or 0
            )
        route.merge(extract_from_json(bus_logic, "BusLogic"))

        buttons = vehicle.get("Buttons") or []
        snap.raw_buttons = buttons if isinstance(buttons, list) else []
        route.merge(extract_from_buttons(snap.raw_buttons))

        # UMG-Unterseiten (Atron, Navigation, IBIS, …)
        paths = collect_umg_paths(vehicle)
        if paths:
            start = self._umg_rotate % max(len(paths), 1)
            self._umg_rotate += _MAX_UMG_FETCHES
            batch = []
            for i in range(_MAX_UMG_FETCHES):
                batch.append(paths[(start + i) % len(paths)])
            for path in batch:
                sub = self._get_json(path.lstrip("/"))
                if isinstance(sub, dict):
                    route.merge(extract_from_json(sub, path))
                    nested_umg = sub.get("UMG")
                    if isinstance(nested_umg, dict):
                        for nk, np in nested_umg.items():
                            if isinstance(np, str):
                                sub2 = self._get_json(np.lstrip("/"))
                                if isinstance(sub2, dict):
                                    route.merge(extract_from_json(sub2, f"{path}/{nk}"))

        if player and isinstance(player, dict):
            route.merge(extract_from_json(player, "player"))

        snap.line_name = route.line_name
        snap.route_name = route.route_name
        snap.current_stop = route.current_stop
        snap.next_stop = route.next_stop
        snap.route_sources = route.sources

        return snap


def _extract_revenue_from_sales(sales: dict[str, Any]) -> float:
    for key in ("TotalRevenue", "Revenue", "Total", "Sum", "Amount", "Cash"):
        if key in sales:
            try:
                return float(sales[key])
            except (TypeError, ValueError):
                pass
    total = 0.0
    for k, v in sales.items():
        if k.lower() in ("ticketcount", "tickets", "count"):
            continue
        try:
            total += float(v)
        except (TypeError, ValueError):
            pass
    return total
