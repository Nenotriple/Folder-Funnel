#region - Imports


# Standard
import os
import re
import shutil
import hashlib
import threading
from difflib import SequenceMatcher

# Standard GUI
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Custom
from file_database import DatabaseManager
from help_window import HelpWindow


#endregion
#region - Constants


WINDOW_TITLE = "Folder-Funnel"

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 480
WINDOW_GEOMETRY = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 300

HISTORY_LIMIT = 100


#endregion
#region - FolderFunnelApp


class FolderFunnelApp:
    def __init__(self, root):
        # Window setup
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # GUI Variables
        self.working_dir_var = tk.StringVar(value="")  # The source folder
        self.status_label_var = tk.StringVar(value="Status: Idle")  # App status
        self.foldercount_var = tk.StringVar(value="Folders: 0")  # Folder count of source folder
        self.filecount_var = tk.StringVar(value="Files: 0")  # File count of source folder
        self.movecount_var = tk.StringVar(value="Moved: 0")  # Number of files moved to source folder
        self.rigorous_duplicate_check_var = tk.BooleanVar(value=True)  # More thorough duplicate check
        self.rigorous_dupe_max_files_var = tk.IntVar(value=25)  # Max files to check for duplicates
        self.dupe_filter_mode_var = tk.StringVar(value="Strict")  # Method for filtering duplicates (Flexible/Strict)
        self.move_queue_timer_length = tk.IntVar(value=15000)  # Timer length (ms) for move queue

        # Other Variables
        self.app_path = os.path.dirname(os.path.abspath(__file__))  # The application folder
        self.database_path = os.path.join(self.app_path, "database")  # The database folder
        self.watch_path = ""  # The duplicate folder that will be watched
        self.messages = []  # Log messages
        self.history_items = {}  # Store history of moved files as {filename: full_path}
        self.move_count = 0  # Number of files moved

        # Queue related variables
        self.move_queue = []  # List of files waiting to be moved
        self.queue_timer = None  # Timer for batch processing
        self.queue_timer_id = None  # Store timer ID for cancellation
        self.queue_start_time = None  # Store when the queue timer started

        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize database
        self.database_thread = None  # Thread for initializing databases
        self.database_manager = DatabaseManager(self, self.database_path)

        # Help window
        self.help_window = HelpWindow(self.root)


