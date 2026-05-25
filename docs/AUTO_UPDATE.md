# Auto-Update – So funktioniert es

## Kurz: Nein, nur `build.ps1` reicht nicht

| Schritt | Wer macht es | Was passiert |
|---------|--------------|--------------|
| `.\build.ps1` | Du | Neue EXE lokal in `dist\` |
| EXE **hochladen** | Du | Öffentliche URL (Download-Link) |
| `version.json` + Server | Du | Höhere Versionsnummer + `download_url` |
| GitHub pushen | Du | Manifest für alle Clients |
| App starten | Spieler | Prüft Update → lädt EXE |

**Nur bauen** = nur auf **deinem PC** die neue Datei. Andere bekommen sie **nicht** automatisch.

---

## Ablauf (einmal einrichten)

### 1. EXE bauen
```powershell
.\build.ps1
```
→ `dist\TheBusTracker.exe`

### 2. EXE irgendwo hosten (öffentliche URL)

**Option A – GitHub Release (empfohlen)**
1. https://github.com/Horsti08/the-bus-tracker/releases → **Create a new release**
2. Tag: `v1.2.1`
3. `TheBusTracker.exe` anhängen
4. Veröffentlichen
5. Rechtsklick auf EXE → Link kopieren (direkte Download-URL)

**Option B – Google Drive / Dropbox**  
→ „Link für alle mit Link“ → direkte Download-URL

### 3. Manifest setzen
```powershell
.\scripts\publish_update.ps1 -DownloadUrl "https://github.com/Horsti08/the-bus-tracker/releases/download/v1.2.1/TheBusTracker.exe"
```

### 4. Auf GitHub pushen
```powershell
$env:GITHUB_TOKEN = "DEIN_TOKEN"
.\scripts\upload_to_github.ps1
```

Render synct → Server liefert auch `/app/version` mit neuer Version (nach Server-Deploy mit neuem Code).

---

## Was die App macht

- **Beim Start:** prüft `https://the-bus-tracker-api.onrender.com/app/version`
- **Alle 30 Min:** erneut
- Wenn `version` > installierte Version **und** `download_url` gesetzt:
  - Hinweis in der Sidebar
  - Bei Start: Dialog „Update installieren?“
  - Download + Neustart der EXE

Ohne `download_url` → nur Hinweis „Neue Version verfügbar“, **kein** automatischer Download.

---

## Versionsnummer

In `shared\__init__.py`:
```python
APP_VERSION = "1.2.1"
```

Jedes Update: Nummer erhöhen (z.B. `1.2.2`), neu bauen, hochladen, `publish_update.ps1` ausführen.
