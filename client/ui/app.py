"""The Bus Tracker – Zero-Config Desktop-Client."""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from client.api_client import ApiClient
from client.auto_auth import ensure_authenticated
from client.bootstrap import initialize_client
from client.config import load_config, save_config
from client.server_connect import CommunityServerUnavailable, ServerInfo
from client.telemetry.client import TelemetryClient, TelemetryConfig
from client.telemetry.tracker import TripTracker
from client.updater import check_for_update, download_and_apply
from shared import APP_VERSION, DEFAULT_TELEMETRY_HOST, DEFAULT_TELEMETRY_PORT

POLL_MS = 400
LIVE_SYNC_EVERY = 4


class BusTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"The Bus Tracker v{APP_VERSION}")
        self.geometry("1150x740")
        self.minsize(920, 620)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = load_config()
        self._running = True
        self._tick_count = 0
        self._active_spedition_id = self.config_data.get("active_spedition_id")
        self._last_snap = None
        self._server_info: ServerInfo | None = None

        self._build_shell()
        self._show_tab("loading")
        threading.Thread(target=self._async_bootstrap, daemon=True).start()

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=56, corner_radius=0)
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.topbar,
            text=f"🚌 The Bus Tracker  v{APP_VERSION}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        self.lbl_server = ctk.CTkLabel(
            self.topbar, text="Server: …", font=ctk.CTkFont(size=13)
        )
        self.lbl_server.grid(row=0, column=1, padx=8, sticky="e")

        self.lbl_game_map = ctk.CTkLabel(
            self.topbar, text="Karte: –", text_color="gray", font=ctk.CTkFont(size=13)
        )
        self.lbl_game_map.grid(row=0, column=2, padx=8, sticky="e")

        self.lbl_telemetry = ctk.CTkLabel(
            self.topbar, text="The Bus: …", font=ctk.CTkFont(size=13)
        )
        self.lbl_telemetry.grid(row=0, column=3, padx=16, sticky="e")

        body = ctk.CTkFrame(self, corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(body, width=190, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.lbl_user = ctk.CTkLabel(self.sidebar, text="", text_color="gray", wraplength=160)
        self.lbl_user.pack(pady=(16, 8), padx=12)

        for name, cmd in [
            ("Dashboard", lambda: self._show_tab("dashboard")),
            ("Spedition", lambda: self._show_tab("spedition")),
            ("Live-Karte", lambda: self._show_tab("live")),
            ("Konto", lambda: self._show_tab("account")),
        ]:
            ctk.CTkButton(self.sidebar, text=name, command=cmd, anchor="w").pack(
                fill="x", padx=12, pady=4
            )

        ctk.CTkButton(
            self.sidebar,
            text="Update prüfen",
            fg_color="gray30",
            command=self._check_update_manual,
        ).pack(side="bottom", fill="x", padx=12, pady=16)

        self.main = ctk.CTkFrame(body, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.tabs: dict[str, ctk.CTkFrame] = {}
        for key in ("loading", "dashboard", "spedition", "live", "account"):
            f = ctk.CTkFrame(self.main)
            f.grid(row=0, column=0, sticky="nsew")
            self.tabs[key] = f

        self._build_loading_tab()
        self._build_dashboard_tab()
        self._build_spedition_tab()
        self._build_live_tab()
        self._build_account_tab()
        self._show_tab("loading")

        self.telemetry = TelemetryClient(
            TelemetryConfig(host=DEFAULT_TELEMETRY_HOST, port=DEFAULT_TELEMETRY_PORT)
        )
        self.tracker = TripTracker()
        self.api: ApiClient | None = None

    def _async_bootstrap(self):
        try:
            offline = self.config_data.get("offline_mode", False)
            api, server, auth_ok = initialize_client(offline_mode=offline)
            self.after(0, lambda: self._on_ready(api, server, auth_ok))
        except CommunityServerUnavailable as exc:
            self.after(0, lambda: self._on_community_failed(str(exc)))
        except Exception as exc:
            self.after(0, lambda: self._on_bootstrap_failed(str(exc)))

    def _on_ready(self, api: ApiClient, server: ServerInfo, auth_ok: bool):
        self.api = api
        self._server_info = server
        if server.kind == "community":
            extra = f" | {server.players_online} online" if server.players_online else ""
            self.lbl_server.configure(
                text=f"Server: {server.label}{extra}",
                text_color="#5DADE2",
            )
        else:
            self.lbl_server.configure(
                text=f"Server: {server.label}",
                text_color="#F39C12",
            )
        if auth_ok:
            self.lbl_user.configure(text=f"👤 {api.display_name}")
            self._refresh_speditions()
        else:
            self.lbl_user.configure(text="👤 Gast (offline)")
        self._show_tab("dashboard")
        self.after(POLL_MS, self._poll_loop)

    def _on_community_failed(self, err: str):
        self.lbl_server.configure(text="Server: nicht erreichbar", text_color="#E74C3C")
        self._show_tab("loading")
        for w in self.tabs["loading"].winfo_children():
            w.destroy()
        box = ctk.CTkFrame(self.tabs["loading"])
        box.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(
            box,
            text="Community-Server nicht erreichbar",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#E74C3C",
        ).pack(pady=8)
        ctk.CTkLabel(
            box,
            text=(
                "Wie bei SPEDV brauchst du den zentralen Internet-Server\n"
                "für Speditionen mit Freunden (ohne WLAN).\n\n"
                f"{err}\n\n"
                "Der Server muss einmal online sein (siehe deploy/community/)."
            ),
            justify="center",
        ).pack(pady=8, padx=16)
        ctk.CTkButton(box, text="Erneut verbinden", command=self._retry_community).pack(
            pady=8, fill="x", padx=40
        )
        ctk.CTkButton(
            box,
            text="Offline-Modus (nur Solo, kein Multiplayer)",
            fg_color="gray30",
            command=self._start_offline_mode,
        ).pack(pady=4, fill="x", padx=40)

    def _retry_community(self):
        self.config_data["offline_mode"] = False
        save_config(self.config_data)
        for w in self.tabs["loading"].winfo_children():
            w.destroy()
        self._build_loading_tab()
        self._show_tab("loading")
        threading.Thread(target=self._async_bootstrap, daemon=True).start()

    def _start_offline_mode(self):
        self.config_data["offline_mode"] = True
        save_config(self.config_data)
        for w in self.tabs["loading"].winfo_children():
            w.destroy()
        self._build_loading_tab()
        threading.Thread(target=self._async_bootstrap, daemon=True).start()

    def _on_bootstrap_failed(self, err: str):
        self.lbl_server.configure(text="Server: Fehler", text_color="#E74C3C")
        messagebox.showerror("Verbindung", f"Fehler:\n{err}")

    def _show_tab(self, name: str):
        for key, frame in self.tabs.items():
            frame.grid_remove()
        self.tabs[name].grid(row=0, column=0, sticky="nsew")

    def _build_loading_tab(self):
        f = self.tabs["loading"]
        ctk.CTkLabel(
            f,
            text="Verbinde mit Community-Server…\n\n"
            "SPEDV-Modell: alle Spieler weltweit über Internet-API\n"
            "(kein WLAN nötig)\n\n"
            "The Bus Telemetrie startet automatisch mit dem Spiel.",
            font=ctk.CTkFont(size=15),
            justify="center",
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _build_dashboard_tab(self):
        f = self.tabs["dashboard"]
        f.grid_columnconfigure((0, 1), weight=1)
        cards = ctk.CTkFrame(f)
        cards.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)
        self.dash_cards = {}
        for i, (title, key, default) in enumerate(
            [
                ("Geschwindigkeit", "speed_val", "–"),
                ("Umsatz", "rev_val", "0 €"),
                ("Tickets", "tix_val", "0"),
                ("Strecke", "dist_val", "0 km"),
            ]
        ):
            card = ctk.CTkFrame(cards)
            card.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=title, text_color="gray").pack(pady=(12, 0))
            lbl = ctk.CTkLabel(card, text=default, font=ctk.CTkFont(size=26, weight="bold"))
            lbl.pack(pady=12)
            self.dash_cards[key] = lbl

        info = ctk.CTkFrame(f)
        info.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16, pady=8)
        f.grid_rowconfigure(1, weight=1)
        self.dash_info = ctk.CTkTextbox(info, height=220)
        self.dash_info.pack(fill="both", expand=True, padx=8, pady=8)
        self.dash_info.insert(
            "1.0",
            "Warte auf The Bus…\n\n"
            "Telemetrie in den Spieloptionen aktivieren (Port 37337).\n"
            "Sobald du auf einer Route im Bus sitzt, startet das Tracking automatisch.\n",
        )
        ctk.CTkButton(f, text="Fahrt beenden", command=self._end_trip_manual).grid(
            row=2, column=0, padx=16, pady=12, sticky="w"
        )

    def _build_spedition_tab(self):
        f = self.tabs["spedition"]
        f.grid_rowconfigure(2, weight=1)
        row = ctk.CTkFrame(f)
        row.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        ctk.CTkLabel(row, text="Spedition", font=ctk.CTkFont(size=20, weight="bold")).pack(
            side="left", padx=8
        )
        ctk.CTkButton(row, text="Aktualisieren", width=100, command=self._refresh_speditions).pack(
            side="right", padx=8
        )
        create = ctk.CTkFrame(f)
        create.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        self.sped_name = ctk.CTkEntry(create, placeholder_text="Name", width=180)
        self.sped_name.pack(side="left", padx=4)
        ctk.CTkButton(create, text="Gründen", command=self._create_spedition).pack(side="left", padx=8)
        self.invite_entry = ctk.CTkEntry(create, placeholder_text="Einladungscode", width=160)
        self.invite_entry.pack(side="right", padx=4)
        ctk.CTkButton(create, text="Beitreten", command=self._join_spedition).pack(side="right", padx=4)
        self.sped_list = ctk.CTkScrollableFrame(f)
        self.sped_list.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        self.stats_label = ctk.CTkLabel(f, text="", justify="left")
        self.stats_label.grid(row=3, column=0, sticky="ew", padx=24, pady=8)

    def _build_live_tab(self):
        f = self.tabs["live"]
        f.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            f, text="Live – Wer fährt wo?", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=12, anchor="w", padx=16)
        self.live_scroll = ctk.CTkScrollableFrame(f)
        self.live_scroll.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkButton(f, text="Aktualisieren", command=self._refresh_live).pack(pady=8)

    def _build_account_tab(self):
        f = self.tabs["account"]
        box = ctk.CTkFrame(f)
        box.pack(padx=24, pady=24, fill="x")
        ctk.CTkLabel(box, text="Konto (optional)", font=ctk.CTkFont(size=18, weight="bold")).pack(
            anchor="w", pady=8
        )
        ctk.CTkLabel(
            box,
            text="Beim ersten Start wird automatisch ein Fahrer-Konto erstellt.\n"
            "Hier kannst du einen eigenen Namen setzen:",
            justify="left",
            text_color="gray",
        ).pack(anchor="w", pady=4)
        self.acc_display = ctk.CTkEntry(box, placeholder_text="Anzeigename", width=280)
        self.acc_display.pack(anchor="w", pady=8)
        ctk.CTkButton(box, text="Anzeigename speichern", command=self._save_display).pack(
            anchor="w", pady=4
        )
        self.acc_user = ctk.CTkEntry(box, placeholder_text="Neuer Benutzername", width=280)
        self.acc_user.pack(anchor="w", pady=8)
        self.acc_pass = ctk.CTkEntry(box, placeholder_text="Passwort", show="*", width=280)
        self.acc_pass.pack(anchor="w", pady=4)
        ctk.CTkButton(box, text="Eigenes Konto anmelden", command=self._custom_login).pack(
            anchor="w", pady=8
        )

    def _check_update_manual(self):
        upd = check_for_update()
        if not upd:
            messagebox.showinfo("Update", f"Du hast die neueste Version ({APP_VERSION}).")
            return
        if upd.get("download_url") and getattr(__import__("sys"), "frozen", False):
            if messagebox.askyesno("Update", f"Version {upd['version']} installieren?"):
                download_and_apply(upd, self)
        else:
            messagebox.showinfo(
                "Update",
                f"Neue Version: {upd.get('version')}\n{upd.get('changelog', '')}",
            )

    def _save_display(self):
        name = self.acc_display.get().strip()
        if name and self.api:
            self.config_data["display_name"] = name
            save_config(self.config_data)
            self.api.display_name = name
            self.lbl_user.configure(text=f"👤 {name}")
            messagebox.showinfo("OK", "Name gespeichert.")

    def _custom_login(self):
        if not self.api:
            return
        try:
            self.api.login(self.acc_user.get().strip(), self.acc_pass.get())
            self.config_data["access_token"] = self.api.token
            self.config_data["username"] = self.api.username
            self.config_data["display_name"] = self.api.display_name
            save_config(self.config_data)
            self.lbl_user.configure(text=f"👤 {self.api.display_name}")
            messagebox.showinfo("OK", "Angemeldet!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def _create_spedition(self):
        if not self.api or not self.api.token:
            return
        try:
            self.api.create_spedition(self.sped_name.get().strip())
            self._refresh_speditions()
            messagebox.showinfo("OK", "Spedition erstellt – Link kopieren und teilen!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def _join_spedition(self):
        code = self.invite_entry.get().strip()
        if code.startswith("bus-tracker://join/"):
            code = code.split("/")[-1]
        try:
            self.api.join_spedition(code)
            self._refresh_speditions()
            messagebox.showinfo("OK", "Beigetreten!")
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def _refresh_speditions(self):
        if not self.api or not self.api.token:
            return
        for w in self.sped_list.winfo_children():
            w.destroy()
        try:
            speditions = self.api.list_speditions()
        except Exception:
            return
        for sp in speditions:
            row = ctk.CTkFrame(self.sped_list)
            row.pack(fill="x", pady=6, padx=4)
            ctk.CTkLabel(row, text=f"{sp['name']} ({sp['member_count']})").pack(
                side="left", padx=8
            )

            def select(s=sp):
                self._active_spedition_id = s["id"]
                self.config_data["active_spedition_id"] = s["id"]
                save_config(self.config_data)
                self._update_stats(s["id"])

            ctk.CTkButton(row, text="Aktiv", width=50, command=select).pack(side="right", padx=4)

            def copy_link(s=sp):
                self.clipboard_clear()
                self.clipboard_append(s["invite_link"])
                messagebox.showinfo("Link kopiert", s["invite_link"])

            ctk.CTkButton(row, text="Link", width=44, command=copy_link).pack(side="right", padx=4)
            if sp["is_owner"]:

                def delete(s=sp):
                    if messagebox.askyesno("Löschen", f"'{s['name']}' löschen?"):
                        self.api.delete_spedition(s["id"])
                        self._refresh_speditions()

                ctk.CTkButton(row, text="✕", width=36, fg_color="#8B0000", command=delete).pack(
                    side="right", padx=4
                )

    def _update_stats(self, spedition_id: int):
        try:
            s = self.api.get_stats(spedition_id)
            self.stats_label.configure(
                text=(
                    f"Statistik: {s['total_trips']} Fahrten | "
                    f"{s['total_revenue_eur']:.2f} € | {s['total_distance_km']:.1f} km"
                )
            )
        except Exception:
            pass

    def _refresh_live(self):
        if not self._active_spedition_id or not self.api:
            return
        for w in self.live_scroll.winfo_children():
            w.destroy()
        try:
            drivers = self.api.get_live_drivers(self._active_spedition_id)
        except Exception as e:
            ctk.CTkLabel(self.live_scroll, text=str(e)).pack()
            return
        if not drivers:
            ctk.CTkLabel(self.live_scroll, text="Niemand online.").pack(pady=20)
            return
        for d in drivers:
            card = ctk.CTkFrame(self.live_scroll)
            card.pack(fill="x", pady=6, padx=4)
            col = "#FF6B6B" if d["is_overspeed"] else "#2ECC71"
            ctk.CTkLabel(
                card,
                text=f"{d['display_name']}  •  {d['speed_kmh']:.0f} km/h",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=col,
            ).pack(anchor="w", padx=12, pady=4)
            txt = (
                f"Server/Karte: {d.get('level_name') or '–'}\n"
                f"Bus: {d['vehicle_model'] or '–'}  |  Linie: {d['line_name'] or '–'}\n"
                f"{d['current_stop'] or '–'} → {d['next_stop'] or '–'}\n"
                f"Umsatz Session: {d['revenue_session_eur']:.2f} €"
            )
            ctk.CTkLabel(card, text=txt, justify="left").pack(anchor="w", padx=12, pady=4)

    def _end_trip_manual(self):
        ended = self.tracker.force_end()
        if ended and self.api and self.api.token:
            self._upload_trip(ended)
            messagebox.showinfo("Fahrt", "Beendet & hochgeladen.")
        elif ended:
            messagebox.showinfo("Fahrt", "Lokal beendet.")

    def _upload_trip(self, trip):
        if not self.api or not self.api.token:
            return
        try:
            self.api.submit_trip(trip.to_dict(), self._active_spedition_id)
            self.tracker = TripTracker()
        except Exception:
            pass

    def _poll_loop(self):
        if not self._running:
            return
        try:
            snap = self.telemetry.fetch_snapshot()
            self._last_snap = snap
            trip = self.tracker.update(snap)

            if snap.connected:
                tel_text = "The Bus: ✓ verbunden"
                tel_color = "#2ECC71"
                map_name = snap.level_name or "Unbekannt"
            else:
                tel_text = "The Bus: wartet…"
                tel_color = "gray"
                map_name = "–"

            self.lbl_telemetry.configure(text=tel_text, text_color=tel_color)
            self.lbl_game_map.configure(text=f"Karte: {map_name}")

            if snap.connected:
                overspeed = (
                    snap.allowed_speed_kmh > 0
                    and snap.speed_kmh > snap.allowed_speed_kmh + 3
                )
                self.dash_cards["speed_val"].configure(
                    text=f"{snap.speed_kmh:.0f} km/h",
                    text_color="#FF6B6B" if overspeed else "white",
                )
                self.dash_cards["rev_val"].configure(
                    text=f"{self.tracker.session_revenue:.2f} €"
                )
                self.dash_cards["tix_val"].configure(text=str(trip.tickets_sold))
                self.dash_cards["dist_val"].configure(text=f"{trip.distance_km:.2f} km")
                self.dash_info.delete("1.0", "end")
                self.dash_info.insert(
                    "1.0",
                    f"Fahrzeug: {snap.vehicle_model}\n"
                    f"Linie: {snap.line_name or '–'} | Route: {snap.route_name or '–'}\n"
                    f"Karte/Server: {snap.level_name or '–'}\n"
                    f"Haltestelle: {snap.current_stop or '–'} → {snap.next_stop or '–'}\n"
                    f"Belegung: {snap.num_occupied_seats}/{snap.num_seats}\n"
                    f"Fahrt: {'aktiv' if trip.active else 'pausiert'} | "
                    f"Max {trip.max_speed_kmh:.0f} km/h\n"
                    f"Tracker-Server: {self._server_info.label if self._server_info else '–'}\n",
                )

            if (
                not trip.active
                and trip.ended_at
                and trip.started_at
                and not trip.uploaded
            ):
                trip.uploaded = True
                if self.api and self.api.token:
                    self._upload_trip(trip)
                self.tracker = TripTracker()

            self._tick_count += 1
            if self.api and self.api.token and self._tick_count % LIVE_SYNC_EVERY == 0:
                self._sync_live(snap)

            if self._tick_count % (LIVE_SYNC_EVERY * 3) == 0 and self.tabs["live"].winfo_ismapped():
                self._refresh_live()

        except Exception:
            pass
        self.after(POLL_MS, self._poll_loop)

    def _sync_live(self, snap):
        if not self.api or not self.api.token:
            return
        try:
            self.api.update_live(
                {
                    "spedition_id": self._active_spedition_id,
                    "is_online": snap.connected,
                    "vehicle_model": snap.vehicle_model,
                    "line_name": snap.line_name,
                    "level_name": snap.level_name,
                    "current_stop": snap.current_stop,
                    "next_stop": snap.next_stop,
                    "speed_kmh": snap.speed_kmh,
                    "allowed_speed_kmh": snap.allowed_speed_kmh,
                    "latitude": snap.location_y / 100000 if snap.location_y else 0,
                    "longitude": snap.location_x / 100000 if snap.location_x else 0,
                    "revenue_session_eur": self.tracker.session_revenue,
                }
            )
        except Exception:
            pass

    def destroy(self):
        self._running = False
        self.telemetry.close()
        if self.api:
            self.api.close()
        super().destroy()


def run_app():
    app = BusTrackerApp()
    app.mainloop()
