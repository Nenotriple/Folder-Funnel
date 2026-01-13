"""
Main (app) is the main application module for Folder-Funnel.
All public functionality is exposed here.

To add new tools or methods, implement them in `main/.../your_new_tool.py` (accepting the `Main` instance), then import and expose them here.
Other modules can then access new features via the `Main` instance.
"""

#region - Imports


# Standard
import os
import sys
import ctypes
import threading
from typing import Optional

# Standard GUI
import tkinter as tk
from tkinter import ttk, scrolledtext

# Third-party
import nenotk as ntk

# Custom
from main.ui import interface
from main.ui import listbox_logic
from main.ui import interface_logic
from main.utils import move_queue
from main.utils import folder_watcher
from main.utils import duplicate_handler
from main.utils import fast_discovery
from main.utils import settings_manager
from main.utils import history_manager
from main.utils import video_thumbnail
from main.utils import tray_manager


#endregion
#region - Main


class Main:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.initialize_app_variables()



#endregion
#region - Variable Registration


    def initialize_app_variables(self):
        # tk Variables
        self.source_dir_var = tk.StringVar(value="")  # The source folder
        self.last_working_directory: str = "" # Persisted working directory (loaded from settings, updated on selection)
        self._startup_reload_prompt_shown: bool = False # Startup state: ensure we only ask once per session
        self.status_label_var = tk.StringVar(value="Idle")  # App status
        self.status_state = "idle"  # Current status state
        self.foldercount_var = tk.StringVar(value="Folders: 0")  # Folder count of source folder
        self.filecount_var = tk.StringVar(value="Files: 0")  # File count of source folder
        self.movecount_var = tk.StringVar(value="Moved: 0")  # Number of files moved to source folder
        self.dupecount_var = tk.StringVar(value="Duplicates: 0")  # Display variable for duplicate count
        self.queuecount_var = tk.StringVar(value="Queue: 0")  # Number of files in the move queue
        self.dupe_handle_mode_var = tk.StringVar(value="Move")  # Method for handling duplicates ("Delete", "Move")
        self.dupe_filter_mode_var = tk.StringVar(value="Flexible")  # Method for finding similar files to check ("Flexible", "Strict")
        self.dupe_check_mode_var = tk.StringVar(value="Similar")  # Additional MD5 check criteria ("Similar", "Single")
        self.dupe_max_files_var = tk.IntVar(value=75)  # Max files to check for duplicates
        self.dupe_use_partial_hash_var = tk.BooleanVar(value=True)  # Use partial hash for faster initial comparison
        self.dupe_partial_hash_size_var = tk.IntVar(value=4096)  # Size in bytes for partial hash (default 4KB)
        self.move_queue_length_var = tk.IntVar(value=1000)  # Timer length (ms) for move queue
        self.text_log_wrap_var = tk.BooleanVar(value=True)  # Wrap text in log window
        self.log_verbosity_var = tk.IntVar(value=1)  # Log verbosity level (1-4): 1=Essential, 2=Extended, 3=Detailed, 4=Debug
        self.history_mode_var = tk.StringVar(value="All")  # History display mode ("All", "Moved", "Duplicate")
        self.history_image_preview_var = tk.BooleanVar(value=True)  # Enable hover preview for image history items
        self.log_prefix_filter_var = tk.BooleanVar(value=True)  # Show log prefix (True=show, False=hide)
        self.ignore_firefox_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files created by Firefox
        self.ignore_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files in the funnel folder
        self.auto_extract_zip_var = tk.BooleanVar(value=False)  # Automatically extract zip files in the funnel folder
        self.auto_delete_zip_var = tk.BooleanVar(value=False)  # Delete zip files after extraction
        self.overwrite_on_conflict_var = tk.BooleanVar(value=False)  # Overwrite files with the same name in the source folder

        # Fast discovery (Windows NTFS USN / fallback scan). Default ON on Windows.
        self.fast_discovery_enabled_var = tk.BooleanVar(value=(sys.platform == "win32"))

        self.minimize_to_tray_var = tk.BooleanVar(value=True)  # Minimize to system tray instead of closing
        self.minimize_to_tray_show_close_tip_var = tk.BooleanVar(value=True) # When minimize-to-tray is enabled, optionally show a one-time tip on first close.
        self._minimize_to_tray_close_tip_shown: bool = False # Session flag for whether the close tip has been shown

        # Desktop notifications (default ON). Independent of minimize-to-tray.
        self.notifications_enabled_var = tk.BooleanVar(value=True)
        self._last_notification_ms: float = 0.0
        self._tray_status_text: str = "Idle"

        # System tray
        self.tray_icon = None  # pystray Icon instance
        self.tray_thread = None  # Thread running the tray icon

        # Initialize UI objects
        self.dir_entry: Optional[ttk.Entry] = None
        self.dir_entry_tooltip: Optional[tk.Widget] = None
        self.browse_button: Optional[ttk.Button] = None
        self.start_stop_button: Optional[ttk.Button] = None
        self.status_label: Optional[tk.Label] = None
        self.status_label_default_fg: Optional[str] = None
        self.text_search: Optional[ntk.FindReplaceEntry] = None
        self.text_log: Optional[scrolledtext.ScrolledText] = None
        self.text_log_hscroll: Optional[ttk.Scrollbar] = None
        self.main_pane: Optional[tk.PanedWindow] = None
        self.main_pane_sash_x: Optional[int] = None
        self.main_pane_default_sash_x: Optional[int] = None
        # Main pane layout (Log + History)
        self.main_pane_orient_var = tk.StringVar(value="vertical")  # "horizontal" or "vertical"
        self.main_pane_order_var = tk.StringVar(value="history_first")  # "log_first" or "history_first"
        self.main_pane_sash_pos: Optional[int] = 475  # x if horizontal, y if vertical
        self.log_pane_frame: Optional[tk.Frame] = None
        self.history_pane_frame: Optional[tk.Frame] = None
        self.history_menubutton: Optional[ttk.Menubutton] = None
        self.history_listbox: Optional[tk.Listbox] = None
        self.history_menu: Optional[tk.Menu] = None
        self.history_header_menu: Optional[tk.Menu] = None
        self.history_zoom = None  # PopUpZoom instance for history preview
        self.history_zoom_current_path: str = ""
        self.file_menu: Optional[tk.Menu] = None
        self.queue_progressbar: Optional[ttk.Progressbar] = None

        # Media thumbnails (video via ffmpeg)
        self.ffmpeg_available: bool = False
        self.ffmpeg_path: str = ""

        # Window geometry persistence
        self.window_geometry: str | None = None  # Persisted geometry string (e.g. "1000x480+10+10")
        self.default_window_geometry: str | None = None  # Session default geometry (used for Reset)

        # App Path
        self.app_path = self.get_app_path()  # The application folder
        self.icon_path = ""  # Path to the application icon

        # Funnel and Duplicate Folders
        self.funnel_dir = ""  # The funnel folder that will be watched
        self.funnel_dir_name = ""  # The name of the funnel folder
        self.funnel_name_prefix = "#FUNNEL#_"  # Prefix for the funnel folder name
        self.duplicate_storage_path = ""  # The folder that will store moved duplicate files
        self.duplicate_name_prefix = "#DUPLICATE#_"  # Prefix for duplicate storage folder name

        # Log
        self.messages = []  # Log message list

        # History
        self.max_history_entries = 100  # Maximum number of history items to store

        # History (rich entries)
        self.history_entries = {}  # {id: entry_dict}
        self.history_order = []  # [id] chronological
        self.history_entry_counter = 0

        # History (Treeview UI state)
        self.history_columns = ("time", "type", "name", "rel", "action")
        self.history_column_labels = {
            "time": "Time",
            "type": "Type",
            "name": "Name",
            "rel": "Relative",
            "action": "Action",
        }
        self.history_column_visible_vars = {c: tk.BooleanVar(value=True) for c in self.history_columns}
        # Match shipped defaults: hide Action column by default
        try:
            self.history_column_visible_vars["action"].set(False)
        except Exception:
            pass
        # Name column cannot be disabled
        self.history_column_visible_vars["name"].set(True)
        self.history_sort_column: str | None = "name"
        self.history_sort_desc: bool = False

        # History items and count
        self.move_history_items = {}  # Store history of moved files and their final path as {filename: {"path": source_path, "order": int}}
        self.move_count = 0  # Files moved
        self.duplicate_history_items = {}  # Store history of matched duplicate files as {filename: {"source": source_path, "duplicate": duplicate_path, "order": int}}
        self.duplicate_count = 0  # Duplicate files detected
        self.history_order_counter = 0  # Counter to track chronological order of history items

        # Live folder/file counts (kept in sync incrementally)
        self.folder_count = 0
        self.file_count = 0

        # Queue related variables
        self.move_queue = []  # List of files waiting to be moved
        self.queue_count = 0  # Number of files in the move queue
        self.queue_timer_id = None  # Store timer ID for cancellation
        self.queue_start_time = None  # Store when the queue timer started

        # Observers for file watching
        self.funnel_observer = None
        self.source_observer = None

        # Temporary filetypes
        self.temp_filetypes = [".tmp", ".temp", ".part", ".crdownload", ".partial", ".bak"]

        # Stats
        self.grand_move_count = 0  # Lifetime total of files moved
        self.grand_duplicate_count = 0  # Lifetime total of duplicate files detected
        self.move_action_time = 6  # Estimated time saved per move action in seconds
        self.dupe_action_time = 11  # Estimated time saved per duplicate action in seconds


