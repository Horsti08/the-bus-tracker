"""Linie, Route und Haltestellen aus The-Bus-Telemetrie extrahieren."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# UI-Zustände, die keine Fahrtdaten sind
_SKIP_STATES = frozenset(
    {
        "",
        "primary",
        "secondary",
        "false",
        "true",
        "none",
        "hover",
        "pressed",
        "disabled",
        "normal",
        "default",
        "inactive",
        "active",
        "hidden",
        "visible",
    }
)

_LINE_KEY_HINTS = (
    "linename",
    "line_name",
    "line",
    "linie",
    "liniennummer",
    "linennr",
    "routenumber",
    "kurs",
    "kursnummer",
    "fahrtnummer",
    "displayline",
    "ibisline",
)
_ROUTE_KEY_HINTS = (
    "routename",
    "route_name",
    "route",
    "routebezeichnung",
    "fahrt",
    "tour",
    "destination",
    "ziel",
    "zieltext",
    "displaytext",
)
_STOP_CURRENT_HINTS = (
    "currentstop",
    "current_stop",
    "stopname",
    "haltestelle",
    "halt",
    "thisstop",
    "aktuellehaltestelle",
    "stopcurrent",
)
_STOP_NEXT_HINTS = (
    "nextstop",
    "next_stop",
    "nexthaltestelle",
    "stopnext",
    "naechstehaltestelle",
)


@dataclass
class RouteInfo:
    line_name: str = ""
    route_name: str = ""
    current_stop: str = ""
    next_stop: str = ""
    sources: list[str] = field(default_factory=list)

    def merge(self, other: "RouteInfo") -> None:
        if other.line_name and not self.line_name:
            self.line_name = other.line_name
        if other.route_name and not self.route_name:
            self.route_name = other.route_name
        if other.current_stop and not self.current_stop:
            self.current_stop = other.current_stop
        if other.next_stop and not self.next_stop:
            self.next_stop = other.next_stop
        for s in other.sources:
            if s not in self.sources:
                self.sources.append(s)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in _SKIP_STATES:
        return ""
    return s


def _looks_like_line(text: str) -> bool:
    if not text or len(text) > 64:
        return False
    low = text.lower()
    if low in _SKIP_STATES:
        return False
    # Linie 245, M29, X7, 300, Bus 100
    if re.match(r"^[A-Za-z]?\d{1,4}[A-Za-z]?$", text):
        return True
    if re.search(r"\b(linie|line|bus)\b", low):
        return True
    if re.match(r"^[A-Z]\d{1,2}$", text):  # M29
        return True
    return len(text) >= 2 and not text.startswith("http")


def _looks_like_stop(text: str) -> bool:
    if not text or len(text) < 2 or len(text) > 120:
        return False
    low = text.lower()
    if low in _SKIP_STATES:
        return False
    if low in ("drive", "neutral", "reverse", "park", "on", "off", "true", "false"):
        return False
    if re.match(r"^\d{1,4}[a-z]?$", text, re.I):
        return True
    # Name, Abkürzung (Hbf) oder mehrteilig
    if " " in text or "-" in text or "'" in text:
        return True
    if len(text) >= 3 and re.search(r"[a-zA-ZäöüÄÖÜß]", text):
        return True
    return False


def _key_matches(key: str, hints: tuple[str, ...]) -> bool:
    k = key.lower().replace("_", "").replace("-", "")
    return any(h in k for h in hints)


def extract_from_json(data: Any, source: str = "json", depth: int = 0) -> RouteInfo:
    info = RouteInfo()
    if depth > 12 or data is None:
        return info

    if isinstance(data, dict):
        for key, val in data.items():
            klow = key.lower()
            if isinstance(val, (dict, list)):
                sub = extract_from_json(val, source, depth + 1)
                info.merge(sub)
                continue
            text = _clean(val)
            if not text:
                continue
            if _key_matches(klow, _LINE_KEY_HINTS) and _looks_like_line(text):
                if not info.line_name:
                    info.line_name = text
                    info.sources.append(f"{source}:{key}")
            elif _key_matches(klow, _ROUTE_KEY_HINTS) and len(text) > 1:
                if not info.route_name:
                    info.route_name = text
                    info.sources.append(f"{source}:{key}")
            elif _key_matches(klow, _STOP_CURRENT_HINTS) and _looks_like_stop(text):
                if not info.current_stop:
                    info.current_stop = text
                    info.sources.append(f"{source}:{key}")
            elif _key_matches(klow, _STOP_NEXT_HINTS) and _looks_like_stop(text):
                if not info.next_stop:
                    info.next_stop = text
                    info.sources.append(f"{source}:{key}")

    elif isinstance(data, list):
        for item in data:
            info.merge(extract_from_json(item, source, depth + 1))

    return info


def extract_from_buttons(buttons: list[dict[str, Any]]) -> RouteInfo:
    info = RouteInfo()
    for btn in buttons:
        name = str(btn.get("Name", "") or "")
        tooltip = str(btn.get("Tooltip", "") or "")
        state = _clean(btn.get("State"))
        value = _clean(btn.get("Value"))
        combined = f"{name} {tooltip}".lower()

        candidates = [state, value]
        # Manche Displays: Name = "Linie", State = "245"
        if state and value and state != value:
            candidates = [value, state]

        if any(x in combined for x in ("line", "linie", "kurs", "ibis", "fis", "display")):
            for c in candidates:
                if _looks_like_line(c):
                    info.line_name = info.line_name or c
                    info.sources.append(f"button:{name}")
                    break
            if "route" in combined or "fahrt" in combined or "tour" in combined:
                for c in candidates:
                    if c and not _looks_like_line(c):
                        info.route_name = info.route_name or c
                        break

        if "route" in combined and "line" not in combined:
            for c in candidates:
                if c and len(c) > 2:
                    info.route_name = info.route_name or c

        if "stop" in combined or "halt" in combined or "haltestelle" in combined:
            if "next" in combined or "nächst" in combined or "naechst" in combined:
                for c in candidates:
                    if _looks_like_stop(c):
                        info.next_stop = info.next_stop or c
            elif "current" in combined or "aktuel" in combined or "this" in combined:
                for c in candidates:
                    if _looks_like_stop(c):
                        info.current_stop = info.current_stop or c
            else:
                for c in candidates:
                    if _looks_like_stop(c):
                        if not info.current_stop:
                            info.current_stop = c
                        elif not info.next_stop:
                            info.next_stop = c

        # Generische Namen: "Stop_1" mit State = Haltestellenname
        if not info.current_stop and "stop" in name.lower() and _looks_like_stop(state):
            info.current_stop = state

    return info


def collect_umg_paths(vehicle: dict[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    umg = vehicle.get("UMG") or {}
    if not isinstance(umg, dict):
        return paths
    for _key, rel in umg.items():
        if not isinstance(rel, str):
            continue
        p = rel.strip()
        if not p:
            continue
        if not p.startswith("/"):
            p = f"/{p}"
        paths.append(p)
    # Bekannte Zusatzpfade (The Bus / TML)
    actor = vehicle.get("ActorName", "")
    if actor:
        for extra in (
            f"/vehicles/{actor}/UMG/Atron",
            f"/vehicles/{actor}/UMG/Navigation",
            f"/vehicles/{actor}/UMG/BoardComputer",
            f"/vehicles/{actor}/UMG/IBIS",
            f"/vehicles/{actor}/UMG/PassengerDisplay",
            f"/vehicles/Current/UMG/Atron",
            f"/vehicles/Current/UMG/Navigation",
            f"/vehicles/Current/UMG/BoardComputer",
        ):
            if extra not in paths:
                paths.append(extra)
    return paths
