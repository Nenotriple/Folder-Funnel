#region - Imports


# Standard
import os
import re
import shutil

# Standard GUI
from tkinter import messagebox

# Third-party
from watchdog.observers import Observer

# Custom
from event_handler import WatchFolderHandler, SourceFolderHandler

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Folder Watcher Functions


def start_folder_watcher(app: 'Main', auto_start=False):
    """Start the folder watching process after verification"""
    if not app.check_working_dir_exists():
        return
    if not auto_start:
        confirm = messagebox.askokcancel("Begin Process?", "This will create a copy of the selected folder and all sub-folders (excluding files), and begin the Folder-Funnel process.\n\nContinue?")
        if not confirm:
            return
    app.toggle_indicator(state="start")
    sync_watch_folders(app, silent="initial")
    _start_folder_watcher(app)
    app.status_label_var.set("Status: Running")
    app.count_folders_and_files()
    app.move_count = 0
    app.movecount_var.set("Moved: 0")
    app.duplicate_count = 0
    app.update_duplicate_count()
    app.toggle_button_state(state="running")


def _start_folder_watcher(app: 'Main'):
    """Start watching both the watch folder and source folder for changes"""
    # Stop any existing observers
    _stop_folder_watcher(app)
    # Set up watch folder observer
    app.watch_observer = Observer()
    watch_handler = WatchFolderHandler(app)
    app.watch_observer.schedule(watch_handler, path=app.watch_path, recursive=True)
    app.watch_observer.start()
    # Set up source folder observer
    app.source_observer = Observer()
    source_handler = SourceFolderHandler(app)
    app.source_observer.schedule(source_handler, path=app.working_dir_var.get(), recursive=True)
    app.source_observer.start()
    app.log("Ready!\n")


def stop_folder_watcher(app: 'Main'):
    """Stop the folder watching process with confirmation"""
    if not (app.watch_observer or app.source_observer):
        return True
    confirm = messagebox.askokcancel("Stop Process?", "This will stop the Folder-Funnel process and remove the duplicate folder.\n\nContinue?")
    if not confirm:
        return False
    _stop_folder_watcher(app)
    app.log("Stopping Folder-Funnel process...")
    app.status_label_var.set("Status: Idle")
    app.toggle_button_state(state="idle")
    if app.watch_path and os.path.exists(app.watch_path):
        shutil.rmtree(app.watch_path)
        app.log(f"Removed watch folder: {app.watch_path}")
    app.toggle_indicator(state="stop")
    return True


def _stop_folder_watcher(app: 'Main'):
    """Stop all file system observers"""
    if app.watch_observer:
        app.watch_observer.stop()
        app.watch_observer.join()
        app.watch_observer = None
    if app.source_observer:
        app.source_observer.stop()
        app.source_observer.join()
        app.source_observer = None


def sync_watch_folders(app: 'Main', silent=False):
    """Create or update the watch folder structure to match the source folder"""
    source_path = app.working_dir_var.get()
    if not app.check_working_dir_exists():
        return
    source_folder_name = os.path.basename(source_path)
    parent_dir = os.path.dirname(source_path)
    app.watch_folder_name = f"{app.watch_name_prefix}{source_folder_name}"
    app.watch_path = os.path.normpath(os.path.join(parent_dir, app.watch_folder_name))
    counter_created = 0
    counter_removed = 0
    try:
        # Create watch folder
        os.makedirs(app.watch_path, exist_ok=True)
        if not silent:
            app.log("Initializing synced folder...")
        # Walk through the source directory and create corresponding directories in the watch folder
        for dirpath, dirnames, filenames in os.walk(source_path):
            relpath = os.path.relpath(dirpath, source_path)
            if relpath == '.':
                continue
            watch_dirpath = os.path.join(app.watch_path, relpath)
            if not os.path.exists(watch_dirpath):
                os.makedirs(watch_dirpath)
                counter_created += 1
        # Walk through the watch folder and remove directories that no longer exist in the source path
        for dirpath, dirnames, filenames in os.walk(app.watch_path, topdown=False):
            relpath = os.path.relpath(dirpath, app.watch_path)
            source_dirpath = os.path.join(source_path, relpath)
            if not os.path.exists(source_dirpath):
                os.rmdir(dirpath)
                counter_removed += 1
        if silent in [False, "semi"]:
            app.log(f"Created: {counter_created}, Removed: {counter_removed} directories in {app.watch_path}")
        elif silent == "initial":
            folder_count = re.split(" ", app.foldercount_var.get())
            app.log(f"Watching: {folder_count[1]} directories in {app.watch_path}")
    except Exception as e:
        messagebox.showerror("Error: create_watch_folders()", f"{str(e)}")


#endregion