#endregion
#region - Interface Setup


    def create_interface(self):
        self.create_menubar()
        self.create_control_row()
        self.create_main_frame()
        self.create_message_row()


    def create_menubar(self):
        # Create menubar
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        # File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Select source path...", command=self.select_working_dir)
        self.file_menu.add_command(label="Open selected path", command=self.open_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_closing)
        # Edit Menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(label="Sync Folders", command=self.sync_watch_folders)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Clear log", command=self.clear_log)
        self.edit_menu.add_command(label="Clear history", command=self.clear_history)
        # Options menu
        self.options_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Options", menu=self.options_menu)
        # Queue Timer submenu
        self.queue_timer_menu = tk.Menu(self.options_menu, tearoff=0)
        self.options_menu.add_cascade(label="Queue Timer", menu=self.queue_timer_menu)
        self.queue_timer_menu.add_command(label="Queue Timer Length", state="disabled")
        self.queue_timer_menu.add_radiobutton(label="5 seconds", variable=self.move_queue_timer_length, value=5000)
        self.queue_timer_menu.add_radiobutton(label="15 seconds", variable=self.move_queue_timer_length, value=15000)
        self.queue_timer_menu.add_radiobutton(label="30 seconds", variable=self.move_queue_timer_length, value=30000)
        self.queue_timer_menu.add_radiobutton(label="1 minute", variable=self.move_queue_timer_length, value=60000)
        self.queue_timer_menu.add_radiobutton(label="5 minutes", variable=self.move_queue_timer_length, value=300000)
        # Duplicate handling submenu
        self.duplicate_handling_menu = tk.Menu(self.options_menu, tearoff=0)
        self.options_menu.add_cascade(label="Duplicate Handling", menu=self.duplicate_handling_menu)
        self.duplicate_handling_menu.add_command(label="Duplicate Checking Mode", state="disabled")
        self.duplicate_handling_menu.add_radiobutton(label="Rigorous", variable=self.rigorous_duplicate_check_var, value=True)
        self.duplicate_handling_menu.add_radiobutton(label="Simple", variable=self.rigorous_duplicate_check_var, value=False)
        self.duplicate_handling_menu.add_separator()
        # Rigorous Check
        self.duplicate_handling_menu.add_command(label="Rigorous Check: Max Files", state="disabled")
        self.duplicate_handling_menu.add_radiobutton(label="10", variable=self.rigorous_dupe_max_files_var, value=10)
        self.duplicate_handling_menu.add_radiobutton(label="25", variable=self.rigorous_dupe_max_files_var, value=25)
        self.duplicate_handling_menu.add_radiobutton(label="50", variable=self.rigorous_dupe_max_files_var, value=50)
        self.duplicate_handling_menu.add_radiobutton(label="100", variable=self.rigorous_dupe_max_files_var, value=100)
        self.duplicate_handling_menu.add_radiobutton(label="1000", variable=self.rigorous_dupe_max_files_var, value=1000)
        self.duplicate_handling_menu.add_separator()
        # Dupe Filter Mode
        self.duplicate_handling_menu.add_command(label="Duplicate Matching Mode", state="disabled")
        self.duplicate_handling_menu.add_radiobutton(label="Strict", variable=self.dupe_filter_mode_var, value="Strict")
        self.duplicate_handling_menu.add_radiobutton(label="Flexible", variable=self.dupe_filter_mode_var, value="Flexible")
        # Help menu
        self.menubar.add_command(label="Help", command=self.open_help_window)


    def create_control_row(self):
        # Create control row
        control_frame = tk.Frame(self.root)
        control_frame.pack(side="top", fill="x")
        # Separator
        ttk.Separator(control_frame, orient="horizontal").pack(side="bottom", fill="x")
        # Folder
        dir_selection_frame = tk.Frame(control_frame)
        dir_selection_frame.pack(side="left", fill="x", expand=True)
        tk.Label(dir_selection_frame, text="Watch Folder:").pack(side="left")
        self.dir_entry = ttk.Entry(dir_selection_frame, textvariable=self.working_dir_var)
        self.dir_entry.pack(side="left", fill="x", expand=True)
        self.browse_button = ttk.Button(dir_selection_frame, text="Browse...", command=self.select_working_dir)
        self.browse_button.pack(side="left")
        self.open_button = ttk.Button(dir_selection_frame, text="Open", command=self.open_folder)
        self.open_button.pack(side="left")
        # Start
        self.start_button = ttk.Button(control_frame, text="Start", command=self.start_folder_watcher)
        self.start_button.pack(side="left")
        # Stop
        self.stop_button = ttk.Button(control_frame, text="Stop", state="disabled", command=self.stop_folder_watcher)
        self.stop_button.pack(side="left")


    def create_main_frame(self):
        # Create main frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)
        # paned window
        self.main_pane = tk.PanedWindow(self.main_frame, orient="horizontal", sashwidth=6, bg="#d0d0d0", bd=0)
        self.main_pane.pack(fill="both", expand=True)
        # Text frame/pane/widget
        self.text_frame = tk.Frame(self.main_pane)
        self.main_pane.add(self.text_frame, stretch="always")
        self.main_pane.paneconfigure(self.text_frame, minsize=200, width=400)
        tk.Label(self.text_frame, text="Log").pack()
        self.text_log = scrolledtext.ScrolledText(self.text_frame, wrap="word", state="disable", width=1, height=1)
        self.text_log.pack(fill="both", expand=True)
        # list frame/pane/widget
        self.list_frame = tk.Frame(self.main_pane)
        self.main_pane.add(self.list_frame, stretch="never")
        self.main_pane.paneconfigure(self.list_frame, minsize=200, width=200)
        tk.Label(self.list_frame, text="History").pack()
        self.history_listbox = tk.Listbox(self.list_frame, width=1, height=1)
        self.history_listbox.pack(fill="both", expand=True)
        # Context menu
        self.list_context_menu = tk.Menu(self.history_listbox, tearoff=0)
        self.list_context_menu.add_command(label="Open", command=self.open_selected_file)
        self.list_context_menu.add_command(label="Show in File Explorer", command=self.show_selected_in_explorer)
        self.list_context_menu.add_separator()
        self.list_context_menu.add_command(label="Delete", command=self.delete_selected_file)
        # Bind right-click event
        self.history_listbox.bind("<Button-3>", self.show_context_menu)


    def create_message_row(self):
        # Message row
        message_frame = tk.Frame(self.root)
        message_frame.pack(side="bottom", fill="x")
        ttk.Separator(message_frame, orient="horizontal").pack(fill="x")
        # Status label
        self.status_label = tk.Label(message_frame, textvariable=self.status_label_var, relief="groove", width=15, anchor="w")
        self.status_label.pack(side="left")
        # Foldercount label
        self.Foldercount_label = tk.Label(message_frame, textvariable=self.foldercount_var, relief="groove", width=15, anchor="w")
        self.Foldercount_label.pack(side="left")
        # Filecount label
        self.filecount_label = tk.Label(message_frame, textvariable=self.filecount_var, relief="groove", width=15, anchor="w")
        self.filecount_label.pack(side="left")
        # Movecount label
        self.movecount_label = tk.Label(message_frame, textvariable=self.movecount_var, relief="groove", width=15, anchor="w")
        self.movecount_label.pack(side="left")
        # Progress bar
        self.progressbar = ttk.Progressbar(message_frame, maximum=20, mode="determinate")
        self.progressbar.pack(side="left", fill="x", expand=True)
        # Queue Timer
        self.queue_progressbar = ttk.Progressbar(message_frame, mode="determinate")
        self.queue_progressbar.pack(side="left", fill="x", expand=True)