#endregion
#region - Interface Logic


    def select_working_dir(self, path=None):
        interface_logic.select_working_dir(self, path)

    def open_folder(self, path=None):
        interface_logic.open_folder(self, path)

    def log(self, message, mode="simple", verbose=1):
        interface_logic.log(self, message, mode, verbose)

    def clear_log(self):
        interface_logic.clear_log(self)

    def set_status(self, state: str, message: str | None = None):
        interface_logic.set_status(self, state, message)
        # Cache for tray thread (avoid reading Tk vars from pystray thread)
        try:
            self._tray_status_text = str(self.status_label_var.get())
        except Exception:
            pass

    def toggle_text_wrap(self):
        interface_logic.toggle_text_wrap(self)

    def toggle_widgets_state(self, state="idle"):
        interface_logic.toggle_widgets_state(self, state)

    def open_help_window(self):
        interface_logic.open_help_window(self)

    def open_stats_popup(self):
        interface_logic.open_stats_popup(self)

    def update_duplicate_count(self):
        interface_logic.update_duplicate_count(self)

    def update_queue_count(self):
        interface_logic.update_queue_count(self)

    def apply_main_pane_layout(self, user_action: bool = False):
        interface_logic.apply_main_pane_layout(self, user_action=user_action)

    def get_history_list(self):
        return interface_logic.get_history_list(self)


