#region - Imports


# Standard
import os
import time
import shutil
import zipfile

# Third-party
import nenotk as ntk

# Custom
from . import duplicate_handler

# Type checking
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Helper Functions


class RetryableMoveError(Exception):
    """Raised when a file can't be moved/processed yet (locked / still being written)."""


_RETRY_BASE_DELAY_MS = 2000
_RETRY_MAX_DELAY_MS = 60000
_RETRY_MAX_ATTEMPTS = 8


def _retry_state(app: 'Main'):
    if not hasattr(app, "move_queue_retry_counts"):
        app.move_queue_retry_counts = {}
    if not hasattr(app, "move_queue_retry_due_ms"):
        app.move_queue_retry_due_ms = {}
    if not hasattr(app, "move_queue_last_stat"):
        app.move_queue_last_stat = {}
    return app.move_queue_retry_counts, app.move_queue_retry_due_ms, app.move_queue_last_stat


def _now_ms() -> int:
    return int(time.time() * 1000)


def _is_due(app: 'Main', path: str) -> bool:
    _, due_ms, _ = _retry_state(app)
    due = due_ms.get(path)
    if due is None:
        return True
    return _now_ms() >= int(due)


def _mark_retry(app: 'Main', path: str, reason: str = "") -> Optional[int]:
    """Increment retry count and compute next delay; returns delay_ms or None if giving up."""
    counts, due_ms, last_stat = _retry_state(app)
    attempts = int(counts.get(path, 0) or 0) + 1
    counts[path] = attempts

    if attempts > _RETRY_MAX_ATTEMPTS:
        # Give up
        counts.pop(path, None)
        due_ms.pop(path, None)
        last_stat.pop(path, None)
        app.log(
            f"Giving up on file after {attempts - 1} retries: {os.path.basename(path)}",
            mode="warning",
            verbose=1,
        )
        if reason:
            app.log(f"Last retry reason: {reason}", mode="warning", verbose=3)
        return None

    delay = min(_RETRY_BASE_DELAY_MS * (2 ** (attempts - 1)), _RETRY_MAX_DELAY_MS)
    due_ms[path] = _now_ms() + int(delay)
    if reason:
        app.log(
            f"Retrying soon ({int(delay/1000)}s): {os.path.basename(path)} — {reason}",
            mode="warning",
            verbose=3,
        )
    return int(delay)


def _clear_retry(app: 'Main', path: str) -> None:
    counts, due_ms, last_stat = _retry_state(app)
    counts.pop(path, None)
    due_ms.pop(path, None)
    last_stat.pop(path, None)


def _is_file_stable(app: 'Main', path: str) -> bool:
    """Returns True when file size/mtime are unchanged across attempts."""
    _, _, last_stat = _retry_state(app)
    try:
        st = os.stat(path)
        stat_key = (st.st_size, st.st_mtime)
    except Exception:
        return False
    prev = last_stat.get(path)
    last_stat[path] = stat_key
    return prev is not None and prev == stat_key


def _schedule_retry_pass(app: 'Main') -> None:
    """Schedule the next queue processing based on earliest due time."""
    _, due_ms, _ = _retry_state(app)
    if not app.move_queue:
        return
    now = _now_ms()
    next_due = None
    for p in app.move_queue:
        d = due_ms.get(p)
        if d is None:
            next_due = now
            break
        if next_due is None or int(d) < int(next_due):
            next_due = int(d)
    if next_due is None:
        return
    delay = max(250, int(next_due - now))
    # Cancel any existing timer and schedule a retry processing pass
    if app.queue_timer_id:
        try:
            app.root.after_cancel(app.queue_timer_id)
        except Exception:
            pass
    app.queue_timer_id = app.root.after(delay, lambda: process_move_queue(app))


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
    """Check if a file has a temporary extension. Returns True if temp, False if not."""
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
    rel_path = os.path.relpath(file_path, app.funnel_dir)
    # Check if file is empty (0 bytes) - The Firefox 0-byte placeholder
    if _is_empty_file(file_path):
        return False
    # Check if Firefox ".part" file
    if _is_part_file(file_path):
        return False
    # File should be processed
    return True


