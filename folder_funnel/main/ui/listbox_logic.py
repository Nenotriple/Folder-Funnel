#region - Imports


# Standard
import io
import os
import re
import subprocess
import threading

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


VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".webm",
    ".flv",
    ".mpeg",
    ".mpg",
}


def toggle_history_mode(app: 'Main'):
    """Switch between history display modes and update UI elements."""
    # Get display mode
    display_mode = app.history_mode_var.get()
    # Update the history menubutton text
    app.history_menubutton.config(text=f"History - {display_mode}")
    # Bind actions based on the active mode (matches previous UX expectations)
    if display_mode == "Duplicate":
        handle_widget_binds(app, "duplicate")
    elif display_mode == "Moved":
        handle_widget_binds(app, "moved")
    else:
        handle_widget_binds_all(app)
    refresh_history_listbox(app)


def refresh_history_listbox(app: 'Main'):
    """Clear and repopulate the history Treeview based on current display mode."""
    tree = app.history_listbox
    if not tree:
        return
    # Clear
    for child in tree.get_children(""):
        tree.delete(child)

    from main.utils import history_manager

    mode = app.history_mode_var.get()
    entries = getattr(app, "history_entries", {})

    entry_ids = history_manager.filtered_ids(app, mode)
    sort_column = getattr(app, "history_sort_column", None)
    if sort_column:
        entry_ids = _sorted_history_ids(app, entry_ids, sort_column, getattr(app, "history_sort_desc", False))

    for entry_id in entry_ids:
        entry = entries.get(entry_id)
        if not entry:
            continue
        kind = entry.get("kind")
        ts = entry.get("ts", 0.0) or 0.0
        values = (
            history_manager._format_time(ts),
            "Duplicate" if kind == "duplicate" else "Moved",
            entry.get("name", ""),
            entry.get("rel", ""),
            entry.get("action", ""),
        )
        tree.insert("", "end", iid=str(entry_id), values=values)


def handle_widget_binds(app: 'Main', mode: str):
    """Set event bindings based on active History mode."""
    if mode == "moved":
        app.history_listbox.bind("<Double-Button-1>", lambda e: _on_history_row_double_click(app, e, action="open_moved"))
        app.history_listbox.bind("<Return>", lambda e: open_selected_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_file(app))
        return
    if mode == "duplicate":
        app.history_listbox.bind("<Double-Button-1>", lambda e: _on_history_row_double_click(app, e, action="open_duplicate_source"))
        app.history_listbox.bind("<Return>", lambda e: open_selected_source_file(app))
        app.history_listbox.bind("<Delete>", lambda e: delete_selected_duplicate_file(app))
        return
    handle_widget_binds_all(app)


def handle_widget_binds_all(app: 'Main'):
    """Set event bindings for All mode - smart detection of item type."""
    app.history_listbox.bind("<Double-Button-1>", lambda e: _on_history_row_double_click(app, e, action="open_smart"))
    app.history_listbox.bind("<Return>", lambda e: open_selected_file_smart(app))
    app.history_listbox.bind("<Delete>", lambda e: delete_selected_file_smart(app))


def _on_history_row_double_click(app: 'Main', event, action: str) -> None:
    """Handle double-clicks on the history Treeview.

    Prevents header double-clicks from triggering file actions.
    """
    tree = getattr(app, "history_listbox", None)
    if tree is not None:
        try:
            region = tree.identify_region(event.x, event.y)
        except Exception:
            region = ""
        if region == "heading":
            return

    if action == "open_moved":
        open_selected_file(app)
        return
    if action == "open_duplicate_source":
        open_selected_source_file(app)
        return
    # Default: "open_smart"
    open_selected_file_smart(app)


def update_history_list(app: 'Main', filename, filepath):
    """Legacy wrapper used by move_queue; now records a rich moved entry."""
    try:
        rel = os.path.relpath(filepath, app.source_dir_var.get())
    except Exception:
        rel = filename
    if hasattr(app, "add_history_moved"):
        app.add_history_moved(dest_path=filepath, rel_path=rel, action="Moved")
    else:
        refresh_history_listbox(app)


