"""Fahrt- und Umsatz-Tracking aus Telemetrie-Snapshots."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from client.telemetry.client import VehicleSnapshot


@dataclass
class TripStats:
    active: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None
    vehicle_model: str = ""
    line_name: str = ""
    route_name: str = ""
    level_name: str = ""
    distance_km: float = 0.0
    max_speed_kmh: float = 0.0
    speed_samples: list[float] = field(default_factory=list)
    tickets_sold: int = 0
    revenue_eur: float = 0.0
    stops_served: int = 0
    overspeed_events: int = 0
    uploaded: bool = False
    _last_revenue: float = 0.0
    _last_tickets: int = 0
    _last_x: float | None = None
    _last_y: float | None = None
    _was_at_stop: bool = False
    _overspeed_cooldown: int = 0

    @property
    def avg_speed_kmh(self) -> float:
        if not self.speed_samples:
            return 0.0
        return sum(self.speed_samples) / len(self.speed_samples)

    def to_dict(self) -> dict:
        return {
            "vehicle_model": self.vehicle_model,
            "line_name": self.line_name,
            "route_name": self.route_name,
            "level_name": self.level_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "distance_km": round(self.distance_km, 3),
            "max_speed_kmh": round(self.max_speed_kmh, 1),
            "avg_speed_kmh": round(self.avg_speed_kmh, 1),
            "tickets_sold": self.tickets_sold,
            "revenue_eur": round(self.revenue_eur, 2),
            "stops_served": self.stops_served,
            "overspeed_events": self.overspeed_events,
        }


class TripTracker:
    """Startet eine Fahrt bei laufendem Motor, beendet bei Abbruch."""

    def __init__(self):
        self.trip = TripStats()
        self.session_revenue = 0.0

    def update(self, snap: VehicleSnapshot) -> TripStats:
        driving = snap.connected and snap.engine_started

        if driving and not self.trip.active:
            self._start_trip(snap)
        elif not driving and self.trip.active:
            self._end_trip()

        if not self.trip.active:
            return self.trip

        self._accumulate(snap)
        return self.trip

    def force_end(self) -> TripStats | None:
        if self.trip.active:
            self._end_trip()
            return self.trip
        return None

    def _start_trip(self, snap: VehicleSnapshot):
        self.trip = TripStats(
            active=True,
            started_at=datetime.now(timezone.utc),
            vehicle_model=snap.vehicle_model,
            line_name=snap.line_name,
            route_name=snap.route_name,
            level_name=snap.level_name,
            _last_revenue=snap.revenue_eur,
            _last_tickets=snap.tickets_session,
        )

    def _end_trip(self):
        self.trip.active = False
        self.trip.ended_at = datetime.now(timezone.utc)

    def _accumulate(self, snap: VehicleSnapshot):
        t = self.trip
        t.vehicle_model = snap.vehicle_model or t.vehicle_model
        t.line_name = snap.line_name or t.line_name
        t.route_name = snap.route_name or t.route_name
        t.level_name = snap.level_name or t.level_name

        if snap.speed_kmh > 0.5:
            t.speed_samples.append(snap.speed_kmh)
            t.max_speed_kmh = max(t.max_speed_kmh, snap.speed_kmh)

        if snap.allowed_speed_kmh > 0 and snap.speed_kmh > snap.allowed_speed_kmh + 3:
            if t._overspeed_cooldown <= 0:
                t.overspeed_events += 1
                t._overspeed_cooldown = 30
        elif t._overspeed_cooldown > 0:
            t._overspeed_cooldown -= 1

        if snap.is_at_stop and not t._was_at_stop:
            t.stops_served += 1
        t._was_at_stop = snap.is_at_stop

        if t._last_x is not None:
            dx = snap.location_x - t._last_x
            dy = snap.location_y - t._last_y
            dist_m = math.sqrt(dx * dx + dy * dy)
            if 0.5 < dist_m < 500:
                t.distance_km += dist_m / 1000.0
        t._last_x = snap.location_x
        t._last_y = snap.location_y

        if snap.revenue_eur > t._last_revenue:
            t.revenue_eur += snap.revenue_eur - t._last_revenue
            self.session_revenue = t.revenue_eur
        t._last_revenue = max(t._last_revenue, snap.revenue_eur)

        if snap.tickets_session > t._last_tickets:
            t.tickets_sold += snap.tickets_session - t._last_tickets
        t._last_tickets = max(t._last_tickets, snap.tickets_session)

        occupied_delta = max(0, snap.num_occupied_seats - getattr(self, "_prev_occupied", 0))
        if occupied_delta > 0 and snap.tickets_session == t._last_tickets:
            t.tickets_sold += occupied_delta
        self._prev_occupied = snap.num_occupied_seats
