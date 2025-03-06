#region - Imports

# Standard
import os

# Standard GUI
from tkinter import filedialog, messagebox

# Custom
import listbox_logic
from help_text import HELP_TEXT

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


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
        app.working_dir_var.set(path)
        app.dir_entry_tooltip.config(text=path)
        app.log(f"\nSelected folder: {path}\n")
        app.count_folders_and_files()


def open_folder(app: 'Main', path=None):
    """Open a folder in the file explorer; if no path is provided, use the working directory."""
    if not path:
        path = app.working_dir_var.get()
    if os.path.exists(path):
        os.startfile(path)
    else:
        messagebox.showerror("Error", "Folder not found")


def log(app: 'Main', message):
    """Add a message to the log if it's not the same as the last one."""
    if app.messages and app.messages[-1] == message:
        return
    app.messages.append(message)
    app.text_log.configure(state="normal")
    app.text_log.insert("end", f"{message}\n")
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
    """Toggle text wrapping in the log text area."""
    wrap = app.text_log_wrap_var.get()
    app.text_log.configure(wrap="word" if wrap else "none")


def toggle_button_state(app: 'Main', state="idle"):
    """Toggle the state of start and stop buttons based on application state."""
    start = app.start_button
    stop = app.stop_button
    if state == "running":
        start.configure(state="disabled")
        stop.configure(state="normal")
    elif state == "idle":
        start.configure(state="normal")
        stop.configure(state="disabled")
    elif state == "disabled":
        start.configure(state=state)
        stop.configure(state=state)


def toggle_indicator(app: 'Main', state=None):
    """Toggle the activity indicator (progressbar) state."""
    if state == "start":
        app.running_indicator.configure(mode="indeterminate")
        app.running_indicator.start()
    else:
        app.running_indicator.configure(mode="determinate")
        app.running_indicator.stop()


def open_help_window(app: 'Main'):
    """Open the help window with the application help text."""
    app.help_window.open_window(geometry="800x700", help_text=HELP_TEXT)


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
