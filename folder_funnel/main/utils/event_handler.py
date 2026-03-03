#region - Imports


# Standard
import os

# Third-party
from watchdog.events import FileSystemEventHandler

# Local imports
from . import duplicate_handler

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Constants


DELAY = 2000  # Delay in milliseconds for after() calls


#endregion
#region - Timer ID Tracking


# Module-level timer IDs for debounce cancellation
_count_timer_id = None
_sync_timer_id = None


#endregion
#region - Helper Functions


def queue_move_file(app: 'Main', path):
    """Queue a file or folder for moving to the watch folder."""
    app.root.after(DELAY, lambda: app.queue_move_file(path))


def handle_rename_event(app: 'Main', src, dest):
    """Handle a file rename event."""
    app.root.after(DELAY, lambda: app.handle_rename_event(src, dest))


def _set_timer(timer_name: str, timer_id):
    """Internal: store timer ids by name."""
    global _count_timer_id, _sync_timer_id
    if timer_name == "count":
        _count_timer_id = timer_id
    elif timer_name == "sync":
        _sync_timer_id = timer_id


def _get_timer(timer_name: str):
    """Internal: fetch timer ids by name."""
    if timer_name == "count":
        return _count_timer_id
    if timer_name == "sync":
        return _sync_timer_id
    return None


def _run_and_clear(timer_name: str, callback, *args, **kwargs):
    """Invoke callback then clear stored timer id."""
    _set_timer(timer_name, None)
    callback(*args, **kwargs)


def _debounce(app: 'Main', timer_name: str, callback, delay: int = DELAY, *args, **kwargs):
    """Cancel any pending timer of this name and schedule a new one."""
    current_id = _get_timer(timer_name)
    if current_id is not None:
        try:
            app.root.after_cancel(current_id)
        except Exception:
            pass
    new_id = app.root.after(delay, lambda: _run_and_clear(timer_name, callback, *args, **kwargs))
    _set_timer(timer_name, new_id)


def sync_funnel_folders(app: 'Main', silent="semi"):
    """Sync the funnel folders with the source folder. Debounced with timer cancellation."""
    _debounce(app, "sync", _do_sync, DELAY, app, silent)


def _do_sync(app: 'Main', silent):
    """Execute the sync operation and clear the timer ID."""
    global _sync_timer_id
    _sync_timer_id = None
    app.sync_funnel_folders(silent)


def count_folders_and_files(app: 'Main'):
    """Count the number of folders and files in the source folder. Debounced with timer cancellation."""
    _debounce(app, "count", _do_count, DELAY, app)


def _do_count(app: 'Main'):
    """Execute the count operation and clear the timer ID."""
    global _count_timer_id
    _count_timer_id = None
    app.count_folders_and_files()


def invalidate_dir_cache(dir_path: str = None):
    """Invalidate the directory cache when file system changes occur."""
    duplicate_handler.invalidate_dir_cache(dir_path)


#endregion
#region - cls FunnelFolderHandler


class FunnelFolderHandler(FileSystemEventHandler):
    def __init__(self, app: 'Main'):
        self.parent = app


    def on_created(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        # If a new folder is created, queue it so its contents are processed once ready
        if event.is_directory:
            if os.path.exists(event.src_path):
                queue_move_file(self.parent, event.src_path)
        # Else, queue the file for moving
        else:
            if os.path.exists(event.src_path):
                queue_move_file(self.parent, event.src_path)


    def on_deleted(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        # Funnel deletions do not require a full sync; moves will catch up


    def on_modified(self, event):
        # Some downloads are created as placeholders (e.g., 0-byte/temp) and
        # become valid only after subsequent writes/rename. Re-queue file
        # modifications so temp-filtered creations can be picked up later.
        if event.is_directory:
            return
        invalidate_dir_cache(os.path.dirname(event.src_path))
        if os.path.exists(event.src_path):
            queue_move_file(self.parent, event.src_path)


    def on_moved(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        invalidate_dir_cache(os.path.dirname(event.dest_path))
        handle_rename_event(self.parent, event.src_path, event.dest_path)


#endregion
#region - cls SourceFolderHandler


class SourceFolderHandler(FileSystemEventHandler):
    def __init__(self, app: 'Main'):
        self.parent = app


    def on_created(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        if event.is_directory:
            from . import folder_watcher  # Lazy import
            folder_watcher.mirror_created_dir(self.parent, event.src_path)
            self.parent.adjust_counts(folder_delta=1)
        else:
            self.parent.adjust_counts(file_delta=1)


    def on_deleted(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        if event.is_directory:
            from . import folder_watcher  # Lazy import
            folder_watcher.mirror_deleted_dir(self.parent, event.src_path)
            self.parent.adjust_counts(folder_delta=-1)
        else:
            self.parent.adjust_counts(file_delta=-1)


    def on_moved(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        invalidate_dir_cache(os.path.dirname(event.dest_path))
        if event.is_directory:
            from . import folder_watcher  # Lazy import
            folder_watcher.mirror_moved_dir(self.parent, event.src_path, event.dest_path)
