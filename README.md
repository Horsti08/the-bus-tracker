# The Bus Tracker v1.2.0

**SPEDV-Modell** – alle Spieler weltweit über **einen zentralen Internet-API-Server**. Kein WLAN, keine IP-Eingabe.

## SPEDV vs. The Bus Tracker

| SPEDV | The Bus Tracker |
|-------|-----------------|
| Zentraler SPEDV-Server im Internet | **Community-API** (`COMMUNITY_API_ENDPOINTS`) |
| Alle Clients verbinden automatisch | EXE verbindet beim Start – **kein WLAN** |
| VTC / Spedition / Live | Spedition, Einladungslink, Live-Karte |
| ETS2 Telemetrie lokal | The Bus Telemetrie Port 37337 |

## Was passiert automatisch

1. **EXE starten** → verbindet zum **Community-Server** (Internet)
2. **Fahrer-Konto** → automatisch erstellt (wie SPEDV-Login)
3. **The Bus** → Telemetrie erkannt sobald du im Bus sitzt
4. **Oberleiste** → welcher Server, wie viele online, Karte, The Bus Status
5. **Auto-Updater** → `releases/version.json`

## Community-Server (einmal einrichten)

**Ohne diesen Server kein Multiplayer übers Internet** (wie SPEDV ohne deren API).

→ Anleitung: **[deploy/community/README.md](deploy/community/README.md)**

Kurz: Auf [Render.com](https://render.com) deployen → URL in `shared/__init__.py` → EXE neu bauen → fertig für alle.

## Oberleiste in der EXE

| Anzeige | Bedeutung |
|---------|-----------|
| **Server: Lokal** | Du bist Host, Freunde im LAN finden dich automatisch |
| **Server: LAN – PC-Name** | Mit Host im gleichen Netzwerk verbunden |
| **Server: Community** | Zentraler Internet-Server (wenn in `version.json` eingetragen) |
| **Karte: Berlin …** | Aktuelle Map/Level aus The Bus |
| **The Bus: ✓** | Telemetrie aktiv |

## Für alle Spieler (ohne WLAN)

1. Community-Server deployen (siehe oben) – **einmal**
2. Jeder installiert **`TheBusTracker.exe`**
3. EXE öffnen → verbindet automatisch zum **gleichen Internet-Server**
4. Spedition gründen → **HTTPS-Link teilen** (z.B. `https://…/join/CODE`)
5. **Live-Karte** → alle Fahrer weltweit sichtbar

## The Bus einrichten (einmalig)

Einstellungen → **Telemetrie-Schnittstelle (BETA)** → Spiel neu starten → Route laden → einsteigen.

## Bauen

```powershell
.\build.ps1
```

EXE: `dist\TheBusTracker.exe`

## Test ohne Spiel

```powershell
python tools\mock_telemetry.py
.\dist\TheBusTracker.exe
```

## Dateien

- `client/` – GUI, Telemetrie, Updater, Discovery
- `server/` – API + UDP-Beacon
- `releases/version.json` – Version & Update-URLs