def _enqueue_file_if_allowed(app: 'Main', file_path: str, rel_path: str = None) -> bool:
    """Apply temp-file filters and queue the file if eligible."""
    if not _should_process_firefox_temp_files(app, file_path):
        return False
    if app.ignore_temp_files_var.get() and _is_temp_file(app, file_path):
        return False
    if file_path in app.move_queue:
        return False
    app.move_queue.append(file_path)
    app.update_queue_count()
    if rel_path is None:
        try:
            rel_path = os.path.relpath(file_path, app.funnel_dir)
        except Exception:
            rel_path = file_path
    app.log(f"Queued: {rel_path}", mode="info", verbose=2)
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


def _is_zip_file(file_path):
    """Check if a file is a ZIP file by extension and validity."""
    # Check extension
    _, ext = os.path.splitext(file_path.lower())
    if ext != '.zip':
        return False
    # Verify it's a valid zip file
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            return True
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        return False
    except Exception:
        return False


def _extract_zip(app: 'Main', zip_path, extract_dir):
    """Extract a ZIP file to the specified directory."""
    try:
        # Create the extraction directory if it doesn't exist
        os.makedirs(extract_dir, exist_ok=True)
        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Extract all contents, overwriting existing files
            zip_ref.extractall(path=extract_dir)
        # Log the extraction
        rel_path = os.path.relpath(zip_path, app.source_dir_var.get())
        rel_extract = os.path.relpath(extract_dir, app.source_dir_var.get())
        app.log(f"Extracted ZIP: {rel_path} → {rel_extract}", mode="info", verbose=1)
        # Remove the original ZIP file if enabled
        if app.auto_delete_zip_var.get():
            os.remove(zip_path)
            app.log(f"Deleted ZIP after extraction: {rel_path}", mode="info", verbose=2)
        return True
    except Exception as e:
        app.log(f"Error extracting ZIP {zip_path}: {str(e)}", mode="error", verbose=1)
        return False


#endregion
#region - File Handling


def _handle_new_folder(app: 'Main', source_path):
    """Handle a new folder being created in the watch directory."""
    try:
        # Get relative path from watch folder
        rel_path = os.path.relpath(source_path, app.funnel_dir)
        dest_path = os.path.join(app.source_dir_var.get(), rel_path)
        # Create folder structure in both locations
        os.makedirs(dest_path, exist_ok=True)
        app.log(f"Created folder: {rel_path}", mode="info", verbose=2)
        # Walk through the source directory and handle all contents
        for dirpath, dirnames, filenames in os.walk(source_path):
            # Calculate relative paths
            rel_dirpath = os.path.relpath(dirpath, source_path)
            # Create subdirectories in both locations
            for dirname in dirnames:
                rel_dir = os.path.join(rel_path, rel_dirpath, dirname)
                funnel_dir = os.path.join(app.funnel_dir, rel_dir)
                dest_dir = os.path.join(app.source_dir_var.get(), rel_dir)
                os.makedirs(funnel_dir, exist_ok=True)
                os.makedirs(dest_dir, exist_ok=True)
                app.log(f"Created subfolder: {rel_dir}", mode="info", verbose=3)
            # Queue all files for moving
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                relative_for_log = os.path.join(rel_path, rel_dirpath, filename)
                _enqueue_file_if_allowed(app, file_path, relative_for_log)
    except Exception as e:
        app.log(f"Error handling new folder {source_path}: {str(e)}", mode="error", verbose=1)


