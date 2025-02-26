#region - Imports


# Standard
import os
import tkinter as tk
from tkinter import messagebox

# Custom
import interface

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Listbox Logic


def toggle_history_mode(app: 'Main'):
    list = get_history_list(app)
    app.history_listbox.delete(0, "end")
    for filename in list:
        app.history_listbox.insert(0, filename)


def update_history_list(app: 'Main', filename, filepath):
    """Update the history list with a new filename and its full path."""
    list = get_history_list(app)
    # Add new item to dictionary
    list[filename] = filepath
    # Remove oldest items if limit is reached
    while len(list) > app.max_history_entries:
        oldest_key = next(iter(list))
        del list[oldest_key]
    # Clear and repopulate the list widget
    app.history_listbox.delete(0, "end")
    for filename in list:
        # Insert at top to show newest first
        app.history_listbox.insert(0, filename)


def show_history_context_menu(app: 'Main', event):
    clicked_index = app.history_listbox.nearest(event.y)
    if clicked_index >= 0:
        app.history_listbox.selection_clear(0, "end")
        app.history_listbox.selection_set(clicked_index)
        app.history_listbox.activate(clicked_index)
        interface.create_history_context_menu(app)
        app.history_menu.post(event.x_root, event.y_root)


def get_selected_filepath(app: 'Main', file_type="source"):
    """
    Get the filepath of the selected item in the history listbox.

    Args:
        app: The FolderFunnelApp instance
        file_type: Either "source" or "duplicate" to indicate which file to return for duplicate entries
    """
    selection = app.history_listbox.curselection()
    if not selection:
        return None
    filename = app.history_listbox.get(selection[0])
    list = get_history_list(app)

    if app.history_mode_var.get() == "Duplicate":
        # For duplicates, return either the source or duplicate path based on file_type
        if file_type == "source":
            return list.get(filename, {}).get("source")
        else:  # duplicate
            return list.get(filename, {}).get("duplicate")
    else:
        # For moved files, return the full path as before
        return list.get(filename)


def open_selected_file(app: 'Main'):
    filepath = get_selected_filepath(app)
    if filepath and os.path.exists(filepath):
        os.startfile(filepath)
    else:
        messagebox.showerror("Error", "File not found")


def open_selected_source_file(app: 'Main'):
    filepath = get_selected_filepath(app, file_type="source")
    if filepath and os.path.exists(filepath):
        os.startfile(filepath)
    else:
        messagebox.showerror("Error", "Source file not found")


def open_selected_duplicate_file(app: 'Main'):
    filepath = get_selected_filepath(app, file_type="duplicate")
    if filepath and os.path.exists(filepath):
        os.startfile(filepath)
    else:
        messagebox.showerror("Error", "Duplicate file not found")


def show_selected_in_explorer(app: 'Main'):
    filepath = get_selected_filepath(app)
    if filepath and os.path.exists(filepath):
        os.system(f'explorer /select,"{filepath}"')
    else:
        messagebox.showerror("Error", "File not found")


def show_selected_source_in_explorer(app: 'Main'):
    filepath = get_selected_filepath(app, file_type="source")
    if filepath and os.path.exists(filepath):
        os.system(f'explorer /select,"{filepath}"')
    else:
        messagebox.showerror("Error", "Source file not found")


def show_selected_duplicate_in_explorer(app: 'Main'):
    filepath = get_selected_filepath(app, file_type="duplicate")
    if filepath and os.path.exists(filepath):
        os.system(f'explorer /select,"{filepath}"')
    else:
        messagebox.showerror("Error", "Duplicate file not found")


def delete_selected_file(app: 'Main'):
    filepath = get_selected_filepath(app)
    if not filepath or not os.path.exists(filepath):
        messagebox.showerror("Error", "File not found")
        return
    filename = os.path.basename(filepath)
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
        try:
            os.remove(filepath)
            list = get_history_list(app)
            del list[filename]
            app.history_listbox.delete(app.history_listbox.curselection())
            app.log(f"Deleted file: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {str(e)}")


def delete_selected_duplicate_file(app: 'Main'):
    filepath = get_selected_filepath(app, file_type="duplicate")
    if not filepath or not os.path.exists(filepath):
        messagebox.showerror("Error", "Duplicate file not found")
        return
    filename = os.path.basename(filepath)
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete duplicate file '{filename}'?"):
        try:
            os.remove(filepath)
            # Only remove from history if we actually want to track deleted duplicates
            # For now, we'll keep it in history but could add a flag to remove it
            app.log(f"Deleted duplicate file: {filename}")
            messagebox.showinfo("Success", f"Duplicate file deleted: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {str(e)}")


def get_history_list(app: 'Main'):
    """Return the current history list based on selected display mode"""
    display_mode = app.history_mode_var.get()
    if display_mode == "Moved":
        return app.move_history_items
    elif display_mode == "Duplicate":
        return app.duplicate_history_items
    return {}


#endregion