def show_history_context_menu(app: 'Main', event):
    tree = app.history_listbox
    if not tree:
        return
    # If right-clicking a header, show header menu (column toggles)
    try:
        region = tree.identify_region(event.x, event.y)
    except Exception:
        region = ""
    if region == "heading":
        try:
            interface.create_history_header_context_menu(app)
        except Exception:
            pass
        if getattr(app, "history_header_menu", None):
            app.history_header_menu.post(event.x_root, event.y_root)
        return

    row_id = tree.identify_row(event.y)
    if not row_id:
        return
    tree.selection_set(row_id)
    tree.focus(row_id)
    entry = None
    try:
        from main.utils import history_manager
        entry = history_manager.safe_get(app, str(row_id))
    except Exception:
        entry = None
    interface.create_history_context_menu(app, entry=entry)
    app.history_menu.post(event.x_root, event.y_root)


def _selected_entry_id(app: 'Main') -> str | None:
    tree = app.history_listbox
    if not tree:
        return None
    selection = tree.selection()
    if not selection:
        return None
    return str(selection[0])


def get_selected_filepath(app: 'Main', file_type="source"):
    """
    Get the filepath of the selected item in the history listbox.

    Args:
        app: The FolderFunnelApp instance
        file_type: Either "source" or "duplicate" to indicate which file to return for duplicate entries
    """
    from main.utils import history_manager

    entry_id = _selected_entry_id(app)
    if not entry_id:
        return None
    entry = history_manager.safe_get(app, entry_id) or {}
    kind = entry.get("kind")
    if kind == "duplicate":
        if file_type == "source":
            return entry.get("source_path")
        return entry.get("duplicate_path")
    return entry.get("primary_path")


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
    """(Legacy) History storage is now in app.history_entries."""
    return getattr(app, "history_entries", {})


#endregion
#region - Smart Functions


def get_selected_item_type(app: 'Main'):
    """Determine if the selected item is a moved file or duplicate file.
    Returns 'moved', 'duplicate', or None if no selection."""
    from main.utils import history_manager

    entry_id = _selected_entry_id(app)
    if not entry_id:
        return None
    entry = history_manager.safe_get(app, entry_id) or {}
    return entry.get("kind")


def get_selected_filepath_smart(app: 'Main'):
    item_type = get_selected_item_type(app)
    if item_type == "duplicate":
        # In All-mode, treat the duplicate file as the primary file-management target.
        return get_selected_filepath(app, file_type="duplicate")
    return get_selected_filepath(app)


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
    from main.utils import history_manager

    entry_id = _selected_entry_id(app)
    if not entry_id:
        return None
    entry = history_manager.safe_get(app, entry_id) or {}
    return entry.get("name")


def _missing_message(target: str) -> str:
    if target == "duplicate":
        return "Duplicate file not found"
    if target == "source":
        return "Source file not found"
    return "File not found"


