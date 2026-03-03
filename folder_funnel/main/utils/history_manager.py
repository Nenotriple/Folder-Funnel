#region - Imports

# Standard
import os
import time
from typing import TYPE_CHECKING, Dict, List, Optional

# Third-party
import nenotk as ntk

if TYPE_CHECKING:
    from app import Main


#endregion


#region - History Manager


def _now_ts() -> float:
    return time.time()


def _format_time(ts: float) -> str:
    try:
        # 12-hour clock with AM/PM (e.g. "1:05 PM")
        s = time.strftime("%I:%M %p", time.localtime(ts))
        return s.lstrip("0")
    except Exception:
        return ""


def _next_history_id(app: 'Main') -> str:
    counter = getattr(app, "history_entry_counter", 0) + 1
    app.history_entry_counter = counter
    return str(counter)


def _safe_relpath(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base)
    except Exception:
        return path


def _get_entry(app: 'Main', entry_id: str) -> Optional[dict]:
    return getattr(app, "history_entries", {}).get(entry_id)


def add_entry(app: 'Main', entry: dict) -> str:
    """Insert a history entry and trim to max entries.

    Entry schema (dict):
      id: str
      kind: 'moved'|'duplicate'
      ts: float
      time: str
      name: str
      rel: str
      action: str
      primary_path: str
      source_path: Optional[str]   (for duplicates)
      duplicate_path: Optional[str] (for duplicates)
    """
    if not hasattr(app, "history_entries"):
        app.history_entries = {}
    if not hasattr(app, "history_order"):
        app.history_order = []

    entry_id = entry.get("id") or _next_history_id(app)
    entry["id"] = entry_id
    app.history_entries[entry_id] = entry
    app.history_order.append(entry_id)

    # Trim oldest entries across all kinds
    max_entries = int(getattr(app, "max_history_entries", 100) or 100)
    while len(app.history_order) > max_entries:
        oldest_id = app.history_order.pop(0)
        app.history_entries.pop(oldest_id, None)

    # Refresh UI if present
    try:
        if hasattr(app, "refresh_history_listbox"):
            app.refresh_history_listbox()
    except Exception:
        pass

    return entry_id


def add_moved(app: 'Main', dest_path: str, rel_path: str, action: str = "Moved") -> str:
    ts = _now_ts()
    entry = {
        "id": _next_history_id(app),
        "kind": "moved",
        "ts": ts,
        "time": _format_time(ts),
        "name": os.path.basename(dest_path),
        "rel": rel_path or _safe_relpath(dest_path, app.source_dir_var.get()),
        "action": action,
        "primary_path": dest_path,
        "source_path": None,
        "duplicate_path": None,
    }
    return add_entry(app, entry)


def add_duplicate(
    app: 'Main',
    rel_path: str,
    source_path: str,
    duplicate_path: str,
    action: str,
) -> str:
    ts = _now_ts()
    entry = {
        "id": _next_history_id(app),
        "kind": "duplicate",
        "ts": ts,
        "time": _format_time(ts),
        "name": os.path.basename(duplicate_path) if duplicate_path else os.path.basename(rel_path),
        "rel": rel_path or "",
        "action": action,
        # In Duplicate-mode, the primary action historically opens the matched/source file
        "primary_path": source_path,
        "source_path": source_path,
        "duplicate_path": duplicate_path,
    }
    return add_entry(app, entry)


def remove_entry(app: 'Main', entry_id: str) -> None:
    if not hasattr(app, "history_entries"):
        return
    app.history_entries.pop(entry_id, None)
    if hasattr(app, "history_order"):
        try:
            app.history_order.remove(entry_id)
        except ValueError:
            pass
    try:
        if hasattr(app, "refresh_history_listbox"):
            app.refresh_history_listbox()
    except Exception:
        pass


def clear(app: 'Main') -> None:
    if hasattr(app, "history_entries"):
        app.history_entries.clear()
    if hasattr(app, "history_order"):
        app.history_order.clear()
    # Also clear legacy dicts to keep the rest of the app consistent
    if hasattr(app, "move_history_items"):
        app.move_history_items.clear()
    if hasattr(app, "duplicate_history_items"):
        app.duplicate_history_items.clear()
    try:
        if hasattr(app, "refresh_history_listbox"):
            app.refresh_history_listbox()
    except Exception:
        pass


def filtered_ids(app: 'Main', mode: str) -> List[str]:
    """Return history entry IDs newest-first, filtered by mode."""
    order = list(getattr(app, "history_order", []))
    order.reverse()
    if not mode or mode == "All":
        return order
    want = "moved" if mode == "Moved" else "duplicate"
    out: List[str] = []
    entries: Dict[str, dict] = getattr(app, "history_entries", {})
    for entry_id in order:
        entry = entries.get(entry_id)
        if entry and entry.get("kind") == want:
            out.append(entry_id)
    return out


def exists(path: Optional[str]) -> bool:
    return bool(path) and os.path.exists(path)


def copy_to_clipboard(app: 'Main', text: str) -> None:
    try:
        app.root.clipboard_clear()
        app.root.clipboard_append(text)
        app.root.update_idletasks()
        app.log("Copied path to clipboard", mode="system", verbose=3)
    except Exception:
        pass


def open_in_explorer(path: str) -> None:
    os.system(f'explorer /select,"{path}"')


def open_file(path: str) -> None:
    os.startfile(path)


def confirm_delete(kind: str, basename: str) -> bool:
    title = "Confirm Delete"
    prompt = "Delete file:" if kind != "duplicate" else "Delete duplicate file:"
    return ntk.askyesno(title, prompt=prompt, detail=basename)


def safe_get(app: 'Main', entry_id: str) -> Optional[dict]:
    return _get_entry(app, entry_id)


#endregion
