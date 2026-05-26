"""The Bus – Kachel-Buttons für Hauptmenü."""

from __future__ import annotations

import customtkinter as ctk

from client.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_ORANGE,
    ACCENT_PURPLE,
    ACCENT_YELLOW,
    BG_CARD,
    BG_CARD_HOVER,
    TEXT,
    TEXT_DIM,
)


class MenuCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title: str,
        subtitle: str = "",
        accent: str = ACCENT_BLUE,
        command=None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color="#2a3548",
            **kwargs,
        )
        self._command = command
        self._accent = accent

        self.grid_columnconfigure(0, weight=1)
        icon = ctk.CTkLabel(
            self, text="●", font=ctk.CTkFont(size=28), text_color=accent
        )
        icon.grid(row=0, column=0, padx=16, pady=(14, 0), sticky="w")
        ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color=accent
        ).grid(row=1, column=0, padx=16, pady=(4, 0), sticky="w")
        self.sub = ctk.CTkLabel(
            self, text=subtitle, text_color=TEXT_DIM, font=ctk.CTkFont(size=11), anchor="w"
        )
        self.sub.grid(row=2, column=0, padx=16, pady=(2, 14), sticky="w")

        for w in (self, icon):
            w.bind("<Enter>", self._hover_in)
            w.bind("<Leave>", self._hover_out)
            w.bind("<Button-1>", self._click)
        self.sub.bind("<Enter>", self._hover_in)
        self.sub.bind("<Leave>", self._hover_out)
        self.sub.bind("<Button-1>", self._click)

    def set_subtitle(self, text: str):
        self.sub.configure(text=text)

    def _hover_in(self, _e=None):
        self.configure(fg_color=BG_CARD_HOVER)

    def _hover_out(self, _e=None):
        self.configure(fg_color=BG_CARD)

    def _click(self, _e=None):
        if self._command:
            self._command()
