#region - Imports


# Standard
import os
import re
import shutil

# Third-party
from watchdog.observers import Observer
import nenotk as ntk

# Custom
from .event_handler import FunnelFolderHandler, SourceFolderHandler

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
        confirm = ntk.askokcancel("Begin Process?", "This will create a copy of the selected folder and all sub-folders (excluding files), and begin the Folder-Funnel process.\n\nContinue?")
        if not confirm:
            return
    # Show activity on progress bar during initialization
    app.set_status("busy", "Counting files...")
    app.root.update_idletasks()
    app.toggle_widgets_state(state="running")
    app.count_folders_and_files()
    app.set_status("busy", "Syncing folders...")
    app.root.update_idletasks()
    sync_funnel_folders(app, silent="initial")
    # Check for pre-existing files in the funnel folder
    _scan_for_existing_files(app)
    _start_folder_watcher(app)
    app.set_status("running")
    app.move_count = 0
    app.movecount_var.set("Moved: 0")
    app.duplicate_count = 0
    app.update_duplicate_count()


def _tick_progress(app: 'Main', state: dict):
    """Advance and render the manual progress indicator."""
    state["value"] += state.get("step", 0)
    if state["value"] > state.get("max", 100):
        state["value"] = 0
    app.queue_progressbar['value'] = state["value"]
    app.root.update_idletasks()


def _start_folder_watcher(app: 'Main'):
    """Start watching both the watch folder and source folder for changes"""
    # Stop any existing observers
    _stop_folder_watcher(app)
    # Set up funnel folder observer
    app.funnel_observer = Observer()
    funnel_handler = FunnelFolderHandler(app)
    app.funnel_observer.schedule(funnel_handler, path=app.funnel_dir, recursive=True)
    app.funnel_observer.start()
    # Set up source folder observer
    app.source_observer = Observer()
    source_handler = SourceFolderHandler(app)
    app.source_observer.schedule(source_handler, path=app.source_dir_var.get(), recursive=True)
    app.source_observer.start()
    app.log("Ready!\n", mode="system")


def stop_folder_watcher(app: 'Main'):
    """Stop the folder watching process with confirmation"""
    if not (app.funnel_observer or app.source_observer):
        return True
    confirm = ntk.askokcancel("Stop Process?", "This will stop the Folder-Funnel process and remove the funnel folder.\n\nContinue?")
    if not confirm:
        return False
    _stop_folder_watcher(app)
    app.log("Stopping Folder-Funnel process...", mode="system")
    if app.funnel_dir and os.path.exists(app.funnel_dir):
        try:
            shutil.rmtree(app.funnel_dir)
        except Exception as exc:
            app.log(f"Failed to remove watch folder {app.funnel_dir}: {exc}", mode="warning")
    app.log(f"Removed watch folder: {app.funnel_dir}", mode="system")
    app.reset_status_row()
    app.clear_history()
    app.toggle_widgets_state(state="idle")
    return True


def _stop_folder_watcher(app: 'Main'):
    """Stop all file system observers"""
    if app.funnel_observer:
        app.funnel_observer.stop()
        app.funnel_observer.join(timeout=2)
        if hasattr(app.funnel_observer, "is_alive") and app.funnel_observer.is_alive():
            app.log("Funnel observer did not stop cleanly", mode="warning")
        app.funnel_observer = None
    if app.source_observer:
        app.source_observer.stop()
        app.source_observer.join(timeout=2)
        if hasattr(app.source_observer, "is_alive") and app.source_observer.is_alive():
            app.log("Source observer did not stop cleanly", mode="warning")
        app.source_observer = None


def sync_funnel_folders(app: 'Main', silent=False):
    """Create or update the watch folder structure to match the source folder"""
    source_path = app.source_dir_var.get()
    if not app.check_working_dir_exists():
        return
    source_folder_name = os.path.basename(source_path)
    parent_dir = os.path.dirname(source_path)
    app.funnel_dir_name = f"{app.funnel_name_prefix}{source_folder_name}"
    app.funnel_dir = os.path.normpath(os.path.join(parent_dir, app.funnel_dir_name))
    counter_created = 0
    counter_removed = 0
    # Set progress bar to determinate mode for manual animation
    app.queue_progressbar.configure(mode="determinate")
    app.queue_progressbar['value'] = 0
    app.root.update_idletasks()
    progress_state = {"value": 0, "step": 10, "max": 100}
    try:
        # Create watch folder
        os.makedirs(app.funnel_dir, exist_ok=True)
        if not silent:
            app.log("Initializing synced folder...", mode="system")
        # Walk through the source directory and create corresponding directories in the watch folder
        item_counter = 0
        for dirpath, dirnames, filenames in os.walk(source_path):
            relpath = os.path.relpath(dirpath, source_path)
            if relpath == '.':
                continue
            funnel_dirpath = os.path.join(app.funnel_dir, relpath)
            if not os.path.exists(funnel_dirpath):
                os.makedirs(funnel_dirpath)
                counter_created += 1
            item_counter += 1
            if item_counter % 20 == 0:
                _tick_progress(app, progress_state)
        # Walk through the watch folder and remove directories that no longer exist in the source path
        item_counter = 0
        for dirpath, dirnames, filenames in os.walk(app.funnel_dir, topdown=False):
            relpath = os.path.relpath(dirpath, app.funnel_dir)
            source_dirpath = os.path.join(source_path, relpath)
            if not os.path.exists(source_dirpath):
                # Only remove directories that are empty (no files or subdirectories)
                try:
                    if not os.listdir(dirpath):
                        os.rmdir(dirpath)
                        counter_removed += 1
                except OSError:
                    pass
            item_counter += 1
            if item_counter % 20 == 0:
                _tick_progress(app, progress_state)
        if silent in [False, "semi"]:
            app.log(f"Created: {counter_created}, Removed: {counter_removed} directories in {app.funnel_dir}", mode="system")
        elif silent == "initial":
            folder_count = re.split(" ", app.foldercount_var.get())
            file_count = re.split(" ", app.filecount_var.get())
            app.log(f"Watching: {folder_count[1]} directories and {file_count[1]} files in the selected folder.", mode="system")
    except Exception as e:
        ntk.showinfo("Error: sync_funnel_folders()", f"{str(e)}")
        app.log(f"Error syncing funnel folders: {str(e)}", mode="error")
    finally:
        # Reset progress bar to determinate mode
        app.queue_progressbar['value'] = 0
        app.queue_progressbar.configure(mode="determinate")


