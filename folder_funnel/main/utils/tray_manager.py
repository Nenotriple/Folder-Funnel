"""System tray + notifications.

This module contains the tray icon logic (pystray) and desktop notification behavior,
refactored out of `app.py`.

All functions accept the Main application instance (facade pattern).
"""


#region - Imports


from __future__ import annotations

import os
import time
import threading

import tkinter as tk
from tkinter import ttk

import pystray
import nenotk as ntk
from PIL import Image

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Focus / watcher state


def _watcher_running(app: "Main") -> bool:
    """Best-effort check for whether the folder watcher is running."""
    for obs in (getattr(app, "funnel_observer", None), getattr(app, "source_observer", None)):
        if not obs:
            continue
        try:
            is_alive = getattr(obs, "is_alive", None)
            if callable(is_alive):
                if is_alive():
                    return True
            else:
                return True
        except Exception:
            return True
    return False


def _is_app_in_focus(app: "Main") -> bool:
    """Return True if the main window is visible and currently focused."""
    try:
        st = str(app.root.state()).lower()
        if st in ("withdrawn", "iconic"):
            return False
    except Exception:
        pass
    try:
        if not bool(app.root.winfo_viewable()):
            return False
    except Exception:
        # If we can't tell, err on the side of allowing notifications.
        return False
    try:
        # Tk returns a widget when this app has focus on the display.
        return app.root.focus_displayof() is not None
    except Exception:
        return False


#endregion
#region - Close UX


def on_closing(app: "Main") -> None:
    """Handle window close - minimize to tray or exit."""
    if app.minimize_to_tray_var.get():
        # Smooth UX: close button minimizes to tray.
        # Show a one-time tip (optionally suppressible) the first time per session.
        try:
            show_tip = bool(app.minimize_to_tray_show_close_tip_var.get())
        except Exception:
            show_tip = True
        if show_tip and not getattr(app, "_minimize_to_tray_close_tip_shown", False):
            action, dont_show_again = _show_minimize_to_tray_close_tip_dialog(app)
            app._minimize_to_tray_close_tip_shown = True
            if dont_show_again:
                try:
                    app.minimize_to_tray_show_close_tip_var.set(False)
                    app.save_settings()
                except Exception:
                    pass
            if action == "exit":
                app.exit_application()
                return
        minimize_to_tray(app)
        return
    app.exit_application()


def _show_minimize_to_tray_close_tip_dialog(app: "Main") -> tuple[str, bool]:
    """One-time UX tip when closing with minimize-to-tray enabled.
    Returns:
        (action, dont_show_again)
        - action: "minimize" or "exit"
        - dont_show_again: bool
    """
    action = "minimize"
    dont_show_again = False
    win = tk.Toplevel(app.root)
    win.title("Minimize to Tray")
    try:
        win.iconphoto(False, tk.PhotoImage(file=app.icon_path))
    except Exception:
        pass
    win.resizable(False, False)
    win.transient(app.root)
    container = ttk.Frame(win, padding=12)
    container.grid(row=0, column=0, sticky="nsew")
    msg = ("Folder-Funnel will keep running in the system tray when you close the window.\n\nUse File > Exit (or the tray icon menu) to fully quit.")
    ttk.Label(container, text=msg, justify="left", wraplength=420).grid(row=0, column=0, columnspan=2, sticky="w")
    dont_show_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(container, text="Don't show this again", variable=dont_show_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
    buttons = ttk.Frame(container)
    buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))

    def _close_with(choice: str) -> None:
        nonlocal action, dont_show_again
        action = choice
        try:
            dont_show_again = bool(dont_show_var.get())
        except Exception:
            dont_show_again = False
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    minimize_btn = ttk.Button(buttons, text="Minimize", command=lambda: _close_with("minimize"))
    minimize_btn.grid(row=0, column=0, padx=(0, 8))
    exit_btn = ttk.Button(buttons, text="Exit", command=lambda: _close_with("exit"))
    exit_btn.grid(row=0, column=1)

    def _on_x() -> None:
        _close_with("minimize")

    win.protocol("WM_DELETE_WINDOW", _on_x)
    try:
        win.grab_set()
    except Exception:
        pass
    try:
        app.root.update_idletasks()
        ntk.center_window(win, to="screen")
    except Exception:
        pass
    try:
        minimize_btn.focus_set()
    except Exception:
        pass
    app.root.wait_window(win)
    return action, dont_show_again


#endregion
#region - Notifications