def _handle_possible_duplicate_file(app: 'Main', source_path, dest_path, rel_path):
    """Handle a file that might be a duplicate."""
    # Get partial hash size (0 = disabled, otherwise bytes to read)
    partial_hash_size = app.dupe_partial_hash_size_var.get() if app.dupe_use_partial_hash_var.get() else 0
    try:
        is_duplicate, matching_file_path = duplicate_handler.are_files_identical(
            file1=source_path,
            file2=dest_path,
            check_mode=app.dupe_check_mode_var.get(),
            method=app.dupe_filter_mode_var.get(),
            max_files=app.dupe_max_files_var.get(),
            partial_hash_size=partial_hash_size,
            app=app
        )
    except duplicate_handler.FileNotReadyError as exc:
        raise RetryableMoveError(str(exc)) from exc
    if is_duplicate:
        # Files are identical, handle based on dupe_handle_mode
        filename = os.path.basename(source_path)
        duplicate_path = source_path
        dupe_action = "Duplicate deleted"
        if app.dupe_handle_mode_var.get() == "Delete":
            # Delete the duplicate file
            try:
                os.remove(source_path)
            except (PermissionError, OSError) as exc:
                raise RetryableMoveError(str(exc)) from exc
            app.log(f"Duplicate deleted: {rel_path}", mode="info", verbose=1)
        else:  # "Move" mode
            dupe_action = "Duplicate moved"
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
            try:
                shutil.move(source_path, dup_file_path)
            except (PermissionError, OSError) as exc:
                raise RetryableMoveError(str(exc)) from exc
            app.log(f"Duplicate moved: {rel_path} -> {os.path.relpath(dup_file_path, app.duplicate_storage_path)}", mode="info", verbose=1)
            duplicate_path = dup_file_path
        # Record the duplicate file, using the matching file path as source
        original_path = matching_file_path if matching_file_path else dest_path
        if hasattr(app, "add_history_duplicate"):
            app.add_history_duplicate(rel_path=rel_path, source_path=original_path, duplicate_path=duplicate_path, action=dupe_action)
        app.duplicate_count += 1
        app.grand_duplicate_count += 1
        app.update_duplicate_count()
        # Keep legacy dict populated for safety
        try:
            app.history_order_counter += 1
            app.duplicate_history_items[filename] = {"source": original_path, "duplicate": duplicate_path, "order": app.history_order_counter}
        except Exception:
            pass
        return True, None
    else:
        # Not a duplicate, find new name
        new_dest_path = _get_unique_filename(dest_path)
        return False, new_dest_path


def _move_file(app: 'Main', source_path):
    """Internal method to move a file when the queue is ready."""
    try:
        # If the file is still changing, wait for a later pass to avoid hashing/moving partial files.
        if not _is_file_stable(app, source_path):
            raise RetryableMoveError("file still being written")

        # Get the relative path from the watch folder
        rel_path = os.path.relpath(source_path, app.funnel_dir)
        # Calculate the destination path in the source folder
        dest_path = os.path.join(app.source_dir_var.get(), rel_path)
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        # If file exists, handle based on settings
        if os.path.exists(dest_path):
            # If overwrite is enabled, skip duplicate checking
            if app.overwrite_on_conflict_var.get():
                app.log(f"Overwriting existing file: {rel_path}", mode="warning", verbose=2)
            else:
                # Check for duplicates and get unique name if needed
                is_duplicate, new_dest_path = _handle_possible_duplicate_file(app, source_path, dest_path, rel_path)
                if is_duplicate:
                    _clear_retry(app, source_path)
                    return True
                if new_dest_path:
                    dest_path = new_dest_path
        # Move the file
        try:
            shutil.move(source_path, dest_path)
        except (PermissionError, OSError) as exc:
            raise RetryableMoveError(str(exc)) from exc
        action = "Moved"
        app.log(f"Moved: {rel_path}", mode="info", verbose=1)
        # Handle ZIP extraction if enabled
        if app.auto_extract_zip_var.get() and _is_zip_file(dest_path):
            # Create extraction directory named after the zip file (without extension)
            zip_name = os.path.splitext(os.path.basename(dest_path))[0]
            extract_dir = os.path.join(os.path.dirname(dest_path), zip_name)
            _extract_zip(app, dest_path, extract_dir)
        # Update history list with the new filename and full path
        if hasattr(app, "add_history_moved"):
            app.add_history_moved(dest_path=dest_path, rel_path=rel_path, action=action)
        else:
            app.update_history_list(os.path.basename(dest_path), dest_path)
        # Update counts
        app.move_count += 1
        app.grand_move_count += 1
        app.movecount_var.set(f"Moved: {ntk.number_commas(app.move_count)}")
        # Note: count_folders_and_files is called once after batch processing completes
        _clear_retry(app, source_path)
        return True
    except RetryableMoveError:
        raise
    except Exception as e:
        app.log(f"Error moving file {source_path}: {str(e)}", mode="error", verbose=1)
        _clear_retry(app, source_path)
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
    queued_any = False
    if os.path.isdir(source_path):
        before_len = len(app.move_queue)
        _handle_new_folder(app, source_path)
        queued_any = len(app.move_queue) > before_len
    elif source_path not in app.move_queue:
        queued_any = _enqueue_file_if_allowed(app, source_path)
    # Start/restart only when new work exists.
    if queued_any or app.move_queue:
        start_queue(app)


