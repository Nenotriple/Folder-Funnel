#region - Imports


# Standard
import os
import time
import shutil

# Custom
import duplicate_handler

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import FolderFunnelApp


#endregion
#region - Queue Logic


def queue_move_file(app: 'FolderFunnelApp', source_path):
    """Add a file or folder to the move queue and start/restart the timer."""
    if os.path.isdir(source_path):
        _handle_new_folder(app, source_path)
    elif source_path not in app.move_queue:
        app.move_queue.append(source_path)
        app.log(f"Queued file: {os.path.relpath(source_path, app.watch_path)}")
    # Reset queue timer
    if app.queue_timer_id:
        app.root.after_cancel(app.queue_timer_id)
    # Start new timer
    app.queue_start_time = time.time() * 1000
    app.queue_progressbar['value'] = 0
    _update_queue_progress(app)
    app.queue_timer_id = app.root.after(app.move_queue_length_var.get(), lambda: process_move_queue(app))


def _handle_new_folder(app: 'FolderFunnelApp', source_path):
    """Handle a new folder being created in the watch directory."""
    try:
        # Get relative path from watch folder
        rel_path = os.path.relpath(source_path, app.watch_path)
        dest_path = os.path.join(app.working_dir_var.get(), rel_path)
        # Create folder structure in both locations
        os.makedirs(dest_path, exist_ok=True)
        app.log(f"Created folder: {rel_path}")
        # Walk through the source directory and handle all contents
        for dirpath, dirnames, filenames in os.walk(source_path):
            # Calculate relative paths
            rel_dirpath = os.path.relpath(dirpath, source_path)
            # Create subdirectories in both locations
            for dirname in dirnames:
                rel_dir = os.path.join(rel_path, rel_dirpath, dirname)
                watch_dir = os.path.join(app.watch_path, rel_dir)
                dest_dir = os.path.join(app.working_dir_var.get(), rel_dir)
                os.makedirs(watch_dir, exist_ok=True)
                os.makedirs(dest_dir, exist_ok=True)
                app.log(f"Created subfolder: {rel_dir}")
            # Queue all files for moving
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if file_path not in app.move_queue:
                    app.move_queue.append(file_path)
                    app.log(f"Queued file: {os.path.join(rel_path, rel_dirpath, filename)}")
    except Exception as e:
        app.log(f"Error handling new folder {source_path}: {str(e)}")


def _update_queue_progress(app: 'FolderFunnelApp'):
    """Update the queue progress bar."""
    if not app.queue_start_time or not app.move_queue:
        app.queue_progressbar['value'] = 0
        return
    current_time = time.time() * 1000
    elapsed = current_time - app.queue_start_time
    progress = (elapsed / app.move_queue_length_var.get()) * 100
    if progress <= 100:
        app.queue_progressbar['value'] = progress
        # Update every 50ms
        app.root.after(50, lambda: _update_queue_progress(app))
    else:
        app.queue_progressbar['value'] = 100


def process_move_queue(app: 'FolderFunnelApp'):
    """Process all queued file moves."""
    app.queue_timer_id = None  # Reset timer ID
    app.queue_start_time = None  # Reset start time
    app.queue_progressbar['value'] = 0  # Reset progress bar
    if not app.move_queue:
        return
    app.log(f"Processing {len(app.move_queue)} queued files...")
    success_count = 0
    for source_path in app.move_queue:
        if _move_file(app, source_path):
            success_count += 1
    app.log(f"Batch move complete: {success_count}/{len(app.move_queue)} files moved successfully\n")
    app.move_queue.clear()


def _move_file(app: 'FolderFunnelApp', source_path):
    """Internal method to actually move a file. Used by process_move_queue."""
    try:
        # Get the relative path from the watch folder
        rel_path = os.path.relpath(source_path, app.watch_path)
        # Calculate the destination path in the source folder
        dest_path = os.path.join(app.working_dir_var.get(), rel_path)
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        # If file exists, check if it's a duplicate
        if os.path.exists(dest_path):
            # Compare file contents
            if duplicate_handler.are_files_identical(
                file1=source_path,
                file2=dest_path,
                rigorous_check=app.rigorous_duplicate_check_var.get(),
                method=app.dupe_filter_mode_var.get(),
                max_files=app.dupe_max_files_var.get()
            ):
                # Files are identical, handle based on dupe_handle_mode
                filename = os.path.basename(source_path)
                if app.dupe_handle_mode_var.get() == "Delete":
                    # Delete the duplicate file
                    os.remove(source_path)
                    app.log(f"Deleted duplicate file: {rel_path}")
                else:  # "Move" mode
                    if not app.duplicate_storage_path:
                        app.create_duplicate_storage_folder()
                    # Ensure the directory structure exists in the duplicate folder
                    rel_dir = os.path.dirname(rel_path)
                    dup_dir_path = os.path.join(app.duplicate_storage_path, rel_dir)
                    os.makedirs(dup_dir_path, exist_ok=True)
                    # Calculate destination path in duplicate storage
                    dup_file_path = os.path.join(app.duplicate_storage_path, rel_path)
                    # Handle if file already exists in duplicate storage
                    if os.path.exists(dup_file_path):
                        base, ext = os.path.splitext(dup_file_path)
                        counter = 1
                        while os.path.exists(dup_file_path):
                            dup_file_path = f"{base}_{counter}{ext}"
                            counter += 1
                    # Move the duplicate file
                    shutil.move(source_path, dup_file_path)
                    app.log(f"Moved duplicate file: {rel_path} -> {os.path.relpath(dup_file_path, app.duplicate_storage_path)}")
                # Record the duplicate file
                # Store both the source (kept) path and duplicate path
                duplicate_path = source_path
                if app.dupe_handle_mode_var.get() == "Move":
                    duplicate_path = dup_file_path
                app.duplicate_history_items[filename] = {"source": dest_path, "duplicate": duplicate_path}
                app.duplicate_count += 1
                app.update_duplicate_count()
                return True
            # Not a duplicate, find new name
            base, ext = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = f"{base}_{counter}{ext}"
                counter += 1
        # Move the file
        shutil.move(source_path, dest_path)
        app.log(f"Moved file: {rel_path} -> {os.path.basename(dest_path)}")
        # Update history list with the new filename and full path
        app.update_history_list(os.path.basename(dest_path), dest_path)
        # Update counts
        app.move_count += 1
        app.movecount_var.set(f"Moved: {app.move_count}")
        app.count_folders_and_files()
        return True
    except Exception as e:
        app.log(f"Error moving file {source_path}: {str(e)}")
        return False


def handle_rename_event(app: 'FolderFunnelApp', old_path, new_path):
    """
    Remove the old file path from the move queue if present, then add the new path for subsequent moving.
    """
    try:
        if old_path in app.move_queue:
            app.move_queue.remove(old_path)
            app.log(f"Removed old path from queue: {old_path}")
        if not os.path.isdir(new_path) and new_path not in app.move_queue:
            app.move_queue.append(new_path)
            app.log(f"Queued renamed file: {os.path.basename(new_path)}")
    except Exception as e:
        app.log(f"Error handling rename event: {str(e)}")


#endregion
