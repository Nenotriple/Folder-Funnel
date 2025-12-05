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
#region - Helper Functions


def queue_move_file(app: 'Main', path):
    """Queue a file for moving to the watch folder."""
    app.root.after(DELAY, lambda: app.queue_move_file(path))


def handle_rename_event(app: 'Main', src, dest):
    """Handle a file rename event."""
    app.root.after(DELAY, lambda: app.handle_rename_event(src, dest))


def sync_funnel_folders(app: 'Main', silent="semi"):
    """Sync the funnel folders with the source folder."""
    app.root.after(DELAY, lambda: app.sync_funnel_folders(silent))


def count_folders_and_files(app: 'Main'):
    """Count the number of folders and files in the source folder."""
    app.root.after(DELAY, lambda: app.count_folders_and_files())


def invalidate_dir_cache(dir_path: str = None):
    """Invalidate the directory cache when file system changes occur."""
    duplicate_handler.invalidate_dir_cache(dir_path)


#endregion
#region - cls WatchFolderHandler


class WatchFolderHandler(FileSystemEventHandler):
    def __init__(self, app: 'Main'):
        self.parent = app


    def on_created(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        # If a new folder is created, sync the watch folders
        if event.is_directory:
            sync_funnel_folders(self.parent, silent="semi")
        # Else, queue the file for moving
        else:
            # Check if the file exists and queue it
            if os.path.exists(event.src_path):
                queue_move_file(self.parent, event.src_path)


    def on_deleted(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        sync_funnel_folders(self.parent, silent="silent")


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
            sync_funnel_folders(self.parent, silent="semi")
        count_folders_and_files(self.parent)


    def on_deleted(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        if event.is_directory:
            sync_funnel_folders(self.parent, silent="silent")
        count_folders_and_files(self.parent)


    def on_moved(self, event):
        invalidate_dir_cache(os.path.dirname(event.src_path))
        invalidate_dir_cache(os.path.dirname(event.dest_path))
        if event.is_directory:
            sync_funnel_folders(self.parent, silent="semi")
        count_folders_and_files(self.parent)
