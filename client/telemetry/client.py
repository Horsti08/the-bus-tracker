"""HTTP-Client für The Bus Telemetrie (Port 37337)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from shared import DEFAULT_TELEMETRY_HOST, DEFAULT_TELEMETRY_PORT


@dataclass
class TelemetryConfig:
    host: str = DEFAULT_TELEMETRY_HOST
    port: int = DEFAULT_TELEMETRY_PORT
    timeout: float = 0.5

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


def _bool_str(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


class TelemetryClient:
    def __init__(self, config: TelemetryConfig | None = None):
        self.config = config or TelemetryConfig()
        self._client = httpx.Client(timeout=self.config.timeout)

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

        umg = vehicle.get("UMG") or {}
        for key, rel_path in umg.items():
            if isinstance(rel_path, str):
                snap.extra_paths[key] = rel_path

        bus_logic = vehicle.get("BusLogic") or {}
        sales = bus_logic.get("Sales") or {}
        if isinstance(sales, dict):
            snap.bus_logic_sales = sales
            snap.revenue_eur = _extract_revenue_from_sales(sales)
            snap.tickets_session = int(sales.get("TicketCount", sales.get("Tickets", 0)) or 0)

        buttons = vehicle.get("Buttons") or []
        snap.raw_buttons = buttons if isinstance(buttons, list) else []
        snap.line_name, snap.route_name, snap.current_stop, snap.next_stop = _parse_route_from_buttons(
            snap.raw_buttons
        )

        if "Atron" in snap.extra_paths:
            atron = self._get_json(snap.extra_paths["Atron"].lstrip("/"))
            if isinstance(atron, dict):
                snap.line_name = snap.line_name or str(atron.get("Line", atron.get("LineName", "")))
                snap.route_name = snap.route_name or str(atron.get("Route", atron.get("RouteName", "")))
                snap.current_stop = snap.current_stop or str(
                    atron.get("CurrentStop", atron.get("Stop", ""))
                )
                snap.next_stop = snap.next_stop or str(atron.get("NextStop", ""))
                atron_sales = atron.get("Sales") or atron.get("BusLogic", {}).get("Sales")
                if isinstance(atron_sales, dict):
                    snap.bus_logic_sales = {**snap.bus_logic_sales, **atron_sales}
                    snap.revenue_eur = max(snap.revenue_eur, _extract_revenue_from_sales(atron_sales))

        if "Navigation" in snap.extra_paths:
            nav = self._get_json(snap.extra_paths["Navigation"].lstrip("/"))
            if isinstance(nav, dict):
                snap.line_name = snap.line_name or str(nav.get("Line", nav.get("LineName", "")))
                snap.route_name = snap.route_name or str(nav.get("Route", nav.get("RouteName", "")))
                snap.current_stop = snap.current_stop or str(
                    nav.get("CurrentStop", nav.get("StopName", ""))
                )
                snap.next_stop = snap.next_stop or str(nav.get("NextStop", ""))

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


def _parse_route_from_buttons(buttons: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    line, route, current, nxt = "", "", "", ""
    for btn in buttons:
        name = str(btn.get("Name", ""))
        state = str(btn.get("State", ""))
        value = str(btn.get("Value", ""))
        lower = name.lower()
        if "line" in lower and state and state not in ("Primary", "false", "None"):
            line = state if not line else line
        if "route" in lower and state and state not in ("Primary", "false"):
            route = state
        if "stop" in lower or "haltestelle" in lower:
            if "next" in lower:
                nxt = value or state
            elif "current" in lower or "aktuelle" in lower:
                current = value or state
    return line, route, current, nxt
