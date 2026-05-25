# Community-Server (SPEDV-Modell)

**Ein zentraler Internet-Server** – alle Spieler verbinden sich automatisch, **ohne WLAN**.

## Schnell-Deploy auf Render.com (kostenlos)

1. Account auf [render.com](https://render.com)
2. **New → Blueprint** → Repository verbinden
3. `deploy/render.yaml` wird erkannt → **Deploy**
4. URL kopieren, z.B. `https://the-bus-tracker-api.onrender.com`
5. In `shared/__init__.py` unter `COMMUNITY_API_ENDPOINTS` eintragen (falls abweichend)
6. EXE neu bauen (`.\build.ps1`) und an alle Spieler verteilen

Alle Clients verbinden dann automatisch zu dieser URL.

## Lokal testen (Entwicklung)

```powershell
cd "g:\The Bus Tracker"
python run_server.py
```

Dann in `shared/__init__.py` temporär eintragen:

```python
COMMUNITY_API_ENDPOINTS = ["http://127.0.0.1:5050"]
```

## Endpunkte (wie SPEDV-API)

| Endpoint | Beschreibung |
|----------|----------------|
| `GET /health` | Server online? |
| `GET /app/info` | Name, Spieler online, API-URL |
| `GET /app/version` | Version + `community_api_url` |
| `POST /auth/register` | Konto |
| `POST /auth/login` | Login |
| `GET/POST /speditions` | Firmen |
| `POST /speditions/join` | Einladung |
| `GET /speditions/{id}/live` | Wer fährt wo |
| `POST /live` | Position senden |
| `GET /join/{code}` | Web-Einladung |

## Einladungslinks

Nach Deploy sind Links öffentlich:

`https://the-bus-tracker-api.onrender.com/join/ABC123`

Spieler gibt den Code in der EXE unter **Spedition → Beitreten** ein.

## Wichtig

- **Free Tier** auf Render schläft nach Inaktivität – erster Request dauert ~30s (wie bei vielen Free-APIs).
- Für 24/7: Paid Plan oder VPS mit `docker build -f deploy/Dockerfile .`