def process_move_queue(app: 'Main'):
    """Process all queued file moves."""
    stop_queue(app)  # Stop the queue timer and reset progress indicators
    if not app.move_queue:
        return
    # Work on a snapshot so we can safely requeue failures.
    pending = list(app.move_queue)
    batch_total = len(pending)
    start_moved = int(getattr(app, "move_count", 0) or 0)
    start_dupes = int(getattr(app, "duplicate_count", 0) or 0)
    app.log(f"Processing {ntk.number_commas(len(app.move_queue))} queued file{'s' if len(app.move_queue) != 1 else ''}...", mode="info", verbose=2)
    success_count = 0
    failed_paths = []
    for source_path in pending:
        if not os.path.exists(source_path):
            _clear_retry(app, source_path)
            app.log(f"File not found, skipping: {source_path}", mode="warning", verbose=2)
            continue
        if not _is_due(app, source_path):
            failed_paths.append(source_path)
            continue
        try:
            if _move_file(app, source_path):
                success_count += 1
            else:
                _clear_retry(app, source_path)
        except RetryableMoveError as exc:
            delay = _mark_retry(app, source_path, reason=str(exc))
            if delay is not None:
                failed_paths.append(source_path)

    # Replace queue with failures for retry; successes are removed.
    app.move_queue = failed_paths
    app.update_queue_count()

    if batch_total == 1:
        app.log(
            f"Move pass complete: {ntk.number_commas(success_count)}/1 file ({ntk.number_commas(len(failed_paths))} pending)\n",
            mode="info",
            verbose=1,
        )
    else:
        app.log(
            f"Batch pass complete: {ntk.number_commas(success_count)}/{ntk.number_commas(batch_total)} files ({ntk.number_commas(len(failed_paths))} pending)\n",
            mode="info",
            verbose=1,
        )

    # Desktop notification (independent of minimize-to-tray)
    # Only notify when the queue fully clears to avoid notification spam on retry passes.
    if not app.move_queue:
        try:
            moved_delta = int(getattr(app, "move_count", 0) or 0) - start_moved
            dupe_delta = int(getattr(app, "duplicate_count", 0) or 0) - start_dupes
            title = "Folder-Funnel"
            msg = f"Batch complete. Processed: {batch_total}. Moved: {moved_delta}. Duplicates: {dupe_delta}."
            if hasattr(app, "notify"):
                app.notify(msg, title=title)
        except Exception:
            pass

    # If anything failed due to locks/partial writes, schedule the next pass.
    if app.move_queue:
        _schedule_retry_pass(app)


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
            app.log(f"Removed renamed file from queue: {os.path.basename(old_path)}", mode="info", verbose=3)
        if not os.path.isdir(new_path) and new_path not in app.move_queue:
            queue_move_file(app, new_path)
        app.update_queue_count()
    except Exception as e:
        app.log(f"Error handling rename event: {str(e)}", mode="error", verbose=1)


#endregion
