# Dein Repo: https://github.com/Horsti08/the-bus-tracker

## Schritt 1 – Code hochladen (2 Min.)

Das Repo ist noch **leer**. So füllst du es:

1. Öffne: https://github.com/Horsti08/the-bus-tracker/upload/main
2. Ziehe diese ZIP in den Browser:
   ```
   G:\The Bus Tracker\the-bus-tracker-github.zip
   ```
   **ODER** alle Dateien aus `G:\The Bus Tracker` (ohne `dist`, `data`, `build`)
3. Unten: **Commit changes**

Wichtig: `render.yaml` muss im Root liegen (ist in der ZIP).

---

## Schritt 2 – Render deployen (3 Min.)

1. https://dashboard.render.com → einloggen
2. **New +** → **Blueprint**
3. GitHub verbinden → Repo **`Horsti08/the-bus-tracker`** wählen
4. Service **`the-bus-tracker-api`** → **Apply**
5. Warten bis **Live** (grün)

Deine API-URL (steht im Render-Dashboard):

```
https://the-bus-tracker-api.onrender.com
```

Test:

```powershell
curl https://the-bus-tracker-api.onrender.com/health
```

---

## Schritt 3 – EXE (optional URL anpassen)

Falls Render eine andere URL vergibt, in `shared\__init__.py`:

```python
COMMUNITY_API_ENDPOINTS = ["https://DEINE-URL.onrender.com"]
```

Dann:

```powershell
.\build.ps1
```

---

## Fertig

Alle Spieler: `TheBusTracker.exe` starten → verbinden automatisch zum Community-Server → Spedition + Live ohne WLAN.
