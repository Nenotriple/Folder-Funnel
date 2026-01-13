#region - Imports


# Standard
import os
import re
import shutil
import threading

# Third-party
from watchdog.observers import Observer
import nenotk as ntk

# Custom
from .event_handler import FunnelFolderHandler, SourceFolderHandler
from . import fast_discovery

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
    # Show activity during initialization (non-blocking)
    app.set_status("busy", "Counting files...")
    app.toggle_widgets_state(state="running")

    # Cancellation token for overlapping starts/stops
    init_token = object()
    app._init_run_token = init_token

    def _ui(fn, *args, **kwargs):
        try:
            app.root.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            return

    def _is_cancelled() -> bool:
        return getattr(app, "_init_run_token", None) is not init_token

    def _ui_log(message: str, mode: str = "system", verbose: int = 2) -> None:
        _ui(app.log, message, mode=mode, verbose=verbose)

    def _compute_counts(source_path: str) -> tuple[int, int]:
        # Prefer fast discovery when enabled and available.
        try:
            if getattr(app, "fast_discovery_enabled_var", None) is not None and app.fast_discovery_enabled_var.get():
                if hasattr(app, "fast_discovery_available") and app.fast_discovery_available(path=source_path):
                    return fast_discovery.get_counts_via_mft(source_path)
        except Exception:
            pass

        folder_count = 0
        file_count = 0
        i = 0
        for _root_dir, dirs, files in os.walk(source_path):
            folder_count += len(dirs)
            file_count += len(files)
            i += 1
            if i % 100 == 0:
                _ui(app.foldercount_var.set, f"Folders: {ntk.number_commas(folder_count)}")
                _ui(app.filecount_var.set, f"Files: {ntk.number_commas(file_count)}")
        return folder_count, file_count

    def _scan_existing_files(funnel_dir: str) -> list[str]:
        if not funnel_dir or not os.path.exists(funnel_dir):
            return []
        existing_files: list[str] = []
        from .move_queue import _should_process_firefox_temp_files, _is_temp_file
        for dirpath, _dirnames, filenames in os.walk(funnel_dir):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if not _should_process_firefox_temp_files(app, file_path):
                    continue
                if app.ignore_temp_files_var.get() and _is_temp_file(app, file_path):
                    continue
                existing_files.append(os.path.normpath(file_path))
        return existing_files

    def _prompt_existing_files(existing_files: list[str]) -> None:
        if not existing_files:
            return
        file_count_str = ntk.number_commas(len(existing_files))
        message = (
            f"Found {file_count_str} pre-existing file{'s' if len(existing_files) != 1 else ''} in the funnel folder.\n\n"
            f"Would you like to add {'them' if len(existing_files) != 1 else 'it'} to the move queue for processing?"
        )
        confirm = ntk.askyesno("Pre-existing Files Found", message)
        if confirm:
            for file_path in existing_files:
                if file_path not in app.move_queue:
                    app.move_queue.append(file_path)
            app.update_queue_count()
            app.log(
                f"Added {file_count_str} pre-existing file{'s' if len(existing_files) != 1 else ''} to the move queue",
                mode="info",
                verbose=2,
            )
            from .move_queue import start_queue

            start_queue(app)
        else:
            app.log(
                f"Ignored {file_count_str} pre-existing file{'s' if len(existing_files) != 1 else ''} in the funnel folder",
                mode="info",
                verbose=2,
            )

    def _finalize_startup(existing_files: list[str]) -> None:
        if _is_cancelled():
            return
        try:
            _prompt_existing_files(existing_files)
        except Exception:
            pass
        _start_folder_watcher(app)
        app.set_status("running")
        app.move_count = 0
        app.movecount_var.set("Moved: 0")
        app.duplicate_count = 0
        app.update_duplicate_count()

    def _worker() -> None:
        try:
            source_path = app.source_dir_var.get()
            if not source_path or not os.path.exists(source_path):
                return

            folder_count, file_count = _compute_counts(source_path)
            if _is_cancelled():
                return
            _ui(app.foldercount_var.set, f"Folders: {ntk.number_commas(folder_count)}")
            _ui(app.filecount_var.set, f"Files: {ntk.number_commas(file_count)}")
            try:
                app.folder_count = int(folder_count)
                app.file_count = int(file_count)
            except Exception:
                pass

            _ui(app.set_status, "busy", "Syncing folders...")
            # Synchronous sync on this worker thread (UI updates marshaled internally)
            sync_funnel_folders(app, silent="initial")
            if _is_cancelled():
                return

            # Scan for pre-existing files (worker thread), prompt on UI thread
            existing_files = _scan_existing_files(getattr(app, "funnel_dir", ""))
            _ui(_finalize_startup, existing_files)
        except Exception as exc:
            _ui_log(f"Startup initialization failed: {exc}", mode="warning", verbose=1)

    threading.Thread(target=_worker, daemon=True).start()


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
    app.log("Ready!\n", mode="system", verbose=1)


