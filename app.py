#region - Imports


# Standard
import os
import sys
import ctypes
from typing import Optional

# Standard GUI
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Custom
import interface
import move_queue
import listbox_logic
import folder_watcher
import interface_logic
import duplicate_handler
import settings_manager
from help_window import HelpWindow


#endregion
#region - Main


class Main:
    def __init__(self, root: tk.Tk):
        self.root = root


#endregion
#region - Variable Registration


        # tk Variables
        self.working_dir_var = tk.StringVar(value="")  # The source folder
        self.status_label_var = tk.StringVar(value="Status: Idle")  # App status
        self.foldercount_var = tk.StringVar(value="Folders: 0")  # Folder count of source folder
        self.filecount_var = tk.StringVar(value="Files: 0")  # File count of source folder
        self.movecount_var = tk.StringVar(value="Moved: 0")  # Number of files moved to source folder
        self.dupecount_var = tk.StringVar(value="Duplicates: 0")  # Display variable for duplicate count
        self.queuecount_var = tk.StringVar(value="Queue: 0")  # Number of files in the move queue
        self.dupe_handle_mode_var = tk.StringVar(value="Move")  # Method for handling duplicates ("Delete", "Move")
        self.dupe_filter_mode_var = tk.StringVar(value="Flexible")  # Method for finding similar files to check ("Flexible", "Strict")
        self.dupe_check_mode_var = tk.StringVar(value="Similar")  # Additional MD5 check criteria ("Similar", "Single")
        self.dupe_max_files_var = tk.IntVar(value=50)  # Max files to check for duplicates
        self.move_queue_length_var = tk.IntVar(value=15000)  # Timer length (ms) for move queue
        self.text_log_wrap_var = tk.BooleanVar(value=True)  # Wrap text in log window
        self.history_mode_var = tk.StringVar(value="Moved")  # History display mode ("Moved", "Duplicate")
        self.ignore_firefox_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files created by Firefox
        self.ignore_temp_files_var = tk.BooleanVar(value=True)  # Ignore temporary files in the funnel folder
        self.auto_extract_zip_var = tk.BooleanVar(value=False)  # Automatically extract zip files in the funnel folder
        self.auto_delete_zip_var = tk.BooleanVar(value=False)  # Delete zip files after extraction
        self.overwrite_on_conflict_var = tk.BooleanVar(value=False)  # Overwrite files with the same name in the source folder

        # Initialize UI objects
        self.dir_entry: Optional[ttk.Entry] = None
        self.dir_entry_tooltip: Optional[tk.Widget] = None
        self.start_button: Optional[ttk.Button] = None
        self.stop_button: Optional[ttk.Button] = None
        self.text_log: Optional[scrolledtext.ScrolledText] = None
        self.history_menubutton: Optional[ttk.Menubutton] = None
        self.history_listbox: Optional[tk.Listbox] = None
        self.history_menu: Optional[tk.Menu] = None
        self.running_indicator: Optional[ttk.Progressbar] = None
        self.queue_progressbar: Optional[ttk.Progressbar] = None

        # App Path
        self.app_path = self.get_app_path()  # The application folder

        # Funnel and Duplicate Folders
        self.watch_path = ""  # The funnel folder that will be watched
        self.watch_folder_name = ""  # The name of the funnel folder
        self.watch_name_prefix = "#FUNNEL#_"  # Prefix for the funnel folder name
        self.duplicate_storage_path = ""  # The folder that will store moved duplicate files
        self.duplicate_name_prefix = "#DUPLICATE#_"  # Prefix for duplicate storage folder name

        # Log
        self.messages = []  # Log message list

        # History
        self.max_history_entries = 100  # Maximum number of history items to store

        # History items and count
        self.move_history_items = {}  # Store history of moved files and their final path as {filename: source_path}
        self.move_count = 0  # Files moved
        self.duplicate_history_items = {}  # Store history of matched duplicate files as {filename: {"source": source_path, "duplicate": duplicate_path}}
        self.duplicate_count = 0  # Duplicate files detected

        # Queue related variables
        self.move_queue = []  # List of files waiting to be moved
        self.queue_count = 0  # Number of files in the move queue
        self.queue_timer_id = None  # Store timer ID for cancellation
        self.queue_start_time = None  # Store when the queue timer started

        # Observers for file watching
        self.watch_observer = None
        self.source_observer = None

        # Temporary filetypes
        self.temp_filetypes = [".tmp", ".temp", ".part", ".crdownload", ".partial", ".bak"]

        # Help window
        self.help_window = HelpWindow(self.root)


