"""
Module for handling interface logic operations in Folder-Funnel application.
Contains functions for logging, history clearing, UI element state management, etc.
"""

import listbox_logic


def log(app, message):
    """Add a message to the log if it's not the same as the last one."""
    if app.messages and app.messages[-1] == message:
        return
    app.messages.append(message)
    app.text_log.configure(state="normal")
    app.text_log.insert("end", f"{message}\n")
    app.text_log.configure(state="disable")
    app.text_log.see("end")


def clear_log(app):
    """Clear the log text area."""
    app.text_log.configure(state="normal")
    app.text_log.delete(1.0, "end")
    app.text_log.configure(state="disable")


def clear_history(app):
    """Clear the history listbox and the underlying history list."""
    app.history_listbox.delete(0, "end")
    list = listbox_logic.get_history_list(app)
    list.clear()


def toggle_text_wrap(app):
    """Toggle text wrapping in the log text area."""
    wrap = app.text_log_wrap_var.get()
    app.text_log.configure(wrap="word" if wrap else "none")


def toggle_button_state(app, state="idle"):
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


def toggle_indicator(app, state=None):
    """Toggle the activity indicator (progressbar) state."""
    if state == "start":
        app.running_indicator.configure(mode="indeterminate")
        app.running_indicator.start()
    else:
        app.running_indicator.configure(mode="determinate")
        app.running_indicator.stop()


def open_help_window(app):
    """Open the help window with the application help text."""
    app.help_window.open_window(geometry="800x700", help_text=app.HELP_TEXT)


def update_duplicate_count(app):
    """Update the duplicate count display."""
    app.duplicate_count_var.set(f"Duplicates: {app.duplicate_count}")


def get_history_list(app):
    """Get the appropriate history list based on current mode."""
    return listbox_logic.get_history_list(app)