def stop_folder_watcher(app: 'Main'):
    """Stop the folder watching process with confirmation"""
    if not (app.funnel_observer or app.source_observer):
        return True
    confirm = ntk.askokcancel("Stop Process?", "This will stop the Folder-Funnel process and remove the funnel folder.\n\nContinue?")
    if not confirm:
        return False
    # Cancel any in-progress initialization.
    try:
        app._init_run_token = None
    except Exception:
        pass
    _stop_folder_watcher(app)
    app.log("Stopping Folder-Funnel process...", mode="system", verbose=1)
    if app.funnel_dir and os.path.exists(app.funnel_dir):
        try:
            shutil.rmtree(app.funnel_dir)
        except Exception as exc:
            app.log(f"Failed to remove funnel folder {app.funnel_dir}: {exc}", mode="warning", verbose=2)
    app.log(f"Removed funnel folder: {app.funnel_dir}", mode="system", verbose=1)
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
            app.log("Funnel observer did not stop cleanly", mode="warning", verbose=4)
        app.funnel_observer = None
    if app.source_observer:
        app.source_observer.stop()
        app.source_observer.join(timeout=2)
        if hasattr(app.source_observer, "is_alive") and app.source_observer.is_alive():
            app.log("Source observer did not stop cleanly", mode="warning", verbose=4)
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

    def _ui(fn, *args, **kwargs):
        try:
            app.root.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            return

    def _ui_tick() -> None:
        try:
            _tick_progress(app, progress_state)
        except Exception:
            pass

    try:
        os.makedirs(app.funnel_dir, exist_ok=True)
        if not silent:
            _ui(app.log, "Initializing synced folder...", mode="system", verbose=2)

        # Create directories in funnel: prefer fast discovery when enabled.
        def _process_dirs_batch(batch: list[str]) -> None:
            nonlocal counter_created
            item_counter = 0
            for abs_dir in batch:
                try:
                    relpath = os.path.relpath(abs_dir, source_path)
                    if relpath == '.':
                        continue
                    funnel_dirpath = os.path.join(app.funnel_dir, relpath)
                    if not os.path.exists(funnel_dirpath):
                        os.makedirs(funnel_dirpath, exist_ok=True)
                        counter_created += 1
                except Exception:
                    continue
                item_counter += 1
                if item_counter % 50 == 0:
                    _ui(_ui_tick)

        use_fast = False
        try:
            if getattr(app, "fast_discovery_enabled_var", None) is not None and app.fast_discovery_enabled_var.get():
                if hasattr(app, "fast_discovery_available") and app.fast_discovery_available(path=source_path):
                    use_fast = True
        except Exception:
            use_fast = False

        if use_fast:
            fast_discovery.enumerate_paths_via_mft(
                source_path,
                include_dirs=True,
                batch_size=2000,
                batch_callback=_process_dirs_batch,
            )
        else:
            # Fallback: walk source and mirror directories.
            batch: list[str] = []
            for dirpath, _dirnames, _filenames in os.walk(source_path):
                batch.append(dirpath)
                if len(batch) >= 2000:
                    _process_dirs_batch(batch)
                    batch = []
            if batch:
                _process_dirs_batch(batch)

        # Remove stale dirs from funnel (best-effort)
        item_counter = 0
        for dirpath, _dirnames, _filenames in os.walk(app.funnel_dir, topdown=False):
            relpath = os.path.relpath(dirpath, app.funnel_dir)
            source_dirpath = os.path.join(source_path, relpath)
            if not os.path.exists(source_dirpath):
                try:
                    if not os.listdir(dirpath):
                        os.rmdir(dirpath)
                        counter_removed += 1
                except OSError:
                    pass
            item_counter += 1
            if item_counter % 200 == 0:
                _ui(_ui_tick)

        if silent in [False, "semi"]:
            _ui(
                app.log,
                f"Sync complete: Created {ntk.number_commas(counter_created)}, removed {ntk.number_commas(counter_removed)} directories",
                mode="system",
                verbose=2,
            )
        elif silent == "initial":
            try:
                folder_count = re.split(" ", app.foldercount_var.get())
                file_count = re.split(" ", app.filecount_var.get())
                _ui(
                    app.log,
                    f"Watching: {ntk.number_commas(folder_count[1])} folders and {ntk.number_commas(file_count[1])} files",
                    mode="system",
                    verbose=2,
                )
            except Exception:
                pass
    except Exception as e:
        _ui(ntk.showinfo, "Error: sync_funnel_folders()", f"{str(e)}")
        _ui(app.log, f"Error syncing funnel folders: {str(e)}", mode="error", verbose=1)
    finally:
        _ui(app.queue_progressbar.__setitem__, 'value', 0)
        _ui(app.queue_progressbar.configure, mode="determinate")


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
        file_count = ntk.number_commas(len(existing_files))
        message = f"Found {file_count} pre-existing file{'s' if file_count != 1 else ''} in the funnel folder.\n\nWould you like to add {'them' if file_count != 1 else 'it'} to the move queue for processing?"
        confirm = ntk.askyesno("Pre-existing Files Found", message)
        if confirm:
            # Add files to the move queue
            for file_path in existing_files:
                if file_path not in app.move_queue:
                    app.move_queue.append(file_path)
            app.update_queue_count()
            app.log(f"Added {file_count} pre-existing file{'s' if file_count != 1 else ''} to the move queue", mode="info", verbose=2)
            # Start the queue timer to process these files
            from .move_queue import start_queue
            start_queue(app)
        else:
            app.log(f"Ignored {file_count} pre-existing file{'s' if file_count != 1 else ''} in the funnel folder", mode="info", verbose=2)


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
        app.log(f"Delta sync create failed for {funnel_target}: {exc}", mode="warning", verbose=3)


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
        app.log(f"Delta sync delete failed for {funnel_target}: {exc}", mode="warning", verbose=3)


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
        app.log(f"Delta sync move failed {src_funnel} -> {dest_funnel}: {exc}", mode="warning", verbose=3)


#endregion