#endregion
#region - GUI Logic


    def log(self, message):
        if self.messages and self.messages[-1] == message:
            return
        self.messages.append(message)
        self.text_log.configure(state="normal")
        self.text_log.insert("end", f"{message}\n")
        self.text_log.configure(state="disable")
        self.text_log.see("end")


    def clear_log(self):
        self.text_log.configure(state="normal")
        self.text_log.delete(1.0, "end")
        self.text_log.configure(state="disable")


    def clear_history(self):
        self.history_listbox.delete(0, "end")
        self.history_items.clear()


    def toggle_button_state(self, state="idle"):
        if state == "running":
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        elif state == "idle":
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")


    def toggle_entry_state(self, state="normal"):
        self.dir_entry.configure(state=state)
        self.browse_button.configure(state=state)


    def toggle_progressbar(self, state=None):
        if state == "start":
            self.progressbar.configure(mode="indeterminate")
            self.progressbar.start()
        else:
            self.progressbar.configure(mode="determinate")
            self.progressbar.stop()


#endregion
#region - Listbox Logic


    def update_history_list(self, filename, filepath):
        """Update the history list with a new filename and its full path."""
        # Add new item to dictionary
        self.history_items[filename] = filepath
        # Remove oldest items if limit is reached
        while len(self.history_items) > HISTORY_LIMIT:
            oldest_key = next(iter(self.history_items))
            del self.history_items[oldest_key]
        # Clear and repopulate the list widget
        self.history_listbox.delete(0, "end")
        for filename in self.history_items:
            # Insert at top to show newest first
            self.history_listbox.insert(0, filename)


    def show_context_menu(self, event):
        clicked_index = self.history_listbox.nearest(event.y)
        if clicked_index >= 0:
            self.history_listbox.selection_clear(0, "end")
            self.history_listbox.selection_set(clicked_index)
            self.history_listbox.activate(clicked_index)
            self.list_context_menu.post(event.x_root, event.y_root)


    def get_selected_filepath(self):
        selection = self.history_listbox.curselection()
        if not selection:
            return None
        filename = self.history_listbox.get(selection[0])
        return self.history_items.get(filename)


    def open_selected_file(self):
        filepath = self.get_selected_filepath()
        if filepath and os.path.exists(filepath):
            os.startfile(filepath)
        else:
            messagebox.showerror("Error", "File not found")


    def show_selected_in_explorer(self):
        filepath = self.get_selected_filepath()
        if filepath and os.path.exists(filepath):
            os.system(f'explorer /select,"{filepath}"')
        else:
            messagebox.showerror("Error", "File not found")


    def delete_selected_file(self):
        filepath = self.get_selected_filepath()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "File not found")
            return
        filename = os.path.basename(filepath)
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                os.remove(filepath)
                del self.history_items[filename]
                self.history_listbox.delete(self.history_listbox.curselection())
                self.log(f"Deleted file: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file: {str(e)}")


