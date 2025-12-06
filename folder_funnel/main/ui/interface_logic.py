#region - Imports

# Standard
import os

# Standard GUI
from tkinter import filedialog

# Third-Party
import nenotk as ntk

# Custom
from . import listbox_logic
from main.utils import help_text

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Status styles


STATUS_STYLES = {
    "idle": {"text": "Idle", "color": "#9e9e9e"},
    "busy": {"text": "Busy", "color": "#d8801f"},
    "running": {"text": "Running", "color": "#2f9e44"},
}


#endregion
#region - Interface Logic


def select_working_dir(app: 'Main', path=None):
    """Select a folder to use as the source folder."""
    if not path:
        path = filedialog.askdirectory()
        if not path:  # Cancelled dialog
            return
        path = os.path.normpath(path)
    if os.path.exists(path):
        app.source_dir_var.set(path)
        app.dir_entry_tooltip.config(text=path)
        app.log(f"\nSelected source folder: {path}\n", mode="system", verbose=1)


def open_folder(app: 'Main', path=None):
    """Open a folder in the file explorer"""
    if os.path.exists(path):
        os.startfile(path)
    else:
        ntk.showinfo("Error", "Folder not found")
        app.log(f"Folder not found: {path}", mode="error", verbose=1)


def log(app: 'Main', message, mode="simple", verbose=1):
    """Add a message to the log with an optional mode prefix.

    Args:
        app: The Main application instance.
        message: The message to log.
        mode: The log mode/type - "info", "system", "warning", "error", or "simple".
        verbose: Verbosity level (1-4):
            1 = Essential info - always displayed (user-facing events)
            2 = Extended info - useful but not required (additional context)
            3 = Detailed info - low-level operations (technical details)
            4 = Debug info - debugging/diagnostic messages
    """
    # Check verbosity level - skip if message level exceeds user's setting
    user_verbosity = app.log_verbosity_var.get() if hasattr(app, 'log_verbosity_var') else 1
    if verbose > user_verbosity:
        return
    prefixes = {
        "info": "[INFO] ",
        "system": "[SYSTEM] ",
        "warning": "[WARNING] ",
        "error": "[ERROR] ",
        "simple": ""
    }
    prefix = prefixes.get(mode, f"[{mode.upper()}] ") if app.log_prefix_filter_var.get() else ""
    # Move leading newlines to the very start of the printout
    leading_newlines = ""
    rest = message
    while rest.startswith("\n"):
        leading_newlines += "\n"
        rest = rest[1:]
    full_message = f"{leading_newlines}{prefix}{rest}"
    if app.messages and app.messages[-1] == full_message:
        return
    app.messages.append(full_message)
    app.text_log.configure(state="normal")
    app.text_log.insert("end", f"{full_message}\n")
    app.text_log.configure(state="disable")
    app.text_log.see("end")


def clear_log(app: 'Main'):
    """Clear the log text area."""
    app.text_log.configure(state="normal")
    app.text_log.delete(1.0, "end")
    app.text_log.configure(state="disable")


def clear_history(app: 'Main'):
    """Clear the history listbox and the underlying history list."""
    app.history_listbox.delete(0, "end")
    history_list = listbox_logic.get_history_list(app)
    history_list.clear()


def toggle_text_wrap(app: 'Main'):
    """Toggle text wrapping in the log text area and show/hide horizontal scrollbar."""
    wrap = app.text_log_wrap_var.get()
    app.text_log.configure(wrap="word" if wrap else "none")
    # Show/hide horizontal scrollbar
    if wrap:
        app.text_log_hscroll.grid_remove()
        app.text_log.configure(xscrollcommand=None)
    else:
        app.text_log_hscroll.config(command=app.text_log.xview)
        app.text_log.configure(xscrollcommand=app.text_log_hscroll.set)
        app.text_log_hscroll.grid(row=3, column=0, sticky="ew")


def toggle_widgets_state(app: 'Main', state="idle"):
    """Toggle the state of UI widgets based on application state."""
    button = app.start_stop_button
    browse = app.browse_button
    dir_entry = app.dir_entry
    file_menu = app.file_menu
    if state == "running":
        button.configure(text="Stop", command=app.stop_folder_watcher, state="normal")
        if browse:
            browse.configure(state="disabled")
        if dir_entry:
            dir_entry.configure(state="disabled")
        if file_menu:
            file_menu.entryconfig("Select Source Path...", state="disabled")
    elif state == "idle":
        button.configure(text="Start", command=app.start_folder_watcher, state="normal")
        if browse:
            browse.configure(state="normal")
        if dir_entry:
            dir_entry.configure(state="normal")
        if file_menu:
            file_menu.entryconfig("Select Source Path...", state="normal")
    elif state == "disabled":
        button.configure(state=state)
        if browse:
            browse.configure(state=state)
        if dir_entry:
            dir_entry.configure(state=state)
        if file_menu:
            file_menu.entryconfig("Select Source Path...", state=state)


def set_status(app: 'Main', state: str, message: str | None = None):
    """Update status label text and color for a given state."""
    normalized = (state or "idle").lower()
    style = STATUS_STYLES.get(normalized, {})
    text = message or style.get("text") or normalized.title()
    app.status_state = normalized
    app.status_label_var.set(text)
    label = getattr(app, "status_label", None)
    if label:
        color = style.get("color") or getattr(app, "status_label_default_fg", None)
        if color:
            label.configure(fg=color)


def reset_status_row(app: 'Main'):
    """Reset the status row."""
    set_status(app, "idle")
    app.foldercount_var.set("Folders: 0")
    app.filecount_var.set("Files: 0")
    app.movecount_var.set("Moved: 0")
    app.dupecount_var.set("Duplicates: 0")
    app.queuecount_var.set("Queue: 0")
    app.queue_progressbar.configure(value=0)


def open_help_window(app: 'Main'):
    """Open the help window with the application help text."""
    window = ntk.tkmarktext.TextWindow(master=app.root, title="Help", text=help_text.ABOUT_FOLDER_FUNNEL, geometry="600x400", icon=app.icon_path)
    window.open_window()


def open_stats_popup(app: 'Main'):
    """Open the stats popup window."""
    def format_hms(seconds):
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    total_move_time = int(app.grand_move_count * app.move_action_time)
    total_dupe_time = int(app.grand_duplicate_count * app.dupe_action_time)
    total_time = total_move_time + total_dupe_time
    ntk.showinfo(
        "Stats",
        f"Total moves: {int(app.grand_move_count)}\n"
        f"Total duplicates: {int(app.grand_duplicate_count)}\n\n"
        "Estimated time saved per action:\n"
        f"Move: {int(app.move_action_time)} seconds\n"
        f"Duplicate: {int(app.dupe_action_time)} seconds\n\n"
        "Total estimated time saved:\n"
        f"Moves: {format_hms(total_move_time)}\n"
        f"Duplicates: {format_hms(total_dupe_time)}\n"
        f"Total: {format_hms(total_time)}"
    )



def update_duplicate_count(app: 'Main'):
    """Update the duplicate count display."""
    app.dupecount_var.set(f"Duplicates: {app.duplicate_count}")


def update_queue_count(app: 'Main'):
    """Update the move queue count display."""
    app.queue_count = len(app.move_queue)
    app.queuecount_var.set(f"Queue: {app.queue_count}")


def get_history_list(app: 'Main'):
    """Get the appropriate history list based on current mode."""
    return listbox_logic.get_history_list(app)
