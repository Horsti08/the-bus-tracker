# Render Deploy – Schritt für Schritt (5 Minuten)

## Was du brauchst

- GitHub-Konto (kostenlos)
- Render-Konto (kostenlos): https://dashboard.render.com

---

## Schritt 1: Code auf GitHub

### Variante A – GitHub Website (ohne Git installiert)

1. Gehe zu https://github.com/new
2. Repository-Name: `the-bus-tracker`
3. **Create repository**
4. Klicke **“uploading an existing file”**
5. Ziehe den **gesamten Ordner** `The Bus Tracker` rein (oder ZIP entpacken und alle Dateien hochladen)
6. Commit

### Variante B – GitHub Desktop

1. GitHub Desktop installieren
2. File → Add local repository → `G:\The Bus Tracker`
3. Publish repository

---

## Schritt 2: Auf Render deployen

1. Öffne https://dashboard.render.com
2. **New +** → **Blueprint**
3. **Connect GitHub** (einmalig autorisieren)
4. Repository **`the-bus-tracker`** auswählen
5. Render zeigt die **`render.yaml`** – Services:
   - `the-bus-tracker-api` (Python, Free)
6. Klicke **Apply**

⏳ Warte 3–5 Minuten bis Status **Live** ist.

---

## Schritt 3: URL testen

Deine URL steht oben im Dashboard, z.B.:

```
https://the-bus-tracker-api.onrender.com
```

Im Browser oder PowerShell:

```powershell
curl https://the-bus-tracker-api.onrender.com/health
```

Antwort: `{"status":"ok","version":"1.2.0",...}`

---

## Schritt 4: EXE für alle Spieler

Falls die URL anders heißt, in `shared\__init__.py` anpassen:

```python
COMMUNITY_API_ENDPOINTS = [
    "https://DEINE-URL.onrender.com",
]
```

Dann neu bauen:

```powershell
cd "G:\The Bus Tracker"
.\build.ps1
```

`dist\TheBusTracker.exe` an alle geben – **fertig**.

---

## Automatisch mit API-Key

1. Render Dashboard → Account Settings → **API Keys** → Create
2. PowerShell:

```powershell
$env:RENDER_API_KEY = "rnd_dein_key"
.\scripts\deploy_render.ps1 -GitHubRepoUrl "https://github.com/DEINNAME/the-bus-tracker"
```

---

## Häufige Probleme

| Problem | Lösung |
|---------|--------|
| 404 auf URL | Deploy noch nicht fertig – Events-Tab prüfen |
| Erster Request langsam | Free Tier „schläft“ – 30s warten |
| Build failed | `requirements.txt` im Repo-Root prüfen |
| Daten weg nach Redeploy | Normal auf Free ohne Disk – für Produktion Paid Plan |

---

## Nach dem Deploy

- Einladungslinks: `https://deine-url.onrender.com/join/CODE`
- Alle EXEs verbinden automatisch – **kein WLAN nötig**
