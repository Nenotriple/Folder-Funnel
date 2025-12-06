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
import pystray
import nenotk as ntk
from PIL import Image

# Custom
from main.ui import interface
from main.ui import listbox_logic
from main.ui import interface_logic
from main.utils import move_queue
from main.utils import folder_watcher
from main.utils import duplicate_handler
from main.utils import settings_manager


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
        self.move_queue_length_var = tk.IntVar(value=15000)  # Timer length (ms) for move queue
        self.text_log_wrap_var = tk.BooleanVar(value=True)  # Wrap text in log window
        self.log_verbosity_var = tk.IntVar(value=1)  # Log verbosity level (1-4): 1=Essential, 2=Extended, 3=Detailed, 4=Debug
        self.history_mode_var = tk.StringVar(value="All")  # History display mode ("All", "Moved", "Duplicate")
        self.log_prefix_filter_var = tk.BooleanVar(value=True)  # Show log prefix (True=show, False=hide)
        self.ignore_firefox_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files created by Firefox
        self.ignore_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files in the funnel folder
        self.auto_extract_zip_var = tk.BooleanVar(value=False)  # Automatically extract zip files in the funnel folder
        self.auto_delete_zip_var = tk.BooleanVar(value=False)  # Delete zip files after extraction
        self.overwrite_on_conflict_var = tk.BooleanVar(value=False)  # Overwrite files with the same name in the source folder
        self.minimize_to_tray_var = tk.BooleanVar(value=False)  # Minimize to system tray instead of closing

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
        self.history_menubutton: Optional[ttk.Menubutton] = None
        self.history_listbox: Optional[tk.Listbox] = None
        self.history_menu: Optional[tk.Menu] = None
        self.file_menu: Optional[tk.Menu] = None
        self.queue_progressbar: Optional[ttk.Progressbar] = None

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

    def get_history_list(self):
        return interface_logic.get_history_list(self)


#endregion
#region - Listbox Logic


    def clear_history(self):
        interface_logic.clear_history(self)

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
        """Count the number of folders and files in the source folder, updating the progress bar."""
        # Prevent re-entry if already counting
        if getattr(self, '_counting_in_progress', False):
            return
        self._counting_in_progress = True
        try:
            folder_count = 0
            file_count = 0
            i = 0
            for root_dir, dirs, files in os.walk(self.source_dir_var.get()):
                folder_count += len(dirs)
                file_count += len(files)
                i += 1
                if i % 20 == 0:
                    self.foldercount_var.set(f"Folders: {folder_count}")
                    self.filecount_var.set(f"Files: {file_count}")
                    self.root.update_idletasks()
            self.folder_count = folder_count
            self.file_count = file_count
            self.foldercount_var.set(f"Folders: {folder_count}")
            self.filecount_var.set(f"Files: {file_count}")
        finally:
            self._counting_in_progress = False


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
        self.foldercount_var.set(f"Folders: {self.folder_count}")
        self.filecount_var.set(f"Files: {self.file_count}")


#endregion
#region - Settings Logic


    def load_and_apply_settings(self):
        settings_manager.load_settings(self)
        settings_manager.apply_settings_to_ui(self)


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
        WINDOW_MIN_HEIGHT = 300
        # Setup window
        self.set_appid()
        self.set_icon()
        self.root.title(WINDOW_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}')
        ntk.center_window(self.root, to='screen')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Load settings
        self.root.after(100, lambda: self.load_and_apply_settings())


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
        """Handle window close - minimize to tray or exit."""
        if self.minimize_to_tray_var.get():
            confirm = ntk.askyesnocancel("Minimize to Tray", "Minimize Folder-Funnel to the system tray?", detail="You can restore it later from the tray icon.", yes_text="Minimize", no_text="Cancel", cancel_text="Close Window")
            if confirm is None: # User cancelled
                self.exit_application()
            elif confirm: # User confirmed
                self.minimize_to_tray()
            # User declined - do nothing
        else:
            self.exit_application()


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
        """Minimize the application to the system tray."""
        self.log("Minimized to system tray", mode="system", verbose=2)
        self.root.withdraw()
        self.start_tray_icon()


    def reveal_from_tray(self):
        """Restore the application window from the system tray."""
        self.stop_tray_icon()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.log("Restored from system tray", mode="system", verbose=2)


    def start_tray_icon(self):
        """Start the system tray icon."""
        menu = pystray.Menu(
            pystray.MenuItem("Reveal Folder-Funnel", lambda: self.root.after(0, self.reveal_from_tray), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: self.status_label_var.get(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Folder-Funnel", lambda: self.root.after(0, self._tray_exit)),
        )
        # Load icon image
        if os.path.exists(self.icon_path):
            icon_image = Image.open(self.icon_path)
        else:
            # Fallback: create a simple colored icon
            icon_image = Image.new('RGB', (64, 64), color='blue')
        # Create and run tray icon
        self.tray_icon = pystray.Icon("Folder-Funnel", icon_image, "Folder-Funnel", menu)
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()


    def stop_tray_icon(self):
        """Stop and remove the system tray icon."""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
            self.tray_thread = None


    def _tray_exit(self):
        """Exit from tray - restore window first then exit."""
        self.stop_tray_icon()
        self.root.deiconify()
        self.exit_application()


# Run the application
root = tk.Tk()
app = Main(root)
interface.create_interface(app)
app.setup_window()
root.mainloop()