#endregion
#region - Folder Watcher Logic


    def start_folder_watcher(self):
        if not self.check_working_dir_exists():
            return
        confirm = messagebox.askokcancel("Begin Process?", "This will create a copy of the selected folder and all sub-folders (Excluding files), and begin the Folder-Funnel process.\n\nContinue?")
        if not confirm:
            return
        self.toggle_progressbar(state="start")
        self.sync_watch_folders()
        self.initialize_databases()
        self.database_manager.start_watching(self.watch_path)
        self.status_label_var.set("Status: Initializing")
        self.toggle_button_state(state="running")
        self.count_folders_and_files()
        self.move_count = 0
        self.movecount_var.set("Moved: 0")


    def initialize_databases(self):
        self.database_thread = threading.Thread(target=self._initialize_databases)
        self.database_thread.start()


    def _initialize_databases(self):
        self.log("Initializing databases...")
        self.toggle_entry_state(state="disabled")
        self.database_manager.add_database("source", self.working_dir_var.get())
        self.database_manager.add_database("watch", self.watch_path)
        self.toggle_entry_state(state="normal")
        self.log("Ready!")
        self.status_label_var.set("Status: Running")


    def stop_folder_watcher(self):
        if not self.database_manager.observer:
            return
        confirm = messagebox.askokcancel("Stop Process?", "This will stop the Folder-Funnel process and remove the duplicate folder.\n\nContinue?")
        if not confirm:
            return
        self.database_manager.stop_watching()
        self.log("Stopping Folder-Funnel process...")
        self.status_label_var.set("Status: Idle")
        self.toggle_button_state(state="idle")
        if self.watch_path and os.path.exists(self.watch_path):
            shutil.rmtree(self.watch_path)
            self.log(f"Removed watch folder: {self.watch_path}")
        self.toggle_progressbar(state="stop")


    def sync_watch_folders(self):
        source_path = self.working_dir_var.get()
        if not self.check_working_dir_exists():
            return
        source_folder_name = os.path.basename(source_path)
        parent_dir = os.path.dirname(source_path)
        watch_folder_name = f"#watching#_{source_folder_name}"
        self.watch_path = os.path.normpath(os.path.join(parent_dir, watch_folder_name))
        counter_created = 0
        counter_removed = 0
        try:
            # Create watch folder
            os.makedirs(self.watch_path, exist_ok=True)
            self.log(f"Using watch folder: {self.watch_path}")
            # Walk through the source directory and create corresponding directories in the watch folder
            for dirpath, dirnames, filenames in os.walk(source_path):
                relpath = os.path.relpath(dirpath, source_path)
                if relpath == '.':
                    continue
                watch_dirpath = os.path.join(self.watch_path, relpath)
                if not os.path.exists(watch_dirpath):
                    os.makedirs(watch_dirpath)
                    counter_created += 1
            # Walk through the watch folder and remove directories that no longer exist in the source path
            for dirpath, dirnames, filenames in os.walk(self.watch_path, topdown=False):
                relpath = os.path.relpath(dirpath, self.watch_path)
                source_dirpath = os.path.join(source_path, relpath)
                if not os.path.exists(source_dirpath):
                    os.rmdir(dirpath)
                    counter_removed += 1
            self.log(f"Created {counter_created} new directories in {self.watch_path}")
            self.log(f"Removed {counter_removed} directories from {self.watch_path}")
        except Exception as e:
            messagebox.showerror("Error: create_watch_folders()", f"{str(e)}")


