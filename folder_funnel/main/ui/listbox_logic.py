#region - Imports


# Standard
import os

# Third-Party
import nenotk as ntk
from PIL import Image, UnidentifiedImageError

# Custom
from . import interface

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main
    from nenotk.widgets.popup_zoom import PopUpZoom


#endregion
#region - Listbox Logic


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".avif",
    ".heic",
    ".ico",
}


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
    _perform_history_action(app, target="default", action="open")


def open_selected_source_file(app: 'Main'):
    _perform_history_action(app, target="source", action="open")


def open_selected_duplicate_file(app: 'Main'):
    _perform_history_action(app, target="duplicate", action="open")


def show_selected_in_explorer(app: 'Main'):
    _perform_history_action(app, target="default", action="explore")


def show_selected_source_in_explorer(app: 'Main'):
    _perform_history_action(app, target="source", action="explore")


def show_selected_duplicate_in_explorer(app: 'Main'):
    _perform_history_action(app, target="duplicate", action="explore")


def delete_selected_file(app: 'Main'):
    _perform_history_action(app, target="default", action="delete")


def delete_selected_duplicate_file(app: 'Main'):
    _perform_history_action(app, target="duplicate", action="delete")


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
    _perform_history_action(app, target="smart", action="open")


def show_selected_in_explorer_smart(app: 'Main'):
    """Show the selected file in explorer, automatically detecting if it's moved or duplicate."""
    _perform_history_action(app, target="smart", action="explore")


def delete_selected_file_smart(app: 'Main'):
    """Delete the selected file, automatically detecting if it's moved or duplicate."""
    _perform_history_action(app, target="smart", action="delete")


def _resolve_history_path(app: 'Main', target: str):
    """Resolve the selected path based on target type."""
    if target == "duplicate":
        return get_selected_filepath(app, file_type="duplicate")
    if target == "source":
        return get_selected_filepath(app, file_type="source")
    if target == "smart":
        return get_selected_filepath_smart(app)
    return get_selected_filepath(app)


def _selected_filename(app: 'Main'):
    selection = app.history_listbox.curselection()
    if not selection:
        return None
    return app.history_listbox.get(selection[0])


def _missing_message(target: str) -> str:
    if target == "duplicate":
        return "Duplicate file not found"
    if target == "source":
        return "Source file not found"
    return "File not found"


def _remove_history_entry(app: 'Main', filename: str):
    if filename in app.duplicate_history_items:
        del app.duplicate_history_items[filename]
    if filename in app.move_history_items:
        del app.move_history_items[filename]


def _delete_prompt(target: str, item_type: str) -> str:
    if target == "duplicate" or item_type == "duplicate":
        return "Delete duplicate file:"
    return "Delete file:"


def _perform_history_action(app: 'Main', target: str, action: str):
    """Central dispatcher for history actions (open/explore/delete)."""
    filepath = _resolve_history_path(app, target)
    if not filepath or not os.path.exists(filepath):
        ntk.showinfo("Error", _missing_message(target))
        return
    filename = _selected_filename(app)
    item_type = get_selected_item_type(app)
    if action == "open":
        os.startfile(filepath)
        return
    if action == "explore":
        os.system(f'explorer /select,"{filepath}"')
        return
    if action == "delete":
        prompt = _delete_prompt(target, item_type)
        if not ntk.askyesno("Confirm Delete", prompt=prompt, detail=os.path.basename(filepath)):
            return
        try:
            os.remove(filepath)
            if filename:
                _remove_history_entry(app, filename)
                app.history_listbox.delete(app.history_listbox.curselection())
            app.log(f"Deleted file: {os.path.basename(filepath)}", mode="info", verbose=1)
            if item_type == "duplicate":
                ntk.showinfo("Success", f"Duplicate file deleted: {os.path.basename(filepath)}")
        except Exception as e:
            ntk.showinfo("Error", f"Could not delete file: {str(e)}")
        return


def _history_path_for_name(app: 'Main', filename: str):
    """Resolve a full path for a history entry name."""
    if filename in app.duplicate_history_items:
        data = app.duplicate_history_items.get(filename, {})
        return data.get("duplicate") or data.get("source")
    move_data = app.move_history_items.get(filename)
    if isinstance(move_data, dict):
        return move_data.get("path")
    return move_data


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS and os.path.isfile(path)


def _load_preview_image(path: str):
    """Return a safely loaded copy of the image for preview or None on failure."""
    try:
        with Image.open(path) as img:
            return img.copy()
    except (FileNotFoundError, PermissionError, UnidentifiedImageError):
        return None
    except Exception:
        return None


def _is_over_listbox_item(listbox, event) -> bool:
    """Check if the mouse event is actually over a listbox item, not empty space."""
    if listbox.size() == 0:
        return False
    idx = listbox.nearest(event.y)
    if idx < 0:
        return False
    try:
        bbox = listbox.bbox(idx)
        if bbox is None:
            return False
        # bbox returns (x, y, width, height) of the item
        item_top = bbox[1]
        item_bottom = bbox[1] + bbox[3]
        return item_top <= event.y <= item_bottom
    except Exception:
        return False


def handle_history_hover(app: 'Main', event) -> None:
    """Update the PopUpZoom image when hovering image entries in the history listbox.

    PopUpZoom handles show/hide via its internal Motion/Leave bindings.
    We only need to update the image and enable/disable zoom when the hovered item changes.
    """
    history_zoom: 'PopUpZoom' = app.history_zoom
    if not history_zoom:
        return
    # If preview is disabled, ensure zoom stays disabled (only set once)
    if not app.history_image_preview_var.get():
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        return
    # Check if hovering over an actual item, not empty space
    if not _is_over_listbox_item(app.history_listbox, event):
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        app.history_zoom_current_path = ""
        return
    idx = app.history_listbox.nearest(event.y)
    filename = app.history_listbox.get(idx)
    path = _history_path_for_name(app, filename)
    if not path or not _is_image_file(path):
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        app.history_zoom_current_path = ""
        return
    # Only reload image if path changed
    if app.history_zoom_current_path != path:
        image_copy = _load_preview_image(path)
        if not image_copy:
            if history_zoom.zoom_enabled.get():
                history_zoom.zoom_enabled.set(False)
            app.history_zoom_current_path = ""
            app.log(f"Preview unavailable for {os.path.basename(path)}", mode="warning", verbose=3)
            return
        history_zoom.set_image(image_copy)
        app.history_zoom_current_path = path
    # Enable zoom only if not already enabled (avoid redundant sets)
    if not history_zoom.zoom_enabled.get():
        history_zoom.zoom_enabled.set(True)


def handle_history_leave(app: 'Main', event) -> None:
    """Reset hover state when leaving the listbox. PopUpZoom handles hiding internally."""
    app.history_zoom_current_path = ""


def toggle_history_preview(app: 'Main') -> None:
    """Enable or disable hover previews and hide the popup when disabled."""
    enabled = app.history_image_preview_var.get()
    history_zoom: 'PopUpZoom' = app.history_zoom
    if history_zoom:
        history_zoom.zoom_enabled.set(enabled)
        if not enabled:
            history_zoom.hide_popup(None)


#endregion
