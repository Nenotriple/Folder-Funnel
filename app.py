#endregion
#region - Imports


# Standard
import os
import shutil
import threading

# Standard GUI
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Custom
from file_database import DatabaseManager


#endregion
#region - Constants


WINDOW_TITLE = "Folder-Funnel"

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 480
WINDOW_GEOMETRY = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 300

HISTORY_LIMIT = 100  # Maximum number of items in history list


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
        self.working_dir_var = tk.StringVar(value="") # The source folder
        self.status_label_var = tk.StringVar(value="Status: Idle")

        # Other Variables
        self.app_path = os.path.dirname(os.path.abspath(__file__)) # The application folder
        self.database_path = os.path.join(self.app_path, "database") # The database folder
        self.watch_path = "" # The duplicate folder that will be watched
        self.messages = [] # Log messages
        self.history_items = {}  # Store history of moved files as {filename: full_path}
        self.database_thread = None

        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize database
        self.database_manager = DatabaseManager(self, self.database_path)


    def center_window(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = WINDOW_WIDTH
        window_height = WINDOW_HEIGHT
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')


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
        # Create File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Select Folder", command=self.select_working_dir)
        self.file_menu.add_command(label="Exit", command=self.on_closing)


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

        # Create context menu
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
        # Progress bar
        self.progress_bar = ttk.Progressbar(message_frame, mode="indeterminate")
        self.progress_bar.pack(side="left", fill="x", expand=True)


#endregion
#region - GUI Logic


    def log(self, message):
        self.messages.append(message)
        self.text_log.configure(state="normal")
        self.text_log.insert("end", f"{message}\n")
        self.text_log.configure(state="disable")
        self.text_log.see("end")


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
        if not self.working_dir_var.get():
            messagebox.showerror("Error", "No folder selected")
            return
        confirm = messagebox.askokcancel("Begin Process?", "This will create a copy of the selected folder and all sub-folders (Excluding files), and begin the Folder-Funnel process.\n\nContinue?")
        if not confirm:
            return
        self.progress_bar.start()
        self.create_watch_folders()
        self.initialize_databases()
        self.database_manager.start_watching(self.watch_path)
        self.status_label_var.set("Status: Initializing")
        self.toggle_button_state(state="running")


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
        self.progress_bar.stop()


    def create_watch_folders(self):
        source_path = self.working_dir_var.get()
        source_folder_name = os.path.basename(source_path)
        parent_dir = os.path.dirname(source_path)
        watch_folder_name = f"#watching#_{source_folder_name}"
        self.watch_path = os.path.normpath(os.path.join(parent_dir, watch_folder_name))
        counter = 0
        try:
            # Create watch folder
            os.makedirs(self.watch_path, exist_ok=True)
            self.log(f"Using watch folder: {self.watch_path}")
            # Walk through the source directory
            for dirpath, dirnames, filenames in os.walk(source_path):
                # Calculate relative path from source root
                relpath = os.path.relpath(dirpath, source_path)
                # Skip if we're at the root
                if relpath == '.':
                    continue
                # Create corresponding directory in watch folder
                watch_dirpath = os.path.join(self.watch_path, relpath)
                if not os.path.exists(watch_dirpath):
                    os.makedirs(watch_dirpath)
                    counter += 1
            self.log(f"Created {counter} new directories in {self.watch_path}")
        except Exception as e:
            messagebox.showerror("Error: create_watch_folders()", f"{str(e)}")


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


    def open_folder(self, path=None):
        if not path:
            path = self.working_dir_var.get()
        if os.path.exists(path):
            os.startfile(path)


    def move_file(self, source_path):
        """Move a file from watch folder to source folder, handling filename conflicts."""
        try:
            # Get the relative path from the watch folder
            rel_path = os.path.relpath(source_path, self.watch_path)
            # Calculate the destination path in the source folder
            dest_path = os.path.join(self.working_dir_var.get(), rel_path)
            # Ensure the destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            # Handle filename conflicts
            base, ext = os.path.splitext(dest_path)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = f"{base}_{counter}{ext}"
                counter += 1
            # Move the file
            shutil.move(source_path, dest_path)
            self.log(f"Moved file: {rel_path} -> {os.path.basename(dest_path)}")
            # Update history list with the new filename and full path
            self.update_history_list(os.path.basename(dest_path), dest_path)
            return True
        except Exception as e:
            self.log(f"Error moving file {source_path}: {str(e)}")
            return False


#endregion
#region - Framework


    def on_closing(self):
        """Handle cleanup when closing the application"""
        self.stop_folder_watcher()
        self.root.quit()


root = tk.Tk()
app = FolderFunnelApp(root)
app.create_interface()
app.center_window()
root.mainloop()
