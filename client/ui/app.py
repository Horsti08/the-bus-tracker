"""The Bus Tracker – Zero-Config Desktop-Client."""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from client.api_client import ApiClient, format_api_error
from client.ui.cards import MenuCard
from client.ui.map_canvas import LiveMapCanvas
from client.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    ACCENT_YELLOW,
    BG_CARD,
    BG_DARK,
    BG_HEADER,
    TEXT,
    TEXT_DIM,
)
from client.auto_auth import ensure_authenticated
from client.bootstrap import initialize_client
from client.config import load_config, save_config
from client.server_connect import CommunityServerUnavailable, ServerInfo
from client.telemetry.client import TelemetryClient, TelemetryConfig
from client.telemetry.tracker import TripTracker
from client.updater import check_for_update, download_and_apply
from shared import APP_VERSION, DEFAULT_TELEMETRY_HOST, DEFAULT_TELEMETRY_PORT

POLL_MS = 400
LIVE_SYNC_EVERY = 5
UI_REFRESH_EVERY = 10
LIVE_AUTO_MS = 2000
AUTO_UPDATE_MS = 30 * 60 * 1000


class BusTrackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"The Bus Tracker v{APP_VERSION}")
        self.geometry("1280x800")
        self.minsize(1000, 680)
        self.configure(fg_color=BG_DARK)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.config_data = load_config()
        self._running = True
        self._tick_count = 0
        self._active_spedition_id = self.config_data.get("active_spedition_id")
        self._last_snap = None
        self._server_info: ServerInfo | None = None
        self._current_tab = "loading"
        self._live_busy = False
        self._live_job: str | None = None
        self._update_job: str | None = None
        self._sped_refresh_job: str | None = None
        self._cached_dash_info = ""
        self._bank_cache: dict | None = None

        self._build_shell()
        self._show_tab("loading")
        threading.Thread(target=self._async_bootstrap, daemon=True).start()

    def _build_shell(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=BG_HEADER)
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            self.topbar,
            text="☰ Hauptmenü",
            width=120,
            fg_color="transparent",
            hover_color=BG_CARD,
            command=lambda: self._show_tab("menu"),
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        ctk.CTkLabel(
            self.topbar,
            text="The Bus Tracker",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=1, padx=8, sticky="w")

        self.lbl_version = ctk.CTkLabel(
            self.topbar,
            text=f"v{APP_VERSION}",
            text_color=ACCENT_GREEN,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_version.grid(row=0, column=2, padx=8, sticky="e")

        self.lbl_server = ctk.CTkLabel(
            self.topbar, text="Server: …", font=ctk.CTkFont(size=12), text_color=TEXT_DIM
        )
        self.lbl_server.grid(row=0, column=3, padx=8, sticky="e")

        self.lbl_game_map = ctk.CTkLabel(
            self.topbar, text="Karte: –", text_color=TEXT_DIM, font=ctk.CTkFont(size=12)
        )
        self.lbl_game_map.grid(row=0, column=4, padx=8, sticky="e")

        self.lbl_telemetry = ctk.CTkLabel(
            self.topbar, text="The Bus: …", font=ctk.CTkFont(size=12)
        )
        self.lbl_telemetry.grid(row=0, column=5, padx=16, sticky="e")

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_DARK)
        self.main.grid(row=1, column=0, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.lbl_user = ctk.CTkLabel(self, text="", text_color=TEXT_DIM)
        self.lbl_status = ctk.CTkLabel(
            self, text="", text_color=TEXT_DIM, font=ctk.CTkFont(size=10)
        )

        self.tabs: dict[str, ctk.CTkFrame] = {}
        for key in (
            "loading",
            "menu",
            "dashboard",
            "spedition",
            "live",
            "ranking",
            "bank",
            "account",
        ):
            f = ctk.CTkFrame(self.main, fg_color=BG_DARK)
            f.grid(row=0, column=0, sticky="nsew")
            self.tabs[key] = f

        self._build_loading_tab()
        self._build_menu_tab()
        self._build_dashboard_tab()
        self._build_spedition_tab()
        self._build_live_tab()
        self._build_ranking_tab()
        self._build_bank_tab()
        self._build_account_tab()
        self._show_tab("loading")

        foot = ctk.CTkFrame(self, height=28, fg_color=BG_HEADER, corner_radius=0)
        foot.grid(row=2, column=0, sticky="ew")
        self.lbl_user.pack(in_=foot, side="left", padx=12)
        self.lbl_status.pack(in_=foot, side="right", padx=12)

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
        self._show_tab("menu")
        self.after(POLL_MS, self._poll_loop)
        self._schedule_auto_update()

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

    def _toast(self, msg: str, color: str = "#AAAAAA"):
        self.lbl_status.configure(text=msg[:120], text_color=color)

    def _run_bg(self, work, on_ok=None, on_err=None):
        def runner():
            try:
                result = work()
                if on_ok:
                    self.after(0, lambda: on_ok(result))
            except Exception as e:
                if on_err:
                    self.after(0, lambda: on_err(e))
                else:
                    self.after(0, lambda: self._toast(format_api_error(e), "#E74C3C"))

        threading.Thread(target=runner, daemon=True).start()

    def _show_tab(self, name: str):
        self._current_tab = name
        for key, frame in self.tabs.items():
            frame.grid_remove()
        self.tabs[name].grid(row=0, column=0, sticky="nsew")
        if name == "live":
            self._schedule_live_auto()
        elif self._live_job:
            try:
                self.after_cancel(self._live_job)
            except Exception:
                pass
            self._live_job = None
        if name == "spedition" and self._active_spedition_id:
            self._refresh_members_async()
            self._schedule_sped_auto()
        elif self._sped_refresh_job:
            try:
                self.after_cancel(self._sped_refresh_job)
            except Exception:
                pass
            self._sped_refresh_job = None
        if name == "ranking" and self._active_spedition_id:
            self._refresh_ranking_async()
        if name == "bank":
            self._refresh_bank_async()

    def _build_loading_tab(self):
        f = self.tabs["loading"]
        ctk.CTkLabel(
            f,
            text="Verbinde mit Community-Server…\n\n"
            "SPEDV-Modell: alle Spieler weltweit über Internet-API\n"
            "(kein WLAN nötig)\n\n"
            "The Bus Telemetrie startet automatisch mit dem Spiel.",
            font=ctk.CTkFont(size=15),
            text_color=TEXT,
            justify="center",
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _build_menu_tab(self):
        f = self.tabs["menu"]
        f.grid_columnconfigure((0, 1, 2), weight=1)
        f.grid_rowconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(
            f,
            text="Hauptmenü",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, columnspan=3, padx=24, pady=(20, 8), sticky="w")

        cards = [
            ("Freie Fahrt", "Telemetrie & Umsatz", ACCENT_GREEN, "dashboard"),
            ("Spedition", "Firma & Fahrer", ACCENT_YELLOW, "spedition"),
            ("Live-Karte", "Berlin / Hamburg", ACCENT_BLUE, "live"),
            ("Ranking", "Bestenliste", ACCENT_PURPLE, "ranking"),
            ("Bankkonto", "Firma & Fahrer", ACCENT_ORANGE, "bank"),
            ("Optionen", f"Version v{APP_VERSION}", "#8899aa", "account"),
        ]
        pos = [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
        for (title, sub, col, tab), (r, c) in zip(cards, pos):
            MenuCard(
                f,
                title=title,
                subtitle=sub,
                accent=col,
                command=lambda t=tab: self._show_tab(t),
            ).grid(row=r, column=c, padx=12, pady=10, sticky="nsew")

        ctk.CTkButton(
            f,
            text="Update suchen",
            fg_color=BG_CARD,
            hover_color="#2a3548",
            command=self._check_update_manual,
        ).grid(row=3, column=2, padx=12, pady=8, sticky="e")

    def _build_dashboard_tab(self):
        f = self.tabs["dashboard"]
        f.grid_columnconfigure((0, 1), weight=1)
        cards = ctk.CTkFrame(f, fg_color="transparent")
        cards.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=16)
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1)
        self.dash_cards = {}
        accents = [ACCENT_GREEN, ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_BLUE]
        for i, (title, key, default) in enumerate(
            [
                ("Geschwindigkeit", "speed_val", "–"),
                ("Umsatz", "rev_val", "0 €"),
                ("Tickets", "tix_val", "0"),
                ("Strecke", "dist_val", "0 km"),
            ]
        ):
            card = ctk.CTkFrame(cards, fg_color=BG_CARD, corner_radius=12)
            card.grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=title, text_color=accents[i]).pack(pady=(12, 0))
            lbl = ctk.CTkLabel(
                card, text=default, font=ctk.CTkFont(size=26, weight="bold"), text_color=TEXT
            )
            lbl.pack(pady=12)
            self.dash_cards[key] = lbl

        route_row = ctk.CTkFrame(f, fg_color="transparent")
        route_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=4)
        route_row.grid_columnconfigure((0, 1), weight=1)

        line_card = ctk.CTkFrame(route_row, fg_color=BG_CARD, corner_radius=12)
        line_card.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(line_card, text="LINIE / ROUTE", text_color=ACCENT_YELLOW).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        self.dash_line = ctk.CTkLabel(
            line_card, text="–", font=ctk.CTkFont(size=28, weight="bold"), text_color=TEXT, wraplength=420
        )
        self.dash_line.pack(anchor="w", padx=14, pady=(4, 12))

        stop_card = ctk.CTkFrame(route_row, fg_color=BG_CARD, corner_radius=12)
        stop_card.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(stop_card, text="HALTESTELLE", text_color=ACCENT_BLUE).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        self.dash_stop = ctk.CTkLabel(
            stop_card, text="–", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT, wraplength=420
        )
        self.dash_stop.pack(anchor="w", padx=14, pady=(4, 0))
        self.dash_next_stop = ctk.CTkLabel(
            stop_card, text="Nächste: –", text_color=TEXT_DIM, wraplength=420
        )
        self.dash_next_stop.pack(anchor="w", padx=14, pady=(2, 12))

        pax_card = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=12)
        pax_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=4)
        ctk.CTkLabel(
            pax_card,
            text="FAHRGÄSTE",
            text_color=ACCENT_PURPLE,
        ).pack(side="left", padx=14, pady=10)
        self.dash_passengers = ctk.CTkLabel(
            pax_card, text="–", font=ctk.CTkFont(size=15), text_color=TEXT
        )
        self.dash_passengers.pack(side="left", padx=8, pady=10)
        ctk.CTkLabel(
            pax_card,
            text="0/28 = belegte Sitze laut Spiel · oft immer 0 in der Beta",
            text_color=TEXT_DIM,
            font=ctk.CTkFont(size=11),
        ).pack(side="right", padx=14)

        info = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=12)
        info.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=16, pady=8)
        f.grid_rowconfigure(3, weight=1)
        self.dash_info = ctk.CTkTextbox(
            info, height=120, fg_color="#0d1118", text_color=TEXT_DIM, font=ctk.CTkFont(size=12)
        )
        self.dash_info.pack(fill="both", expand=True, padx=8, pady=8)
        self.dash_info.insert(
            "1.0",
            "Warte auf The Bus…\n"
            "Route im Spiel wählen (Betriebsplan) – dann erscheinen Linie & Haltestellen.\n",
        )
        ctk.CTkButton(f, text="Fahrt beenden", command=self._end_trip_manual).grid(
            row=4, column=0, padx=16, pady=12, sticky="w"
        )

    def _build_spedition_tab(self):
        f = self.tabs["spedition"]
        f.grid_rowconfigure(3, weight=1)
        f.grid_columnconfigure(0, weight=1)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        ctk.CTkLabel(
            row, text="Spedition", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_YELLOW
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row, text="Aktualisieren", width=100, fg_color=BG_CARD, command=self._refresh_speditions
        ).pack(side="right", padx=8)
        create = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=10)
        create.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        self.sped_name = ctk.CTkEntry(create, placeholder_text="Name", width=180)
        self.sped_name.pack(side="left", padx=8, pady=8)
        ctk.CTkButton(
            create,
            text="Gründen",
            fg_color=ACCENT_YELLOW,
            text_color="#111",
            command=self._create_spedition,
        ).pack(side="left", padx=8)
        self.invite_entry = ctk.CTkEntry(create, placeholder_text="Einladungscode", width=160)
        self.invite_entry.pack(side="right", padx=8, pady=8)
        ctk.CTkButton(create, text="Beitreten", command=self._join_spedition).pack(
            side="right", padx=4
        )
        self.sped_list = ctk.CTkScrollableFrame(f, fg_color=BG_CARD)
        self.sped_list.grid(row=2, column=0, sticky="ew", padx=16, pady=8, ipady=80)
        self.stats_label = ctk.CTkLabel(f, text="", justify="left", text_color=TEXT_DIM)
        self.stats_label.grid(row=3, column=0, sticky="ew", padx=24, pady=4)
        ctk.CTkLabel(
            f, text="Fahrer in deiner Spedition", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT
        ).grid(row=4, column=0, sticky="w", padx=24)
        self.members_text = ctk.CTkTextbox(
            f, height=200, fg_color="#0d1118", text_color=TEXT, font=ctk.CTkFont(size=12)
        )
        self.members_text.grid(row=5, column=0, sticky="nsew", padx=16, pady=8)
        f.grid_rowconfigure(5, weight=1)

    def _build_live_tab(self):
        f = self.tabs["live"]
        f.grid_rowconfigure(0, weight=1)
        f.grid_columnconfigure(0, weight=1)
        self.live_map = LiveMapCanvas(f)
        self.live_map.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

    def _build_ranking_tab(self):
        f = self.tabs["ranking"]
        f.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            f, text="Ranking", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_PURPLE
        ).pack(pady=12, anchor="w", padx=16)
        self.ranking_text = ctk.CTkTextbox(
            f, fg_color="#0d1118", text_color=TEXT, font=ctk.CTkFont(family="Consolas", size=13)
        )
        self.ranking_text.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkButton(f, text="Aktualisieren", command=self._refresh_ranking_async).pack(pady=8)

    def _build_bank_tab(self):
        f = self.tabs["bank"]
        box = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=12)
        box.pack(padx=24, pady=24, fill="x")
        ctk.CTkLabel(
            box, text="Bankkonto", font=ctk.CTkFont(size=20, weight="bold"), text_color=ACCENT_ORANGE
        ).pack(anchor="w", padx=16, pady=(16, 8))
        self.lbl_driver_bank = ctk.CTkLabel(
            box, text="Fahrer: –", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT
        )
        self.lbl_driver_bank.pack(anchor="w", padx=16, pady=8)
        self.lbl_sped_bank = ctk.CTkLabel(
            box, text="Spedition: –", font=ctk.CTkFont(size=18), text_color=TEXT_DIM
        )
        self.lbl_sped_bank.pack(anchor="w", padx=16, pady=(0, 16))
        ctk.CTkLabel(
            box,
            text="Umsatz aus Fahrten wird automatisch gutgeschrieben.\n"
            "15 % der Fahrt-Einnahmen gehen auf das Speditionskonto.",
            text_color=TEXT_DIM,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 16))
        ctk.CTkButton(box, text="Konten aktualisieren", command=self._refresh_bank_async).pack(
            padx=16, pady=(0, 16), anchor="w"
        )

    def _build_account_tab(self):
        f = self.tabs["account"]
        box = ctk.CTkFrame(f, fg_color=BG_CARD, corner_radius=12)
        box.pack(padx=24, pady=24, fill="x")
        ctk.CTkLabel(
            box,
            text=f"Optionen  •  installierte Version v{APP_VERSION}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=12)
        ctk.CTkLabel(
            box,
            text="Auto-Update: Sidebar → Update suchen\n"
            "Neue EXE: build.ps1 → GitHub Release → publish_update.ps1",
            text_color=TEXT_DIM,
            justify="left",
        ).pack(anchor="w", padx=16, pady=4)
        ctk.CTkButton(
            box, text="Update jetzt suchen", command=self._check_update_manual
        ).pack(anchor="w", padx=16, pady=12)
        ctk.CTkLabel(box, text="Konto (optional)", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=8
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

    def _schedule_auto_update(self):
        def check():
            url = self.api.base_url if self.api else None
            upd = check_for_update(url)
            if upd and upd.get("download_url") and getattr(__import__("sys"), "frozen", False):
                self._toast(f"Update {upd['version']} verfügbar – Sidebar", "#5DADE2")
            elif upd:
                self._toast(f"Neue Version {upd.get('version')} auf Server", "#5DADE2")

        self._run_bg(lambda: check())
        if self._update_job:
            try:
                self.after_cancel(self._update_job)
            except Exception:
                pass
        self._update_job = self.after(AUTO_UPDATE_MS, self._schedule_auto_update)

    def _check_update_manual(self):
        url = self.api.base_url if self.api else None
        self._toast("Suche Update…", "gray")

        def work():
            return check_for_update(url)

        def ok(upd):
            if not upd:
                self._toast(f"Aktuell: v{APP_VERSION}", "#2ECC71")
                return
            if upd.get("download_url") and getattr(__import__("sys"), "frozen", False):
                if messagebox.askyesno("Update", f"Version {upd['version']} installieren?"):
                    download_and_apply(upd, self)
            else:
                self._toast(f"Neu: v{upd.get('version')} (kein Download-Link)", "#F39C12")

        self._run_bg(work, on_ok=ok)

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
        name = self.sped_name.get().strip()
        if len(name) < 2:
            self._toast("Name mindestens 2 Zeichen", "#E74C3C")
            return
        self._toast("Erstelle Spedition…", "gray")
        self._run_bg(
            lambda: self.api.create_spedition(name),
            on_ok=lambda _: (self._refresh_speditions(), self._toast("Spedition erstellt!", "#2ECC71")),
        )

    def _join_spedition(self):
        code = self.invite_entry.get().strip()
        if code.startswith("bus-tracker://join/"):
            code = code.split("/")[-1]
        if "join/" in code and "http" in code:
            code = code.rstrip("/").split("/")[-1]
        if len(code) < 4:
            self._toast("Einladungscode eingeben (aus Link)", "#E74C3C")
            return
        self._toast("Beitrete…", "gray")
        self._run_bg(
            lambda: self.api.join_spedition(code),
            on_ok=lambda _: (self._refresh_speditions(), self._toast("Beigetreten!", "#2ECC71")),
        )

    def _refresh_speditions(self):
        if not self.api or not self.api.token:
            return

        def work():
            return self.api.list_speditions()

        def ok(speditions):
            for w in self.sped_list.winfo_children():
                w.destroy()
            if not speditions:
                ctk.CTkLabel(self.sped_list, text="Noch keine Spedition – oben gründen").pack(pady=12)
                return
            for sp in speditions:
                self._add_spedition_row(sp)

        self._run_bg(work, on_ok=ok)

    def _add_spedition_row(self, sp):
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
            self._refresh_members_async()
            self._toast(f"Aktiv: {s['name']}", "#2ECC71")
            if self._current_tab in ("live", "ranking", "bank"):
                self._show_tab(self._current_tab)

        ctk.CTkButton(row, text="Aktiv", width=50, command=select).pack(side="right", padx=4)

        def copy_link(s=sp):
            self.clipboard_clear()
            self.clipboard_append(s["invite_link"])
            self._toast("Link kopiert!", "#2ECC71")

        ctk.CTkButton(row, text="Link", width=44, command=copy_link).pack(side="right", padx=4)
        if sp["is_owner"]:

            def delete(s=sp):
                if messagebox.askyesno("Löschen", f"'{s['name']}' löschen?"):
                    self._run_bg(
                        lambda: self.api.delete_spedition(s["id"]),
                        on_ok=lambda _: self._refresh_speditions(),
                    )

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

    def _schedule_sped_auto(self):
        if self._sped_refresh_job:
            try:
                self.after_cancel(self._sped_refresh_job)
            except Exception:
                pass
        if self._current_tab == "spedition" and self._active_spedition_id:
            self._refresh_members_async()
            self._sped_refresh_job = self.after(4000, self._schedule_sped_auto)

    def _refresh_members_async(self):
        if not self._active_spedition_id or not self.api:
            self._set_members_text("Keine aktive Spedition.\nWähle oben eine Spedition → Aktiv.")
            return

        sid = self._active_spedition_id

        def work():
            return self.api.get_members(sid)

        def ok(members):
            lines = []
            for m in members:
                on = "🟢" if m.get("is_online") else "⚫"
                lines.append(
                    f"{on} #{m.get('rank', '?')} {m['display_name']} ({m.get('role', 'driver')})\n"
                    f"   Konto: {m.get('balance_eur', 0):,.2f} €  |  "
                    f"Umsatz: {m.get('total_revenue_eur', 0):,.2f} €  |  "
                    f"{m.get('trip_count', 0)} Fahrten\n"
                )
            self._set_members_text("\n".join(lines) if lines else "Noch keine Fahrer.")

        self._run_bg(work, on_ok=ok)

    def _set_members_text(self, text: str):
        self.members_text.delete("1.0", "end")
        self.members_text.insert("1.0", text)

    def _refresh_ranking_async(self):
        if not self._active_spedition_id or not self.api:
            self.ranking_text.delete("1.0", "end")
            self.ranking_text.insert("1.0", "Keine aktive Spedition.")
            return
        sid = self._active_spedition_id

        def work():
            return self.api.get_ranking(sid)

        def ok(rows):
            lines = ["Rang  Fahrer              Umsatz      Fahrten  Strecke\n" + "-" * 55 + "\n"]
            for r in rows:
                lines.append(
                    f"{r['rank']:3}  {r['display_name'][:18]:18}  "
                    f"{r['total_revenue_eur']:>9,.2f} €  {r['trip_count']:>5}  "
                    f"{r['total_distance_km']:>7.1f} km\n"
                )
            self.ranking_text.delete("1.0", "end")
            self.ranking_text.insert("1.0", "".join(lines))

        self._run_bg(work, on_ok=ok)

    def _refresh_bank_async(self):
        if not self.api:
            return

        def work():
            driver = self.api.get_my_bank()
            sped = None
            if self._active_spedition_id:
                sped = self.api.get_spedition_bank(self._active_spedition_id)
            return driver, sped

        def ok(data):
            driver, sped = data
            self.lbl_driver_bank.configure(
                text=f"Fahrer ({driver.get('label', '')}): {driver.get('balance_eur', 0):,.2f} €"
            )
            if sped:
                self.lbl_sped_bank.configure(
                    text=f"Spedition ({sped.get('label', '')}): {sped.get('balance_eur', 0):,.2f} €"
                )
            else:
                self.lbl_sped_bank.configure(text="Spedition: keine aktiv gewählt")

        self._run_bg(work, on_ok=ok)

    def _schedule_live_auto(self):
        if self._live_job:
            try:
                self.after_cancel(self._live_job)
            except Exception:
                pass
        self._refresh_live_async()
        self._live_job = self.after(LIVE_AUTO_MS, self._schedule_live_auto)

    def _refresh_live_async(self):
        if self._live_busy or not self._active_spedition_id or not self.api:
            if not self._active_spedition_id and hasattr(self, "live_map"):
                self.live_map.set_drivers([], "Keine Spedition aktiv")
            return
        self._live_busy = True
        sid = self._active_spedition_id

        def work():
            return self.api.get_live_drivers(sid)

        def ok(drivers):
            self._live_busy = False
            self.live_map.set_drivers(drivers)

        def err(e):
            self._live_busy = False
            self.live_map.sub_lbl.configure(text=format_api_error(e)[:80])

        self._run_bg(work, on_ok=ok, on_err=err)

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
            line_hint = snap.line_name or snap.route_name
            self.lbl_game_map.configure(
                text=f"Karte: {map_name}" + (f"  |  {line_hint}" if line_hint else "")
            )

            if snap.connected and self._tick_count % UI_REFRESH_EVERY == 0:
                if self._current_tab == "dashboard":
                    overspeed = (
                        snap.allowed_speed_kmh > 0
                        and snap.speed_kmh > snap.allowed_speed_kmh + 3
                    )
                    self.dash_cards["speed_val"].configure(
                        text=f"{snap.speed_kmh:.0f} km/h",
                        text_color="#FF6B6B" if overspeed else TEXT,
                    )
                    self.dash_cards["rev_val"].configure(
                        text=f"{self.tracker.session_revenue:.2f} €"
                    )
                    self.dash_cards["tix_val"].configure(
                        text=str(max(trip.tickets_sold, snap.tickets_session))
                    )
                    self.dash_cards["dist_val"].configure(text=f"{trip.distance_km:.2f} km")

                    self.dash_line.configure(text=snap.line_display)
                    self.dash_stop.configure(text=snap.stop_display)
                    nxt = snap.next_stop or "–"
                    self.dash_next_stop.configure(text=f"Nächste Haltestelle: {nxt}")
                    seats = (
                        f"Sitzplätze: {snap.num_occupied_seats}/{snap.num_seats}"
                        if snap.num_seats
                        else "Sitzplätze: –"
                    )
                    self.dash_passengers.configure(
                        text=f"{snap.passengers_display}  |  {seats}  |  Tickets Session: {snap.tickets_session}"
                    )

                    info = (
                        f"Fahrzeug: {snap.vehicle_model}\n"
                        f"Karte: {snap.level_name or '–'}\n"
                        f"Status: {'An Haltestelle' if snap.is_at_stop else 'Unterwegs'}"
                        f"{' · Türen offen' if snap.passenger_doors_open else ''}\n"
                        f"Fahrt: {'aktiv' if trip.active else 'pausiert'} | Max {trip.max_speed_kmh:.0f} km/h\n"
                    )
                    if not snap.line_name and not snap.current_stop:
                        info += (
                            "\nTipp: Im Spiel Route/Betriebsplan starten. "
                            "Linie/Haltestelle kommen vom Bordcomputer (UMG/IBIS).\n"
                            "Falls leer: tools\\probe_telemetry.py ausführen und uns die Button-Namen schicken.\n"
                        )
                    if info != self._cached_dash_info:
                        self._cached_dash_info = info
                        self.dash_info.delete("1.0", "end")
                        self.dash_info.insert("1.0", info)

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
                threading.Thread(
                    target=lambda: self._sync_live(snap), daemon=True
                ).start()

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
                    "line_name": snap.line_name or snap.route_name,
                    "level_name": snap.level_name,
                    "current_stop": snap.current_stop,
                    "next_stop": snap.next_stop,
                    "speed_kmh": snap.speed_kmh,
                    "allowed_speed_kmh": snap.allowed_speed_kmh,
                    "pos_x": snap.location_x,
                    "pos_y": snap.location_y,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "revenue_session_eur": self.tracker.session_revenue,
                }
            )
        except Exception:
            pass

    def destroy(self):
        self._running = False
        for job in (self._live_job, self._update_job, self._sped_refresh_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self.telemetry.close()
        if self.api:
            self.api.close()
        super().destroy()


def run_app():
    app = BusTrackerApp()
    app.mainloop()
