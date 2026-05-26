"""The Bus Karten – Spielkoordinaten (Location X/Y) zu Kartenposition."""

from __future__ import annotations

# LevelName-Teilstrings → Karte (aus Telemetrie world.LevelName)
MAP_PROFILES: dict[str, dict] = {
    "berlin": {
        "title": "Berlin",
        "keywords": ("berlin", "ber", "potsdam"),
        "x_min": 120_000.0,
        "x_max": 210_000.0,
        "y_min": 50_000.0,
        "y_max": 120_000.0,
        "base_lat": 52.52,
        "base_lon": 13.405,
    },
    "hamburg": {
        "title": "Hamburg",
        "keywords": ("hamburg", "hh", "elbe"),
        "x_min": 80_000.0,
        "x_max": 180_000.0,
        "y_min": 40_000.0,
        "y_max": 110_000.0,
        "base_lat": 53.551,
        "base_lon": 9.993,
    },
    "castrop": {
        "title": "Castrop-Rauxel",
        "keywords": ("castrop", "ruhr"),
        "x_min": 150_000.0,
        "x_max": 180_000.0,
        "y_min": 70_000.0,
        "y_max": 85_000.0,
        "base_lat": 51.549,
        "base_lon": 7.309,
    },
}


def detect_map(level_name: str) -> str:
    low = (level_name or "").lower()
    for key, prof in MAP_PROFILES.items():
        if any(k in low for k in prof["keywords"]):
            return key
    return "berlin" if not low else "berlin"


def game_to_normalized(level_name: str, x: float, y: float) -> tuple[float, float, str]:
    key = detect_map(level_name)
    p = MAP_PROFILES.get(key, MAP_PROFILES["berlin"])
    nx = (x - p["x_min"]) / max(p["x_max"] - p["x_min"], 1.0)
    ny = (y - p["y_min"]) / max(p["y_max"] - p["y_min"], 1.0)
    return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny)), p["title"]
