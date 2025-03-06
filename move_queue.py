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
    from app import Main


#endregion
#region - Helper Functions


def _is_empty_file(file_path):
    """Check if a file exists and has 0 bytes. Returns True if empty, False if not."""
    # Check if path exists and is a file
    if not os.path.exists(file_path):
        return False
    if not os.path.isfile(file_path):
        return False
    # Check if the file has zero size
    if os.path.getsize(file_path) == 0:
        return True
    # File has content
    return False


def _is_temp_file(app: 'Main', file_path):
    """Check if a file has a temporary extension. Returns True if temp, False not."""
    _, ext = os.path.splitext(file_path.lower())
    # Check if the extension is in the list of temporary file types
    if ext in app.temp_filetypes:
        return True
    # Not a temporary file
    return False


def _is_part_file(file_path):
    """Check if a file has a ".part" extension (indicating an incomplete download). Returns True if part file, False if not."""
    _, ext = os.path.splitext(file_path.lower())
    # Check specifically for ".part" extension
    if ext == ".part":
        return True
    # Not a part file
    return False


def _should_process_firefox_temp_files(app: 'Main', file_path):
    """Returns True if file should be processed, False if it should be skipped."""
    # Check if temp files should be ignored
    if not app.ignore_firefox_temp_files_var.get():
        return True
    # Get relative path for logging
    rel_path = os.path.relpath(file_path, app.watch_path)
    # Check if file is empty (0 bytes) - The Firefox 0-byte placeholder
    if _is_empty_file(file_path):
        return False
    # Check if Firefox ".part" file
    if _is_part_file(file_path):
        return False
    # File should be processed
    return True


def _update_queue_progress(app: 'Main'):
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


def _get_unique_filename(file_path):
    """Returns a unique file path by appending a counter to the filename if needed."""
    if not os.path.exists(file_path):
        return file_path
    base, ext = os.path.splitext(file_path)
    counter = 1
    unique_path = file_path
    while os.path.exists(unique_path):
        unique_path = f"{base}_{counter}{ext}"
        counter += 1
    return unique_path


#endregion
#region - File Handling


def _handle_new_folder(app: 'Main', source_path):
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
                # Check if file should be processed
                if not _should_process_firefox_temp_files(app, file_path):
                    continue
                # Check if the file is a temporary file that should be ignored
                if app.ignore_temp_files_var.get() and _is_temp_file(app, file_path):
                    continue
                if file_path not in app.move_queue:
                    app.move_queue.append(file_path)
                    app.update_queue_count()
                    app.log(f"Queued file: {os.path.join(rel_path, rel_dirpath, filename)}")
    except Exception as e:
        app.log(f"Error handling new folder {source_path}: {str(e)}")


def _handle_possible_duplicate_file(app: 'Main', source_path, dest_path, rel_path):
    """Handle a file that might be a duplicate."""
    if duplicate_handler.are_files_identical(file1=source_path, file2=dest_path, check_mode=app.dupe_check_mode_var.get(), method=app.dupe_filter_mode_var.get(), max_files=app.dupe_max_files_var.get()):
        # Files are identical, handle based on dupe_handle_mode
        filename = os.path.basename(source_path)
        duplicate_path = source_path
        if app.dupe_handle_mode_var.get() == "Delete":
            # Delete the duplicate file
            os.remove(source_path)
            app.log(f"Deleted duplicate file: {rel_path}")
        else:  # "Move" mode
            if not app.duplicate_storage_path:
                duplicate_handler.create_duplicate_storage_folder(app)
            # Ensure the directory structure exists in the duplicate folder
            rel_dir = os.path.dirname(rel_path)
            dup_dir_path = os.path.join(app.duplicate_storage_path, rel_dir)
            os.makedirs(dup_dir_path, exist_ok=True)
            # Calculate destination path in duplicate storage
            dup_file_path = os.path.join(app.duplicate_storage_path, rel_path)
            # Handle if file already exists in duplicate storage - use get_unique_filename
            dup_file_path = _get_unique_filename(dup_file_path)
            # Move the duplicate file
            shutil.move(source_path, dup_file_path)
            app.log(f"Moved duplicate file: {rel_path} -> {os.path.relpath(dup_file_path, app.duplicate_storage_path)}")
            duplicate_path = dup_file_path
        # Record the duplicate file
        app.duplicate_history_items[filename] = {"source": dest_path, "duplicate": duplicate_path}
        app.duplicate_count += 1
        app.update_duplicate_count()
        # Update history listbox if we're in Duplicate or All mode
        if app.history_mode_var.get() == "Duplicate":
            app.toggle_history_mode(app)
        return True, None
    else:
        # Not a duplicate, find new name
        new_dest_path = _get_unique_filename(dest_path)
        return False, new_dest_path


