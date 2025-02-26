#region - Imports


# Standard
import os

# Third-party
from watchdog.events import FileSystemEventHandler

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - cls WatchFolderHandler


class WatchFolderHandler(FileSystemEventHandler):
    def __init__(self, app: 'Main'):
        self.parent = app


    def on_created(self, event):
        # If a new folder is created, sync the watch folders
        if event.is_directory:
            self.parent.sync_watch_folders(silent="semi")
        # Else, queue the file for moving
        else:
            if os.path.exists(event.src_path):
                self.parent.queue_move_file(event.src_path)


    def on_deleted(self, event):
        self.parent.sync_watch_folders(silent="silent")


    def on_modified(self, event):
        # We only care about new files, not modifications
        pass


    def on_moved(self, event):
        # Inform the app that a file was renamed/moved
        self.parent.handle_rename_event(event.src_path, event.dest_path)


#endregion
#region - cls SourceFolderHandler


class SourceFolderHandler(FileSystemEventHandler):
    def __init__(self, app: 'Main'):
        self.parent = app


    def on_created(self, event):
        if event.is_directory:
            # Only sync folders when a directory is created in source
            self.parent.sync_watch_folders(silent="semi")
        self.parent.count_folders_and_files()


    def on_deleted(self, event):
        if event.is_directory:
            # Only sync folders when a directory is deleted in source
            self.parent.sync_watch_folders(silent="silent")
        self.parent.count_folders_and_files()


    def on_moved(self, event):
        if event.is_directory:
            # Only sync folders when a directory is moved/renamed in source
            self.parent.sync_watch_folders(silent="semi")
        self.parent.count_folders_and_files()