#endregion
#region - Move/Queue Logic


    def queue_move_file(self, source_path):
        """Add a file or folder to the move queue and start/restart the timer."""
        if os.path.isdir(source_path):
            self._handle_new_folder(source_path)
        elif source_path not in self.move_queue:
            self.move_queue.append(source_path)
            self.log(f"Queued file: {os.path.basename(source_path)}")
        # Reset queue timer
        if self.queue_timer_id:
            self.root.after_cancel(self.queue_timer_id)
        # Start new timer
        self.queue_start_time = self.root.tk.getint(self.root.tk.call('clock', 'milliseconds'))
        self.queue_progressbar['value'] = 0
        self._update_queue_progress()
        self.queue_timer_id = self.root.after(self.move_queue_timer_length.get(), self.process_move_queue)


    def _handle_new_folder(self, source_path):
        """Handle a new folder being created in the watch directory."""
        try:
            # Get relative path from watch folder
            rel_path = os.path.relpath(source_path, self.watch_path)
            dest_path = os.path.join(self.working_dir_var.get(), rel_path)
            # Create folder structure in both locations
            os.makedirs(dest_path, exist_ok=True)
            self.log(f"Created folder: {rel_path}")
            # Walk through the source directory and handle all contents
            for dirpath, dirnames, filenames in os.walk(source_path):
                # Calculate relative paths
                rel_dirpath = os.path.relpath(dirpath, source_path)
                # Create subdirectories in both locations
                for dirname in dirnames:
                    rel_dir = os.path.join(rel_path, rel_dirpath, dirname)
                    watch_dir = os.path.join(self.watch_path, rel_dir)
                    dest_dir = os.path.join(self.working_dir_var.get(), rel_dir)

                    os.makedirs(watch_dir, exist_ok=True)
                    os.makedirs(dest_dir, exist_ok=True)
                    self.log(f"Created subfolder: {rel_dir}")
                # Queue all files for moving
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if file_path not in self.move_queue:
                        self.move_queue.append(file_path)
                        self.log(f"Queued file: {os.path.join(rel_path, rel_dirpath, filename)}")
            # Update the databases
            source_db = self.database_manager.get_database("source")
            watch_db = self.database_manager.get_database("watch")
            if source_db and watch_db:
                # Update folder lists
                rel_path = os.path.relpath(source_path, self.watch_path)
                if rel_path not in source_db.folders:
                    source_db.folders.append(rel_path)
                if rel_path not in watch_db.folders:
                    watch_db.folders.append(rel_path)
                # Save database changes
                source_db.save_to_file(str(self.database_manager.database_dir / "source.json"))
                watch_db.save_to_file(str(self.database_manager.database_dir / "watch.json"))
        except Exception as e:
            self.log(f"Error handling new folder {source_path}: {str(e)}")


    def _update_queue_progress(self):
        """Update the queue progress bar."""
        if not self.queue_start_time or not self.move_queue:
            self.queue_progressbar['value'] = 0
            return

        current_time = self.root.tk.getint(self.root.tk.call('clock', 'milliseconds'))
        elapsed = current_time - self.queue_start_time
        progress = (elapsed / self.move_queue_timer_length.get()) * 100

        if progress <= 100:
            self.queue_progressbar['value'] = progress
            # Update every 50ms
            self.root.after(50, self._update_queue_progress)
        else:
            self.queue_progressbar['value'] = 100


    def process_move_queue(self):
        """Process all queued file moves."""
        self.queue_timer_id = None  # Reset timer ID
        self.queue_start_time = None  # Reset start time
        self.queue_progressbar['value'] = 0  # Reset progress bar
        if not self.move_queue:
            return
        self.log(f"Processing {len(self.move_queue)} queued files...")
        success_count = 0
        for source_path in self.move_queue:
            if self._move_file(source_path):
                success_count += 1
        if success_count == 1:
            self.log(f"Move complete: 1 file moved successfully")
        else:
            self.log(f"Batch move complete: {success_count}/{len(self.move_queue)} files moved successfully")
        self.move_queue.clear()


    def _move_file(self, source_path):
        """Internal method to actually move a file. Used by process_move_queue."""
        try:
            # Get the relative path from the watch folder
            rel_path = os.path.relpath(source_path, self.watch_path)
            # Calculate the destination path in the source folder
            dest_path = os.path.join(self.working_dir_var.get(), rel_path)
            # Ensure the destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            watch_db = self.database_manager.get_database("watch")
            source_db = self.database_manager.get_database("source")
            # If file exists, check if it's a duplicate
            if os.path.exists(dest_path):
                # Compare file contents
                if self._are_files_identical(source_path, dest_path):
                    # Files are identical, delete the duplicate
                    os.remove(source_path)
                    self.log(f"Deleted duplicate file: {rel_path}")
                    # Update watch DB to show file removal
                    if watch_db:
                        watch_db.partial_update(rel_path, "deleted")
                        watch_db.save_to_file(str(self.database_manager.database_dir / "watch.json"))
                    return True
                # Not a duplicate, find new name
                base, ext = os.path.splitext(dest_path)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = f"{base}_{counter}{ext}"
                    counter += 1
            # Move the file
            shutil.move(source_path, dest_path)
            self.log(f"Moved file: {rel_path} -> {os.path.basename(dest_path)}")
            # Update watch DB: file no longer resides in watch folder
            if watch_db:
                watch_db.partial_update(rel_path, "deleted")
                watch_db.save_to_file(str(self.database_manager.database_dir / "watch.json"))
            # Update source DB: file was created in source folder
            if source_db:
                new_rel_path = os.path.relpath(dest_path, source_db.root_path)
                source_db.partial_update(new_rel_path, "created")
                source_db.save_to_file(str(self.database_manager.database_dir / "source.json"))
            # Update history list with the new filename and full path
            self.update_history_list(os.path.basename(dest_path), dest_path)
            # Update counts
            self.move_count += 1
            self.movecount_var.set(f"Moved: {self.move_count}")
            self.count_folders_and_files()
            return True
        except Exception as e:
            self.log(f"Error moving file {source_path}: {str(e)}")
            return False


    def handle_rename_event(self, old_path, new_path):
        """
        Remove the old file path from the move queue if present, then add the new path for subsequent moving.
        """
        try:
            if old_path in self.move_queue:
                self.move_queue.remove(old_path)
                self.log(f"Removed old path from queue: {old_path}")
            if not os.path.isdir(new_path) and new_path not in self.move_queue:
                self.move_queue.append(new_path)
                self.log(f"Queued renamed file: {os.path.basename(new_path)}")
        except Exception as e:
            self.log(f"Error handling rename event: {str(e)}")


    def _are_files_identical(self, file1, file2, chunk_size=8192):
        """Compare two files using MD5 hashes. Also checks for similar files in target directory."""
        def get_md5(filename):
            md5 = hashlib.md5()
            with open(filename, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    md5.update(chunk)
            return md5.hexdigest()

        try:
            if not self.rigorous_duplicate_check_var.get():
                # First check the file size (fast)
                if os.path.getsize(file1) == os.path.getsize(file2):
                    return True
                # Then check the MD5 hash
                elif os.path.exists(file2) and get_md5(file1) == get_md5(file2):
                    return True
            else:
                # Check similar files in the same directory as file2
                target_dir = os.path.dirname(file2)
                similar_files = self._find_similar_files(file1, target_dir)
                file1_md5 = get_md5(file1)
                for similar_file in similar_files:
                    if get_md5(similar_file) == file1_md5:
                        return True
                return False
        except Exception:
            return False


    def _find_similar_files(self, filename, target_dir):
        method = self.dupe_filter_mode_var.get()
        # Get base name and extension
        base_name = os.path.basename(filename)
        base_name_without_ext, ext = os.path.splitext(base_name)
        ext = ext.lower()
        similar_files = []
        if method == 'Strict':
            # Method B: Use regex to match base names with potential counters
            base_name_pattern = re.escape(base_name_without_ext) + r'([ _\-]\(\d+\)|[ _\-]\d+)?$'
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if os.path.isfile(full_path):
                    f_base, f_ext = os.path.splitext(f)
                    if f_ext.lower() != ext:
                        continue
                    if re.match(base_name_pattern, f_base, re.IGNORECASE):
                        similar_files.append(full_path)
            similar_files.sort(key=lambda x: SequenceMatcher(None, base_name_without_ext.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
        elif method == 'Flexible':
            # Method A: Remove unique counter suffix if applicable
            if '_' in base_name_without_ext:
                base_name_clean = '_'.join(base_name_without_ext.split('_')[:-1])
            else:
                base_name_clean = base_name_without_ext
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if os.path.isfile(full_path):
                    f_base, f_ext = os.path.splitext(f)
                    if f_ext.lower() != ext:
                        continue
                    if base_name_clean.lower() in f_base.lower():
                        similar_files.append(full_path)
            similar_files.sort(key=lambda x: SequenceMatcher(None, base_name_clean.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
        else:
            self.log(f"Invalid method '{method}' provided to _find_similar_files")
            return []
        return similar_files[:self.rigorous_dupe_max_files_var.get()]


#endregion
#region - File Logic


    def select_working_dir(self, path=None):
        if not path:
            path = filedialog.askdirectory()
            if not path:  # Cancelled dialog
                return
            path = os.path.normpath(path)
        if os.path.exists(path):
            self.working_dir_var.set(path)
            self.log(f"Selected folder: {path}")
            self.count_folders_and_files()


    def open_folder(self, path=None):
        if not path:
            path = self.working_dir_var.get()
        if os.path.exists(path):
            os.startfile(path)


    def check_working_dir_exists(self):
        path = self.working_dir_var.get()
        if not path:
            messagebox.showerror("Error", "No folder selected")
            return False
        elif not os.path.exists(path):
            messagebox.showerror("Error", "Selected folder does not exist")
            return False
        return path


    def count_folders_and_files(self):
        folder_count = 0
        file_count = 0
        for root, dirs, files in os.walk(self.working_dir_var.get()):
            folder_count += len(dirs)
            file_count += len(files)
        self.foldercount_var.set(f"Folders: {folder_count}")
        self.filecount_var.set(f"Files: {file_count}")


#endregion
#region - Help


    def open_help_window(self):
        help_text = {
            "Welcome to Folder-Funnel":
                "Folder-Funnel helps you watch a folder for new or changed files, then seamlessly moves them to a chosen folder. It's designed to keep your workspace organized and reduce clutter.\n\n"
                "The primary goal is to remove the need for manual filename conflict resolution by automatically renaming files to avoid duplicates, and by checking if files are identical before moving them.",

            "Basic Steps:":
                "**1) Select** a folder to watch from *'File' > 'Select source path...'* or via the *'Browse...'* button.\n"
                "**2) Click 'Start'** to duplicate the folder structure and begin monitoring changes.\n"
                "**3) Click 'Stop'** to remove the duplicate folder and end the process.",

            "Duplicate Handling:":
                "• **Rigorous Check**: Compares file contents using MD5 hashes to ensure files are identical.\n"
                "• **Simple Check**: Compares file sizes before moving.\n"
                "• **Duplicate Matching Mode**: Choose *'Strict'* to match filenames exactly, or *'Flexible'* to match similar filenames.",

            "Queue Timer:":
                "• New files and folders in the watch folder are queued for moving after a brief delay. This prevents partial file moves and ensures changes are grouped together.\n"
                "• The queue timer length can be adjusted under *'Options' > 'Queue Timer'*. This is the delay between moving files in the queue.\n"
                "• The timer progress bar shows the time remaining before the next batch move.\n"
                "• The timer is reset each time a new file is added to the queue.",


            "Tips & Tricks:":
                "• Right-click items in *'History'* to open or locate them quickly.\n"
                "• Clear logs or history anytime under the *Edit'* menu.\n"
                "• Check the status bar at the bottom to see progress and queue details."
        }
        self.help_window.open_window(geometry="800x700", help_text=help_text)


#endregion
#region - Framework


    def center_window(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = WINDOW_WIDTH
        window_height = WINDOW_HEIGHT
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')


    def on_closing(self):
        """Handle cleanup when closing the application"""
        # Cancel any pending timer
        if self.queue_timer:
            self.root.after_cancel(self.queue_timer)
            # Process any remaining files
            if self.move_queue:
                self.process_move_queue()
        if self.queue_timer_id:
            self.root.after_cancel(self.queue_timer_id)
            # Process any remaining files
            if self.move_queue:
                self.process_move_queue()
        self.stop_folder_watcher()
        self.root.quit()


root = tk.Tk()
app = FolderFunnelApp(root)
app.create_interface()
app.center_window()
root.mainloop()