def _scan_for_existing_files(app: 'Main'):
    """Scan the funnel folder for existing files and optionally queue them for processing"""
    if not app.funnel_dir or not os.path.exists(app.funnel_dir):
        return
    existing_files = []
    # Walk through the funnel folder to find all existing files
    for dirpath, dirnames, filenames in os.walk(app.funnel_dir):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            # Apply same filtering logic as the regular queue system
            from .move_queue import _should_process_firefox_temp_files, _is_temp_file
            # Check if file should be processed based on Firefox temp files setting
            if not _should_process_firefox_temp_files(app, file_path):
                continue
            # Check if the file is a temporary file that should be ignored
            if app.ignore_temp_files_var.get() and _is_temp_file(app, file_path):
                continue
            existing_files.append(file_path)
    # If files exist, ask user what to do
    if existing_files:
        file_count = len(existing_files)
        message = f"Found {file_count} pre-existing file{'s' if file_count != 1 else ''} in the funnel folder.\n\nWould you like to add {'them' if file_count != 1 else 'it'} to the move queue for processing?"
        confirm = ntk.askyesno("Pre-existing Files Found", message)
        if confirm:
            # Add files to the move queue
            for file_path in existing_files:
                if file_path not in app.move_queue:
                    app.move_queue.append(file_path)
            app.update_queue_count()
            app.log(f"Added {file_count} pre-existing file{'s' if file_count != 1 else ''} to the move queue", mode="info")
            # Start the queue timer to process these files
            from .move_queue import start_queue
            start_queue(app)
        else:
            app.log(f"Ignored {file_count} pre-existing file{'s' if file_count != 1 else ''} in the funnel folder", mode="info")


#endregion
#region - Delta sync helpers


def _rel_to_funnel(app: 'Main', abs_path: str) -> str:
    """Return the path inside the funnel that mirrors a source abs path."""
    rel_path = os.path.relpath(abs_path, app.source_dir_var.get())
    return os.path.normpath(os.path.join(app.funnel_dir, rel_path))


def _prune_empty_parents(path: str, stop_at: str):
    """Walk upward removing empty directories until stop_at (exclusive)."""
    path = os.path.normpath(path)
    stop_at = os.path.normpath(stop_at)
    while path and path.startswith(stop_at) and path != stop_at:
        try:
            os.rmdir(path)
        except OSError:
            return
        path = os.path.dirname(path)


def mirror_created_dir(app: 'Main', abs_dir_path: str):
    """Create matching directory in funnel for a new source directory."""
    if not app.funnel_dir:
        return
    funnel_target = _rel_to_funnel(app, abs_dir_path)
    try:
        os.makedirs(funnel_target, exist_ok=True)
    except Exception as exc:
        app.log(f"Delta sync create failed for {funnel_target}: {exc}", mode="warning")


def mirror_deleted_dir(app: 'Main', abs_dir_path: str):
    """Remove matching directory in funnel when a source directory is deleted."""
    if not app.funnel_dir:
        return
    funnel_target = _rel_to_funnel(app, abs_dir_path)
    if not os.path.exists(funnel_target):
        return
    try:
        if not os.listdir(funnel_target):
            os.rmdir(funnel_target)
        _prune_empty_parents(os.path.dirname(funnel_target), app.funnel_dir)
    except Exception as exc:
        app.log(f"Delta sync delete failed for {funnel_target}: {exc}", mode="warning")


def mirror_moved_dir(app: 'Main', abs_src: str, abs_dest: str):
    """Rename/move the mirrored directory inside the funnel."""
    if not app.funnel_dir:
        return
    src_funnel = _rel_to_funnel(app, abs_src)
    dest_funnel = _rel_to_funnel(app, abs_dest)
    try:
        os.makedirs(os.path.dirname(dest_funnel), exist_ok=True)
        if os.path.exists(src_funnel):
            os.replace(src_funnel, dest_funnel)
        else:
            os.makedirs(dest_funnel, exist_ok=True)
        _prune_empty_parents(os.path.dirname(src_funnel), app.funnel_dir)
    except Exception as exc:
        app.log(f"Delta sync move failed {src_funnel} -> {dest_funnel}: {exc}", mode="warning")


#endregion