#endregion
#region - Listbox Logic


    def clear_history(self):
        interface_logic.clear_history(self)

    def add_history_moved(self, dest_path: str, rel_path: str, action: str = "Moved"):
        history_manager.add_moved(self, dest_path=dest_path, rel_path=rel_path, action=action)

    def add_history_duplicate(self, rel_path: str, source_path: str, duplicate_path: str, action: str):
        history_manager.add_duplicate(self, rel_path=rel_path, source_path=source_path, duplicate_path=duplicate_path, action=action)

    def remove_history_entry(self, entry_id: str):
        history_manager.remove_entry(self, entry_id)

    def toggle_history_mode(self):
        listbox_logic.toggle_history_mode(self)

    def refresh_history_listbox(self):
        listbox_logic.refresh_history_listbox(self)

    def update_history_list(self, filename, filepath):
        listbox_logic.update_history_list(self, filename, filepath)

    def show_history_context_menu(self, event):
        listbox_logic.show_history_context_menu(self, event)

    def get_selected_filepath(self, file_type="source"):
        return listbox_logic.get_selected_filepath(self, file_type)

    def open_selected_file(self):
        listbox_logic.open_selected_file(self)

    def open_selected_source_file(self):
        listbox_logic.open_selected_source_file(self)

    def open_selected_duplicate_file(self):
        listbox_logic.open_selected_duplicate_file(self)

    def show_selected_in_explorer(self):
        listbox_logic.show_selected_in_explorer(self)

    def show_selected_source_in_explorer(self):
        listbox_logic.show_selected_source_in_explorer(self)

    def show_selected_duplicate_in_explorer(self):
        listbox_logic.show_selected_duplicate_in_explorer(self)

    def delete_selected_file(self):
        listbox_logic.delete_selected_file(self)

    def delete_selected_duplicate_file(self):
        listbox_logic.delete_selected_duplicate_file(self)

    def open_selected_file_smart(self):
        listbox_logic.open_selected_file_smart(self)

    def show_selected_in_explorer_smart(self):
        listbox_logic.show_selected_in_explorer_smart(self)

    def delete_selected_file_smart(self):
        listbox_logic.delete_selected_file_smart(self)

    def reset_status_row(self):
        interface_logic.reset_status_row(self)

    def toggle_history_preview(self):
        listbox_logic.toggle_history_preview(self)

    def toggle_history_column(self, column: str):
        listbox_logic.toggle_history_column(self, column)

    def apply_history_column_visibility(self):
        listbox_logic.apply_history_column_visibility(self)

    def sort_history_by_column(self, column: str):
        listbox_logic.sort_history_by_column(self, column)


