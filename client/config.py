import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".the_bus_tracker" / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "device_id": None,
        "device_password": None,
        "access_token": None,
        "user_id": None,
        "username": "",
        "display_name": "",
        "server_url": None,
        "server_label": None,
        "active_spedition_id": None,
    }


def save_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