#endregion
#region - Interface Logic


    def select_working_dir(self, path=None):
        interface_logic.select_working_dir(self, path)

    def open_folder(self, path=None):
        interface_logic.open_folder(self, path)

    def log(self, message):
        interface_logic.log(self, message)

    def clear_log(self):
        interface_logic.clear_log(self)

    def clear_history(self):
        interface_logic.clear_history(self)

    def toggle_text_wrap(self):
        interface_logic.toggle_text_wrap(self)

    def toggle_button_state(self, state="idle"):
        interface_logic.toggle_button_state(self, state)

    def toggle_indicator(self, state=None):
        interface_logic.toggle_indicator(self, state)

    def open_help_window(self):
        interface_logic.open_help_window(self)

    def update_duplicate_count(self):
        interface_logic.update_duplicate_count(self)

    def update_queue_count(self):
        interface_logic.update_queue_count(self)

    def get_history_list(self):
        return interface_logic.get_history_list(self)


#endregion
#region - Listbox Logic


    def toggle_history_mode(self):
        listbox_logic.toggle_history_mode(self)

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


#endregion
#region - Folder Watcher Logic


    def start_folder_watcher(self):
        folder_watcher.start_folder_watcher(self)

    def stop_folder_watcher(self):
        return folder_watcher.stop_folder_watcher(self)

    def sync_watch_folders(self, silent=False):
        folder_watcher.sync_watch_folders(self, silent)


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
        path = self.working_dir_var.get()
        if not path:
            messagebox.showerror("Error", "No folder selected")
            return False
        elif not os.path.exists(path):
            messagebox.showerror("Error", "Selected folder does not exist")
            return False
        return path


    def count_folders_and_files(self):
        """Count the number of folders and files in the source folder."""
        folder_count = 0
        file_count = 0
        for root, dirs, files in os.walk(self.working_dir_var.get()):
            folder_count += len(dirs)
            file_count += len(files)
        self.foldercount_var.set(f"Folders: {folder_count}")
        self.filecount_var.set(f"Files: {file_count}")


#endregion
#region - Settings Logic


    def load_and_apply_settings(self):
        settings_manager.load_settings(self)
        settings_manager.apply_settings_to_ui(self)


    def save_settings(self):
        settings_manager.save_settings(self)


    def reset_settings(self):
        if not messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings to default values?"):
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
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = WINDOW_WIDTH
        window_height = WINDOW_HEIGHT
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Load settings
        self.root.after(100, lambda: self.load_and_apply_settings())


    def set_appid(self):
        myappid = 'Folder-Funnel.Nenotriple'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


    def set_icon(self):
        icon_path = os.path.join(self.app_path, "icon.png")
        if os.path.exists(icon_path):
            self.root.iconphoto(True, tk.PhotoImage(file=icon_path))


    def get_app_path(self):
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        elif __file__:
            return os.path.dirname(__file__)
        return ""


    def on_closing(self):
        """Handle cleanup when closing the application"""
        self.process_pending_moves()
        self.save_settings()
        if not self.stop_folder_watcher():
            return
        duplicate_handler.confirm_duplicate_storage_removal(self)
        self.root.quit()


# Run the application
root = tk.Tk()
app = Main(root)
interface.create_interface(app)
app.setup_window()
root.mainloop()
