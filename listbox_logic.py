#region - Imports


# Standard
import os
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
    app.history_listbox.delete(0, "end")
    # Get display mode
    display_mode = app.history_mode_var.get()
    # Update the history menubutton text
    app.history_menubutton.config(text=f"History - {display_mode}")
    # Determine which list to use for bindings
    if display_mode == "Duplicate":
        handle_widget_binds(app, app.duplicate_history_items)
        items = app.duplicate_history_items
    elif display_mode == "Moved":
        handle_widget_binds(app, app.move_history_items)
        items = app.move_history_items
    else:
        items = {}
    # Populate the listbox
    for filename in items:
        app.history_listbox.insert(0, filename)


def handle_widget_binds(app: 'Main', history_items):
    """Set appropriate event bindings based on the history item type."""
    if history_items == app.move_history_items:
        app.history_listbox.bind("<Double-Button-1>", lambda e: open_selected_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_file(app))
    elif history_items == app.duplicate_history_items:
        app.history_listbox.bind("<Double-Button-1>", lambda e: open_selected_source_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_duplicate_file(app))


def update_history_list(app: 'Main', filename, filepath):
    """Update the moved files history list with a new filename and its full path."""
    # Always add to the move history items
    app.move_history_items[filename] = filepath
    # Remove oldest items if limit is reached
    while len(app.move_history_items) > app.max_history_entries:
        oldest_key = next(iter(app.move_history_items))
        del app.move_history_items[oldest_key]
    # Update listbox only if we're viewing moved files or all files
    display_mode = app.history_mode_var.get()
    if display_mode == "Moved":
        # Clear and repopulate the list widget based on current mode
        toggle_history_mode(app)


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
    # Check if this filename exists in the duplicates dictionary
    if filename in app.duplicate_history_items:
        # For duplicates, return either the source or duplicate path based on file_type
        if file_type == "source":
            return app.duplicate_history_items.get(filename, {}).get("source")
        else:  # duplicate
            return app.duplicate_history_items.get(filename, {}).get("duplicate")
    else:
        # For moved files, return the path from move_history_items
        return app.move_history_items.get(filename)


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
            history_dict = get_history_list(app)
            del history_dict[filename]
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
            history_dict = get_history_list(app)
            del history_dict[filename]
            app.history_listbox.delete(app.history_listbox.curselection())
            app.log(f"Deleted duplicate file: {filename}")
            messagebox.showinfo("Success", f"Duplicate file deleted: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {str(e)}")


def get_history_list(app: 'Main'):
    """Return the appropriate history dict based on selected display mode."""
    display_mode = app.history_mode_var.get()
    if display_mode == "Moved":
        return app.move_history_items
    elif display_mode == "Duplicate":
        return app.duplicate_history_items
    return {}


#endregion