def _remove_history_entry(app: 'Main', filename: str):
    entry_id = _selected_entry_id(app)
    if entry_id and hasattr(app, "remove_history_entry"):
        app.remove_history_entry(entry_id)


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
        try:
            subprocess.Popen(
                ["explorer", "/select,", filepath],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            # Fallback to os.startfile on the containing folder
            try:
                os.startfile(os.path.dirname(filepath))
            except Exception:
                pass
        return
    if action == "delete":
        prompt = _delete_prompt(target, item_type)
        if not ntk.askyesno("Confirm Delete", prompt=prompt, detail=os.path.basename(filepath)):
            return
        try:
            os.remove(filepath)
            if filename:
                _remove_history_entry(app, filename)
                try:
                    sel = _selected_entry_id(app)
                    if sel:
                        app.history_listbox.delete(sel)
                except Exception:
                    pass
            app.log(f"Deleted file: {os.path.basename(filepath)}", mode="info", verbose=1)
            if item_type == "duplicate":
                ntk.showinfo("Success", f"Duplicate file deleted: {os.path.basename(filepath)}")
        except Exception as e:
            ntk.showinfo("Error", f"Could not delete file: {str(e)}")
        return


def remove_selected_history_entry(app: 'Main') -> None:
    entry_id = _selected_entry_id(app)
    if not entry_id:
        return
    if hasattr(app, "remove_history_entry"):
        app.remove_history_entry(entry_id)


def copy_selected_path(app: 'Main', target: str = "smart") -> None:
    from main.utils import history_manager

    path = None
    if target == "duplicate":
        path = get_selected_filepath(app, file_type="duplicate")
    elif target == "source":
        path = get_selected_filepath(app, file_type="source")
    elif target == "default":
        path = get_selected_filepath(app)
    else:
        path = get_selected_filepath_smart(app)

    if not path:
        return
    history_manager.copy_to_clipboard(app, path)


#region - Treeview Columns + Sorting


def apply_history_column_visibility(app: 'Main') -> None:
    tree = getattr(app, "history_listbox", None)
    if not tree:
        return
    # Enforce Name column always visible
    try:
        app.history_column_visible_vars["name"].set(True)
    except Exception:
        pass
    columns = list(getattr(app, "history_columns", ("time", "type", "name", "rel", "action")))
    visible_vars = getattr(app, "history_column_visible_vars", {})
    displaycolumns = [c for c in columns if bool(getattr(visible_vars.get(c), "get", lambda: True)())]
    if "name" not in displaycolumns:
        displaycolumns.append("name")
    tree["displaycolumns"] = displaycolumns

    # If the sorted column is now hidden, clear sorting
    sort_col = getattr(app, "history_sort_column", None)
    if sort_col and sort_col not in displaycolumns:
        app.history_sort_column = None
        app.history_sort_desc = False
    _update_history_heading_arrows(app)


def toggle_history_column(app: 'Main', column: str) -> None:
    if column == "name":
        # Cannot disable
        try:
            app.history_column_visible_vars["name"].set(True)
        except Exception:
            pass
        apply_history_column_visibility(app)
        return
    # Important: tk.Menu checkbuttons toggle their variable automatically.
    # We only need to apply visibility after the variable changes.
    try:
        if getattr(app, "history_column_visible_vars", {}).get(column) is None:
            return
    except Exception:
        return
    apply_history_column_visibility(app)


def sort_history_by_column(app: 'Main', column: str) -> None:
    current = getattr(app, "history_sort_column", None)
    if current == column:
        app.history_sort_desc = not bool(getattr(app, "history_sort_desc", False))
    else:
        app.history_sort_column = column
        app.history_sort_desc = False  # ascending first
    _update_history_heading_arrows(app)
    refresh_history_listbox(app)


def _update_history_heading_arrows(app: 'Main') -> None:
    tree = getattr(app, "history_listbox", None)
    if not tree:
        return
    labels = getattr(app, "history_column_labels", {})
    sort_col = getattr(app, "history_sort_column", None)
    desc = bool(getattr(app, "history_sort_desc", False))
    arrow = " ▼" if desc else " ▲"
    for col in getattr(app, "history_columns", ("time", "type", "name", "rel", "action")):
        text = labels.get(col, col.title())
        if sort_col == col:
            text = text + arrow
        tree.heading(col, text=text, command=lambda c=col: app.sort_history_by_column(c))


def _natural_key(value) -> list:
    """Natural (numeric-aware) sort key: 1,2,10 instead of 1,10,2."""
    if value is None:
        value = ""
    s = str(value)
    parts = re.split(r"(\d+)", s)
    key = []
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            try:
                key.append(int(p))
            except Exception:
                key.append(p)
        else:
            key.append(p.casefold())
    return key


def _sort_key_for_entry(entry: dict, column: str):
    kind = entry.get("kind")
    if column == "time":
        # Prefer numeric timestamp for correct ordering
        return float(entry.get("ts", 0.0) or 0.0)
    if column == "type":
        # Keep stable, predictable ordering
        return 0 if kind == "moved" else 1
    if column == "name":
        return _natural_key(entry.get("name", ""))
    if column == "rel":
        return _natural_key(entry.get("rel", ""))
    if column == "action":
        return _natural_key(entry.get("action", ""))
    return _natural_key(entry.get(column, ""))


def _sorted_history_ids(app: 'Main', entry_ids: list, column: str, desc: bool) -> list:
    entries = getattr(app, "history_entries", {})

    def keyfunc(entry_id):
        entry = entries.get(entry_id) or {}
        return (
            _sort_key_for_entry(entry, column),
            # Tie-breaker: timestamp
            float(entry.get("ts", 0.0) or 0.0),
        )

    try:
        return sorted(entry_ids, key=keyfunc, reverse=bool(desc))
    except Exception:
        return entry_ids


#endregion


#endregion
#region - Hover Preview


def _history_path_for_hover(app: 'Main', entry_id: str):
    """Resolve a full path for a history entry for hover previews."""
    from main.utils import history_manager

    entry = history_manager.safe_get(app, entry_id) or {}
    if entry.get("kind") == "duplicate":
        return entry.get("duplicate_path") or entry.get("source_path")
    return entry.get("primary_path")


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS and os.path.isfile(path)


def _is_video_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in VIDEO_EXTENSIONS and os.path.isfile(path)


def _load_preview_image(path: str):
    """Return a safely loaded copy of the image for preview or None on failure."""
    try:
        with Image.open(path) as img:
            return img.copy()
    except (FileNotFoundError, PermissionError, UnidentifiedImageError):
        return None
    except Exception:
        return None


def _ensure_video_thumb_async(app: 'Main', video_path: str) -> None:
    """Generate a video thumbnail in a background thread, then update PopUpZoom if still hovered."""
    # Deduplicate work per-path
    jobs = getattr(app, "_video_thumb_jobs", None)
    if jobs is None:
        jobs = {}
        app._video_thumb_jobs = jobs
    if jobs.get(video_path):
        return
    jobs[video_path] = True

    def _worker() -> None:
        jpeg_bytes = None
        try:
            from main.utils import video_thumbnail

            jpeg_bytes = video_thumbnail.get_video_thumbnail_jpeg_bytes(app, video_path)
        except Exception:
            jpeg_bytes = None

        def _on_main() -> None:
            try:
                jobs.pop(video_path, None)
            except Exception:
                pass

            history_zoom: 'PopUpZoom' = getattr(app, "history_zoom", None)
            if not history_zoom or not getattr(app, "history_image_preview_var", None) or not app.history_image_preview_var.get():
                return

            # Only update if the user is still hovering this path
            if getattr(app, "history_zoom_current_path", "") != video_path:
                return

            if not jpeg_bytes:
                if history_zoom.zoom_enabled.get():
                    history_zoom.zoom_enabled.set(False)
                return

            image_copy = None
            try:
                with Image.open(io.BytesIO(jpeg_bytes)) as img:
                    image_copy = img.copy()
            except Exception:
                image_copy = None
            if not image_copy:
                if history_zoom.zoom_enabled.get():
                    history_zoom.zoom_enabled.set(False)
                return
            history_zoom.set_image(image_copy)
            if not history_zoom.zoom_enabled.get():
                history_zoom.zoom_enabled.set(True)

        try:
            app.root.after(0, _on_main)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _tree_row_under_cursor(tree, event) -> str | None:
    try:
        row_id = tree.identify_row(event.y)
        return str(row_id) if row_id else None
    except Exception:
        return None


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
    tree = app.history_listbox
    if not tree:
        return
    row_id = _tree_row_under_cursor(tree, event)
    # Check if hovering over an actual row
    if not row_id:
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        app.history_zoom_current_path = ""
        return
    path = _history_path_for_hover(app, row_id)
    if not path:
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        app.history_zoom_current_path = ""
        return

    is_image = _is_image_file(path)
    is_video = _is_video_file(path) and bool(getattr(app, "ffmpeg_available", False))
    if not (is_image or is_video):
        if history_zoom.zoom_enabled.get():
            history_zoom.zoom_enabled.set(False)
        app.history_zoom_current_path = ""
        return
    # Only reload image if path changed
    if app.history_zoom_current_path != path:
        if is_image:
            image_copy = _load_preview_image(path)
            if not image_copy:
                if history_zoom.zoom_enabled.get():
                    history_zoom.zoom_enabled.set(False)
                app.history_zoom_current_path = ""
                app.log(f"Preview unavailable for {os.path.basename(path)}", mode="warning", verbose=3)
                return
            history_zoom.set_image(image_copy)
            app.history_zoom_current_path = path
        else:
            # Video: use ffmpeg thumbnail if present; otherwise generate asynchronously.
            app.history_zoom_current_path = path
            try:
                from main.utils import video_thumbnail

                jpeg_bytes = video_thumbnail.get_video_thumbnail_jpeg_bytes(app, path)
            except Exception:
                jpeg_bytes = None

            if jpeg_bytes:
                image_copy = None
                try:
                    with Image.open(io.BytesIO(jpeg_bytes)) as img:
                        image_copy = img.copy()
                except Exception:
                    image_copy = None
                if image_copy:
                    history_zoom.set_image(image_copy)
                    if not history_zoom.zoom_enabled.get():
                        history_zoom.zoom_enabled.set(True)
                    return

            # No thumbnail yet (or couldn't load). Kick off generation.
            if history_zoom.zoom_enabled.get():
                history_zoom.zoom_enabled.set(False)
            _ensure_video_thumb_async(app, path)
            return
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
