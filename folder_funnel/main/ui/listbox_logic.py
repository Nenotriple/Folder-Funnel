#region - Imports


# Standard
import os
from tkinter import messagebox

# Custom
from . import interface

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Listbox Logic


def toggle_history_mode(app: 'Main'):
    """Switch between history display modes and update UI elements."""
    # Get display mode
    display_mode = app.history_mode_var.get()
    # Update the history menubutton text
    app.history_menubutton.config(text=f"History - {display_mode}")
    # Determine which list to use for bindings
    if display_mode == "Duplicate":
        handle_widget_binds(app, app.duplicate_history_items)
    elif display_mode == "Moved":
        handle_widget_binds(app, app.move_history_items)
    elif display_mode == "All":
        handle_widget_binds_all(app)
    refresh_history_listbox(app)


def refresh_history_listbox(app: 'Main'):
    """Clear and repopulate the history listbox based on current display mode."""
    app.history_listbox.delete(0, "end")
    # Get display mode and determine which list to use
    display_mode = app.history_mode_var.get()
    if display_mode == "Duplicate":
        items = app.duplicate_history_items
        # Sort by order (ascending) so newest items are added last, then insert at 0 to reverse
        sorted_items = sorted(items.items(), key=lambda x: x[1].get("order", 0))
        for filename, _ in sorted_items:
            app.history_listbox.insert(0, filename)
    elif display_mode == "Moved":
        items = app.move_history_items
        # Sort by order (ascending) so newest items are added last, then insert at 0 to reverse
        sorted_items = sorted(items.items(), key=lambda x: x[1].get("order", 0) if isinstance(x[1], dict) else 0)
        for filename, _ in sorted_items:
            app.history_listbox.insert(0, filename)
    elif display_mode == "All":
        # Combine both lists with type tracking and sort by chronological order
        # Moved items in black, duplicate items in gray
        all_items = []
        for filename, data in app.move_history_items.items():
            order = data.get("order", 0) if isinstance(data, dict) else 0
            all_items.append((filename, "moved", order))
        for filename, data in app.duplicate_history_items.items():
            order = data.get("order", 0) if isinstance(data, dict) else 0
            all_items.append((filename, "duplicate", order))
        # Sort by order (ascending) so oldest first, then insert at 0 to show newest at top
        all_items.sort(key=lambda x: x[2])
        for filename, item_type, _ in all_items:
            app.history_listbox.insert(0, filename)
            idx = 0
            if item_type == "duplicate":
                app.history_listbox.itemconfig(idx, fg="#888888")  # Light gray for duplicates
            else:
                app.history_listbox.itemconfig(idx, fg="#000000")  # Black for moved


def handle_widget_binds(app: 'Main', history_items):
    """Set appropriate event bindings based on the history item type."""
    if history_items == app.move_history_items:
        app.history_listbox.bind("<Double-Button-1>", lambda e: open_selected_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_file(app))
    elif history_items == app.duplicate_history_items:
        app.history_listbox.bind("<Double-Button-1>", lambda e: open_selected_source_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_duplicate_file(app))


def handle_widget_binds_all(app: 'Main'):
    """Set event bindings for All mode - smart detection of item type."""
    app.history_listbox.bind("<Double-Button-1>", lambda e: open_selected_file_smart(app))
    app.history_listbox.bind("<Delete>", lambda e: delete_selected_file_smart(app))


def update_history_list(app: 'Main', filename, filepath):
    """Update the moved files history list with a new filename and its full path."""
    # Increment order counter and add to the move history items with order
    app.history_order_counter += 1
    app.move_history_items[filename] = {"path": filepath, "order": app.history_order_counter}
    # Remove oldest items if limit is reached (those with lowest order)
    while len(app.move_history_items) > app.max_history_entries:
        # Find the item with the lowest order
        oldest_key = min(app.move_history_items.keys(), key=lambda k: app.move_history_items[k].get("order", 0))
        del app.move_history_items[oldest_key]
    refresh_history_listbox(app)


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
        move_data = app.move_history_items.get(filename)
        if isinstance(move_data, dict):
            return move_data.get("path")
        return move_data  # Fallback for old format


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
            app.log(f"Deleted file: {filename}", mode="info")
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
            app.log(f"Deleted duplicate file: {filename}", mode="info")
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
#region - Smart Functions for All Mode


def get_selected_item_type(app: 'Main'):
    """Determine if the selected item is a moved file or duplicate file.
    Returns 'moved', 'duplicate', or None if no selection."""
    selection = app.history_listbox.curselection()
    if not selection:
        return None
    filename = app.history_listbox.get(selection[0])
    # Check duplicates first (they have priority in display)
    if filename in app.duplicate_history_items:
        return "duplicate"
    elif filename in app.move_history_items:
        return "moved"
    return None


def get_selected_filepath_smart(app: 'Main'):
    """Get the filepath of the selected item, automatically detecting if it's moved or duplicate."""
    selection = app.history_listbox.curselection()
    if not selection:
        return None
    filename = app.history_listbox.get(selection[0])
    item_type = get_selected_item_type(app)
    if item_type == "duplicate":
        # For duplicates, return the duplicate path (the one that was moved/deleted)
        return app.duplicate_history_items.get(filename, {}).get("duplicate")
    elif item_type == "moved":
        move_data = app.move_history_items.get(filename)
        if isinstance(move_data, dict):
            return move_data.get("path")
        return move_data  # Fallback for old format
    return None


def open_selected_file_smart(app: 'Main'):
    """Open the selected file, automatically detecting if it's moved or duplicate."""
    filepath = get_selected_filepath_smart(app)
    if filepath and os.path.exists(filepath):
        os.startfile(filepath)
    else:
        messagebox.showerror("Error", "File not found")


def show_selected_in_explorer_smart(app: 'Main'):
    """Show the selected file in explorer, automatically detecting if it's moved or duplicate."""
    filepath = get_selected_filepath_smart(app)
    if filepath and os.path.exists(filepath):
        os.system(f'explorer /select,"{filepath}"')
    else:
        messagebox.showerror("Error", "File not found")


def delete_selected_file_smart(app: 'Main'):
    """Delete the selected file, automatically detecting if it's moved or duplicate."""
    item_type = get_selected_item_type(app)
    filepath = get_selected_filepath_smart(app)
    if not filepath or not os.path.exists(filepath):
        messagebox.showerror("Error", "File not found")
        return
    filename = os.path.basename(filepath)
    file_type_label = "duplicate " if item_type == "duplicate" else ""
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {file_type_label}file '{filename}'?"):
        try:
            os.remove(filepath)
            # Remove from appropriate history dict
            if item_type == "duplicate":
                selection = app.history_listbox.curselection()
                if selection:
                    listbox_filename = app.history_listbox.get(selection[0])
                    if listbox_filename in app.duplicate_history_items:
                        del app.duplicate_history_items[listbox_filename]
            elif item_type == "moved":
                selection = app.history_listbox.curselection()
                if selection:
                    listbox_filename = app.history_listbox.get(selection[0])
                    if listbox_filename in app.move_history_items:
                        del app.move_history_items[listbox_filename]
            app.history_listbox.delete(app.history_listbox.curselection())
            app.log(f"Deleted {file_type_label}file: {filename}", mode="info")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {str(e)}")


#endregion
