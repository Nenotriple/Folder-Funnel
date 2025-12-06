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


def sync_funnel_folders(app: 'Main', silent="semi"):
    """Sync the funnel folders with the source folder. Debounced with timer cancellation."""
    global _sync_timer_id
    # Cancel any pending sync operation
    if _sync_timer_id is not None:
        try:
            app.root.after_cancel(_sync_timer_id)
        except Exception:
            pass
    # Schedule new sync with delay
    _sync_timer_id = app.root.after(DELAY, lambda: _do_sync(app, silent))


def _do_sync(app: 'Main', silent):
    """Execute the sync operation and clear the timer ID."""
    global _sync_timer_id
    _sync_timer_id = None
    app.sync_funnel_folders(silent)


def count_folders_and_files(app: 'Main'):
    """Count the number of folders and files in the source folder. Debounced with timer cancellation."""
    global _count_timer_id
    # Cancel any pending count operation
    if _count_timer_id is not None:
        try:
            app.root.after_cancel(_count_timer_id)
        except Exception:
            pass
    # Schedule new count with delay
    _count_timer_id = app.root.after(DELAY, lambda: _do_count(app))


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
        # We only care about new files, not modifications
        pass


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