#endregion
#region - Dupe scanner Logic


    def show_duplicate_scanner(self):
        duplicate_handler.show_duplicate_scanner(self)


#endregion
#region - Folder Watcher Logic


    def start_folder_watcher(self, auto_start=False):
        folder_watcher.start_folder_watcher(self, auto_start)

    def stop_folder_watcher(self):
        return folder_watcher.stop_folder_watcher(self)

    def sync_funnel_folders(self, silent=False):
        folder_watcher.sync_funnel_folders(self, silent)


#endregion
#region - Move/Queue Logic


    def queue_move_file(self, source_path):
        move_queue.queue_move_file(self, source_path)

    def process_move_queue(self):
        move_queue.process_move_queue(self)

    def handle_rename_event(self, old_path, new_path):
        move_queue.handle_rename_event(self, old_path, new_path)

    def process_pending_moves(self):
        move_queue.process_pending_moves(self)


#endregion
#region - File Logic


    def check_working_dir_exists(self):
        """Check if the source folder exists."""
        path = self.source_dir_var.get()
        if not path:
            ntk.showinfo("Error", "No folder selected")
            return False
        elif not os.path.exists(path):
            ntk.showinfo("Error", "Selected folder does not exist")
            return False
        return path


    def count_folders_and_files(self):
        """Count the number of folders and files in the source folder.

        Thread safety:
            - This starts a background worker.
            - UI updates are marshaled via root.after().

        Notes:
            Folder-Funnel relies on counts for informational UI; the live observers
            maintain deltas via adjust_counts().
        """
        if getattr(self, '_counting_in_progress', False):
            return
        source_path = (self.source_dir_var.get() or "").strip()
        if not source_path or not os.path.exists(source_path):
            return
        self._counting_in_progress = True

        def _ui_set_counts(folder_count: int, file_count: int) -> None:
            self.folder_count = int(folder_count)
            self.file_count = int(file_count)
            self.foldercount_var.set(f"Folders: {ntk.number_commas(self.folder_count)}")
            self.filecount_var.set(f"Files: {ntk.number_commas(self.file_count)}")

        def _ui_done() -> None:
            self._counting_in_progress = False

        def _worker() -> None:
            try:
                if self.fast_discovery_enabled_var.get() and self.fast_discovery_available(path=source_path):
                    folder_count, file_count = fast_discovery.get_counts_via_mft(source_path)
                    self.root.after(0, lambda: _ui_set_counts(folder_count, file_count))
                else:
                    # Safe, portable scan with periodic UI updates.
                    folder_count = 0
                    file_count = 0
                    i = 0
                    for _root_dir, dirs, files in os.walk(source_path):
                        folder_count += len(dirs)
                        file_count += len(files)
                        i += 1
                        if i % 50 == 0:
                            self.root.after(0, lambda fc=folder_count, fic=file_count: _ui_set_counts(fc, fic))
                    self.root.after(0, lambda: _ui_set_counts(folder_count, file_count))
            finally:
                self.root.after(0, _ui_done)

        threading.Thread(target=_worker, daemon=True).start()


    def fast_discovery_available(self, path: str | None = None) -> bool:
        """Return True when a fast discovery backend is available for path."""
        try:
            target = (path or self.source_dir_var.get() or "").strip()
            if not target:
                return False
            mode = fast_discovery.detect_volume_support(target)
            return mode in ("usn_journal", "ntfs_mft")
        except Exception:
            return False


    def enumerate_with_fast_discovery(self, root_path: str, on_batch, include_dirs: bool = True, batch_size: int = 1000):
        """Enumerate paths on a worker thread and deliver batches on the UI thread."""
        def _worker() -> None:
            try:
                fast_discovery.enumerate_paths_via_mft(root_path, include_dirs=include_dirs, batch_size=batch_size, batch_callback=lambda batch: self.root.after(0, lambda b=batch: on_batch(b)))
            except Exception:
                # Fail safe: nothing to enumerate.
                return
        threading.Thread(target=_worker, daemon=True).start()


    def adjust_counts(self, folder_delta=0, file_delta=0):
        """Incrementally adjust cached counts and update UI labels."""
        if threading.current_thread() is not threading.main_thread():
            # Marshal to main thread to avoid Tk updates from watcher threads
            self.root.after(0, lambda: self.adjust_counts(folder_delta, file_delta))
            return
        if folder_delta:
            self.folder_count = max(0, self.folder_count + folder_delta)
        if file_delta:
            self.file_count = max(0, self.file_count + file_delta)
        self.foldercount_var.set(f"Folders: {ntk.number_commas(self.folder_count)}")
        self.filecount_var.set(f"Files: {ntk.number_commas(self.file_count)}")