def _move_file(app: 'Main', source_path):
    """Internal method to move a file when the queue is ready."""
    try:
        # Get the relative path from the watch folder
        rel_path = os.path.relpath(source_path, app.watch_path)
        # Calculate the destination path in the source folder
        dest_path = os.path.join(app.working_dir_var.get(), rel_path)
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        # If file exists, handle based on settings
        if os.path.exists(dest_path):
            # If overwrite is enabled, skip duplicate checking
            if app.overwrite_on_conflict_var.get():
                app.log(f"Overwriting existing file: {rel_path}")
            else:
                # Check for duplicates and get unique name if needed
                is_duplicate, new_dest_path = _handle_possible_duplicate_file(app, source_path, dest_path, rel_path)
                if is_duplicate:
                    return True
                if new_dest_path:
                    dest_path = new_dest_path
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


#endregion
#region - Queue Management


def start_queue(app: 'Main'):
    """Start/restart the queue timer and progress bar updates."""
    # Cancel any existing timer
    if app.queue_timer_id:
        app.root.after_cancel(app.queue_timer_id)
    # Start new timer
    app.queue_start_time = time.time() * 1000
    app.queue_progressbar['value'] = 0
    _update_queue_progress(app)
    app.queue_timer_id = app.root.after(app.move_queue_length_var.get(), lambda: process_move_queue(app))


def stop_queue(app: 'Main'):
    """Stop the queue timer and reset progress bar."""
    if app.queue_timer_id:
        app.root.after_cancel(app.queue_timer_id)
    app.queue_timer_id = None  # Reset timer ID
    app.queue_start_time = None  # Reset start time
    app.queue_progressbar['value'] = 0  # Reset progress bar


def queue_move_file(app: 'Main', source_path):
    """Add a file or folder to the move queue and start/restart the timer."""
    if os.path.isdir(source_path):
        _handle_new_folder(app, source_path)
    elif source_path not in app.move_queue:
        # Check if file should be processed
        if not _should_process_firefox_temp_files(app, source_path):
            return
        # Check if the file is a temporary file that should be processed
        if app.ignore_temp_files_var.get() and _is_temp_file(app, source_path):
            return
        app.move_queue.append(source_path)
        app.update_queue_count()
        app.log(f"Queued file: {os.path.relpath(source_path, app.watch_path)}")
    # Start or restart the queue timer
    start_queue(app)


def process_move_queue(app: 'Main'):
    """Process all queued file moves."""
    stop_queue(app)  # Stop the queue timer and reset progress indicators
    if not app.move_queue:
        return
    app.log(f"Processing {len(app.move_queue)} queued files...")
    success_count = 0
    for source_path in app.move_queue:
        if os.path.exists(source_path):  # Check if the file exists before moving
            if _move_file(app, source_path):
                success_count += 1
        else:
            app.log(f"File not found, skipping: {source_path}")
    app.log(f"Batch move complete: {success_count}\{len(app.move_queue)} files moved successfully\n")
    app.move_queue.clear()
    app.update_queue_count()


def process_pending_moves(app: 'Main'):
    """Process any remaining files in the move queue."""
    if app.move_queue:
        process_move_queue(app)
    elif app.queue_timer_id:
        stop_queue(app)


#endregion
#region - Event Handlers


def handle_rename_event(app: 'Main', old_path, new_path):
    """Remove the old file path from the move queue if present, then add the new path for subsequent moving."""
    try:
        if old_path in app.move_queue:
            app.move_queue.remove(old_path)
            app.log(f"Removed old path from queue: {old_path}")
        if not os.path.isdir(new_path) and new_path not in app.move_queue:
            queue_move_file(app, new_path)
        app.update_queue_count()
    except Exception as e:
        app.log(f"Error handling rename event: {str(e)}")


#endregion