def notify(app: "Main", message: str, title: str = "Folder-Funnel") -> None:
    """Send a desktop notification if enabled.
    Uses the tray backend (pystray) for notifications. If the tray icon isn't
    running yet, it will be started automatically.
    """
    try:
        if not bool(app.notifications_enabled_var.get()):
            return
    except Exception:
        return
    # Temporarily suppress notifications while the app is in focus.
    if _is_app_in_focus(app):
        return
    now_ms = time.time() * 1000.0
    # Simple throttle to avoid notification spam during rapid batches.
    if now_ms - float(getattr(app, "_last_notification_ms", 0.0) or 0.0) < 1500.0:
        return
    app._last_notification_ms = now_ms

    def _send() -> None:
        icon = getattr(app, "tray_icon", None)
        if icon is None:
            return
        try:
            icon.notify(str(message), str(title))
        except Exception:
            return

    # Ensure tray icon exists; notifications are independent of minimize-to-tray.
    if getattr(app, "tray_icon", None) is None:
        try:
            start_tray_icon(app)
        except Exception:
            return
        # Give the icon thread a moment to initialize before notifying.
        try:
            app.root.after(500, _send)
        except Exception:
            _send()
        return
    _send()


#endregion
#region - Tray icon


def minimize_to_tray(app: "Main") -> None:
    """Minimize the application to the system tray."""
    app.log("Minimized to system tray", mode="system", verbose=2)
    app.root.withdraw()
    start_tray_icon(app)


def reveal_from_tray(app: "Main") -> None:
    """Restore the application window from the system tray."""
    app.root.deiconify()
    app.root.lift()
    app.root.focus_force()
    app.log("Restored from system tray", mode="system", verbose=2)


def start_tray_icon(app: "Main") -> None:
    """Start the system tray icon."""
    # Guard: don't spawn multiple tray icons/threads.
    if getattr(app, "tray_icon", None) is not None:
        return

    def _toggle_start_stop() -> None:
        if _watcher_running(app):
            app.stop_folder_watcher()
        else:
            app.start_folder_watcher(auto_start=False)

    menu = pystray.Menu(
        pystray.MenuItem("Show Folder-Funnel", lambda: app.root.after(0, lambda: reveal_from_tray(app)), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: str(getattr(app, "_tray_status_text", "")) or "", None, enabled=False),
        pystray.MenuItem(lambda item: "Stop Folder-Funnel" if _watcher_running(app) else "Start Folder-Funnel", lambda: app.root.after(0, _toggle_start_stop)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Process Move Queue", lambda: app.root.after(0, app.process_move_queue), enabled=lambda item: bool(getattr(app, "move_queue", []))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open: Source", lambda: app.root.after(0, lambda: app.open_folder(app.source_dir_var.get())), enabled=lambda item: bool(app.source_dir_var.get()) and os.path.exists(app.source_dir_var.get())),
        pystray.MenuItem("Open: Funnel", lambda: app.root.after(0, lambda: app.open_folder(app.funnel_dir)), enabled=lambda item: bool(getattr(app, "funnel_dir", "")) and os.path.exists(getattr(app, "funnel_dir", ""))),
        pystray.MenuItem("Open: Duplicates", lambda: app.root.after(0, lambda: app.open_folder(app.duplicate_storage_path)), enabled=lambda item: bool(getattr(app, "duplicate_storage_path", "")) and os.path.exists(getattr(app, "duplicate_storage_path", ""))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit Folder-Funnel", lambda: app.root.after(0, lambda: _tray_exit(app)))
    )

    # Load icon image
    if os.path.exists(app.icon_path):
        # Avoid holding an open file handle on Windows.
        img = Image.open(app.icon_path)
        try:
            icon_image = img.copy()
        finally:
            try:
                img.close()
            except Exception:
                pass
    else:
        icon_image = Image.new("RGB", (64, 64), color="blue")
    app.tray_icon = pystray.Icon("Folder-Funnel", icon_image, "Folder-Funnel", menu)
    app.tray_thread = threading.Thread(target=app.tray_icon.run, daemon=True)
    app.tray_thread.start()


def stop_tray_icon(app: "Main") -> None:
    """Stop and remove the system tray icon."""
    icon = getattr(app, "tray_icon", None)
    thread = getattr(app, "tray_thread", None)
    if icon:
        try:
            icon.stop()
        except Exception:
            pass
    # Best-effort join to reduce "ghost" tray icons on Windows.
    if thread and getattr(thread, "is_alive", lambda: False)():
        try:
            thread.join(timeout=1.0)
        except Exception:
            pass
    app.tray_icon = None
    app.tray_thread = None


def _tray_exit(app: "Main") -> None:
    """Exit from tray - restore window first then exit."""
    stop_tray_icon(app)
    app.root.deiconify()
    app.exit_application()


#endregion
