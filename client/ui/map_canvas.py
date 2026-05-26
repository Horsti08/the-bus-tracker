"""Live-Karte – Berlin / Hamburg (Spielkoordinaten)."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from client.ui.theme import ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED, BG_CARD, TEXT, TEXT_DIM
from shared.maps import MAP_PROFILES, game_to_normalized


class LiveMapCanvas(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=12, **kwargs)
        self.title_lbl = ctk.CTkLabel(
            self, text="Live-Karte", font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT
        )
        self.title_lbl.pack(anchor="w", padx=12, pady=(10, 4))
        self.sub_lbl = ctk.CTkLabel(self, text="Warte auf Daten…", text_color=TEXT_DIM, font=ctk.CTkFont(size=11))
        self.sub_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        self.canvas = tk.Canvas(self, bg="#0d1118", highlightthickness=0, height=420)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self._drivers: list[dict] = []
        self._map_key = "berlin"
        self._selected_id: int | None = None

    def set_drivers(self, drivers: list[dict], map_title: str = ""):
        self._drivers = drivers
        if drivers:
            lvl = drivers[0].get("level_name") or ""
            from shared.maps import detect_map

            self._map_key = detect_map(lvl)
        title = map_title or MAP_PROFILES.get(self._map_key, {}).get("title", "Karte")
        self.sub_lbl.configure(
            text=f"{title}  •  {len(drivers)} Fahrer online  •  Klick = Details"
        )
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 400)
        h = max(c.winfo_height(), 300)
        pad = 24

        # Karten-Raster (Stil Berlin)
        for i in range(0, w, 40):
            c.create_line(i, pad, i, h - pad, fill="#1e2836", width=1)
        for j in range(pad, h - pad, 40):
            c.create_line(pad, j, w - pad, j, fill="#1e2836", width=1)

        prof = MAP_PROFILES.get(self._map_key, MAP_PROFILES["berlin"])
        c.create_text(
            w // 2, 14, text=prof["title"].upper(), fill="#4a5568", font=("Segoe UI", 10, "bold")
        )

        # Spieler
        for d in self._drivers:
            x = float(d.get("pos_x") or 0)
            y = float(d.get("pos_y") or 0)
            if x == 0 and y == 0:
                continue
            nx, ny, _ = game_to_normalized(d.get("level_name", ""), x, y)
            px = pad + nx * (w - 2 * pad)
            py = h - pad - ny * (h - 2 * pad)
            col = ACCENT_RED if d.get("is_overspeed") else ACCENT_GREEN
            uid = d.get("user_id")
            r = 10 if uid == self._selected_id else 7
            c.create_oval(px - r, py - r, px + r, py + r, fill=col, outline="white", width=2, tags=f"drv_{uid}")
            c.create_text(px, py - 16, text=d.get("display_name", "?")[:12], fill=TEXT, font=("Segoe UI", 9))

            def on_click(event, drv=d):
                self._selected_id = drv.get("user_id")
                self._show_popup(drv)
                self._redraw()

            tag = f"drv_{uid}"
            c.tag_bind(tag, "<Button-1>", on_click)

    def _show_popup(self, d: dict):
        lines = (
            f"{d.get('display_name')}\n"
            f"{d.get('speed_kmh', 0):.0f} km/h  |  {d.get('revenue_session_eur', 0):.2f} €\n"
            f"Linie {d.get('line_name') or '–'}\n"
            f"{d.get('current_stop') or '–'} → {d.get('next_stop') or '–'}"
        )
        self.sub_lbl.configure(text=lines)