#endregion
#region - Settings Logic


    def load_and_apply_settings(self):
        settings_manager.load_settings(self)
        settings_manager.apply_settings_to_ui(self)
        self.check_ffmpeg()


    def save_settings(self):
        settings_manager.save_settings(self)


    def reset_settings(self):
        if not ntk.askyesno("Reset Settings", "Are you sure you want to reset all settings to default values?"):
            return
        settings_manager.reset_settings(self)


#endregion
#region - Framework


    def setup_window(self):
        # Window settings
        WINDOW_TITLE = "Folder-Funnel"
        WINDOW_WIDTH = 1000
        WINDOW_HEIGHT = 480
        WINDOW_MIN_WIDTH = 400
        WINDOW_MIN_HEIGHT = 150
        # Setup window
        self.set_appid()
        self.set_icon()
        self.root.title(WINDOW_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}')
        ntk.center_window(self.root, to='screen')
        # Capture the app's default geometry
        try:
            self.root.update_idletasks()
            self.default_window_geometry = self.root.winfo_geometry()
        except Exception:
            self.default_window_geometry = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    def check_ffmpeg(self) -> bool:
        """Detect whether ffmpeg is available and prepare thumbnail cache."""
        path = video_thumbnail.find_ffmpeg() or ""
        self.ffmpeg_path = path
        self.ffmpeg_available = bool(path)
        self.log(f"ffmpeg discovery: path='{path}', available={self.ffmpeg_available}", mode="system", verbose=4)
        return self.ffmpeg_available


    def set_appid(self):
        myappid = 'Folder-Funnel.Nenotriple'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


    def set_icon(self):
        self.icon_path = os.path.join(self.app_path, "main", "ui", "icon.png")
        if os.path.exists(self.icon_path):
            self.root.iconphoto(True, tk.PhotoImage(file=self.icon_path))


    def get_app_path(self):
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        elif __file__:
            return os.path.dirname(__file__)
        return ""


    def get_data_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(__file__)


    def on_closing(self):
        tray_manager.on_closing(self)


    def exit_application(self):
        """Fully exit the application."""
        self.process_pending_moves()
        if not self.stop_folder_watcher():
            return
        if not duplicate_handler.confirm_duplicate_storage_removal(self):
            return
        self.save_settings()
        self.stop_tray_icon()
        self.root.quit()


    def minimize_to_tray(self):
        tray_manager.minimize_to_tray(self)


    def reveal_from_tray(self):
        tray_manager.reveal_from_tray(self)


    def notify(self, message: str, title: str = "Folder-Funnel") -> None:
        tray_manager.notify(self, message=message, title=title)


    def start_tray_icon(self):
        tray_manager.start_tray_icon(self)


    def stop_tray_icon(self):
        tray_manager.stop_tray_icon(self)


    def _tray_exit(self):
        self.stop_tray_icon()
        self.root.deiconify()
        self.exit_application()


def main() -> None:
    """Entry point for running the GUI app."""
    root = tk.Tk()
    app = Main(root)
    interface.create_interface(app)
    app.setup_window()
    app.root.after(100, lambda: app.load_and_apply_settings())
    root.mainloop()


if __name__ == "__main__":
    main()
