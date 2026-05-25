"""Einstiegspunkt – Auto-Update, Zero-Config, dann GUI."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_update_check():
    from client.updater import check_for_update, download_and_apply

    update = check_for_update()
    if not update:
        return
    if getattr(sys, "frozen", False) and update.get("download_url"):
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        if messagebox.askyesno(
            "Update verfügbar",
            f"Version {update.get('version')} ist verfügbar.\nJetzt herunterladen und installieren?",
        ):
            download_and_apply(update, root)
        root.destroy()
    elif update:
        print(f"Update verfügbar: {update.get('version')} – bitte neu bauen/herunterladen.")


def main():
    _run_update_check()
    from client.ui.app import run_app

    run_app()


if __name__ == "__main__":
    main()
