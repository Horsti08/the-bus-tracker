# Shared constants – SPEDV-Modell: zentraler Community-API-Server im Internet

APP_VERSION = "1.2.0"
APP_NAME = "The Bus Tracker"
COMMUNITY_SERVER_NAME = "The Bus Tracker Community"

DEFAULT_TELEMETRY_HOST = "127.0.0.1"
DEFAULT_TELEMETRY_PORT = 37337

API_PORT = 5050
DISCOVERY_PORT = 5051

# Update-Manifest (URLs + community_api_urls Liste)
UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/Horsti08/the-bus-tracker/main/releases/version.json"
)

# === SPEDV-Style: Alle Clients verbinden hierhin (Internet, kein WLAN nötig) ===
# Nach deploy/community/README.md einmal deployen, dann URL hier eintragen.
# Reihenfolge = Priorität (erste erreichbare gewinnt).
COMMUNITY_API_ENDPOINTS: list[str] = [
    # Standard-Ziel nach Render-Deploy (siehe deploy/render.yaml):
    "https://the-bus-tracker-api.onrender.com",
]

# Zusätzliche URLs (z.B. Backup-Server)
PUBLIC_API_URLS: list[str] = []

LOCAL_API_URL = f"http://127.0.0.1:{API_PORT}"

# Verbindungs-Timeouts
COMMUNITY_CONNECT_TIMEOUT = 8.0
COMMUNITY_RETRY_COUNT = 3
