#region - Imports


# Standard
import os
import re
import sys
import time
import shutil
import ctypes
from typing import Optional

# Standard GUI
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Third-party
from watchdog.observers import Observer

# Custom
import interface
import duplicate_handler
from help_text import HELP_TEXT
from help_window import HelpWindow
from event_handler import WatchFolderHandler, SourceFolderHandler


#endregion
#region - Constants


WINDOW_TITLE = "Folder-Funnel"
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 480
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 300
HISTORY_LIMIT = 100


#endregion
#region - FolderFunnelApp


class FolderFunnelApp:
    def __init__(self, root: tk.Tk):
        self.root = root

        # tk Variables
        self.working_dir_var = tk.StringVar(value="")  # The source folder
        self.status_label_var = tk.StringVar(value="Status: Idle")  # App status
        self.foldercount_var = tk.StringVar(value="Folders: 0")  # Folder count of source folder
        self.filecount_var = tk.StringVar(value="Files: 0")  # File count of source folder
        self.movecount_var = tk.StringVar(value="Moved: 0")  # Number of files moved to source folder
        self.duplicate_count_var = tk.StringVar(value="Duplicates: 0")  # Display variable for duplicate count
        self.dupe_handle_mode_var = tk.StringVar(value="Move")  # Method for handling duplicates ("Delete", "Move")
        self.dupe_filter_mode_var = tk.StringVar(value="Strict")  # Method for finding similar files to check ("Flexible", "Strict")
        self.rigorous_duplicate_check_var = tk.BooleanVar(value=True)  # Method of checking similar files for duplicates
        self.dupe_max_files_var = tk.IntVar(value=50)  # Max files to check for duplicates
        self.move_queue_length_var = tk.IntVar(value=15000)  # Timer length (ms) for move queue
        self.text_log_wrap_var = tk.BooleanVar(value=True)  # Wrap text in log window
        self.history_mode_var = tk.StringVar(value="Moved")  # History display mode ("Moved", "Duplicate")

        # Initialize UI objects
        self.dir_entry: Optional[ttk.Entry] = None
        self.dir_entry_tooltip: Optional[tk.Widget] = None
        self.start_button: Optional[ttk.Button] = None
        self.stop_button: Optional[ttk.Button] = None
        self.text_log: Optional[scrolledtext.ScrolledText] = None
        self.history_listbox: Optional[tk.Listbox] = None
        self.history_menu: Optional[tk.Menu] = None
        self.running_indicator: Optional[ttk.Progressbar] = None
        self.queue_progressbar: Optional[ttk.Progressbar] = None

        # Other Variables
        self.app_path = self.get_app_path()  # The application folder
        self.watch_path = ""  # The duplicate folder that will be watched
        self.watch_folder_name = ""  # The name of the duplicate folder
        self.watch_name_prefix = "#FUNNEL#_"  # Prefix for the duplicate folder name
        self.duplicate_storage_path = ""  # The folder that will store moved duplicate files
        self.duplicate_name_prefix = "#DUPLICATE#_"  # Prefix for duplicate storage folder name
        self.messages = []  # Log message list
        self.move_history_items = {}  # Store history of moved files as {filename: full_path} (move path)
        self.move_count = 0  # Number of files moved
        self.duplicate_history_items = {}  # Store history of matched duplicate files as {filename: {"source": source_path, "duplicate": duplicate_path}}
        self.duplicate_count = 0  # Number of duplicate files detected

        # Queue related variables
        self.move_queue = []  # List of files waiting to be moved
        self.queue_timer_id = None  # Store timer ID for cancellation
        self.queue_start_time = None  # Store when the queue timer started

        # Observers for file watching
        self.watch_observer = None
        self.source_observer = None

        # Set up close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Help window
        self.help_window = HelpWindow(self.root)


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
        list = self.get_history_list()
        list.clear()


    def toggle_text_wrap(self):
        wrap = self.text_log_wrap_var.get()
        self.text_log.configure(wrap="word" if wrap else "none")


    def toggle_button_state(self, state="idle"):
        start = self.start_button
        stop = self.stop_button
        if state == "running":
            start.configure(state="disabled")
            stop.configure(state="normal")
        elif state == "idle":
            start.configure(state="normal")
            stop.configure(state="disabled")
        elif state == "disabled":
            start.configure(state=state)
            stop.configure(state=state)


    def toggle_indicator(self, state=None):
        if state == "start":
            self.running_indicator.configure(mode="indeterminate")
            self.running_indicator.start()
        else:
            self.running_indicator.configure(mode="determinate")
            self.running_indicator.stop()


    def open_help_window(self):
        self.help_window.open_window(geometry="800x700", help_text=HELP_TEXT)


    def update_duplicate_count(self):
        self.duplicate_count_var.set(f"Duplicates: {self.duplicate_count}")


    def get_history_list(self):
        display_mode = self.history_mode_var.get()
        if display_mode == "Moved":
            return self.move_history_items
        elif display_mode == "Duplicate":
            return self.duplicate_history_items
        return {}


#endregion
#region - Listbox Logic


    def toggle_history_mode(self):
        list = self.get_history_list()
        self.history_listbox.delete(0, "end")
        for filename in list:
            self.history_listbox.insert(0, filename)


    def update_history_list(self, filename, filepath):
        """Update the history list with a new filename and its full path."""
        list = self.get_history_list()
        # Add new item to dictionary
        list[filename] = filepath
        # Remove oldest items if limit is reached
        while len(list) > HISTORY_LIMIT:
            oldest_key = next(iter(list))
            del list[oldest_key]
        # Clear and repopulate the list widget
        self.history_listbox.delete(0, "end")
        for filename in list:
            # Insert at top to show newest first
            self.history_listbox.insert(0, filename)


    def show_history_context_menu(self, event):
        clicked_index = self.history_listbox.nearest(event.y)
        if clicked_index >= 0:
            self.history_listbox.selection_clear(0, "end")
            self.history_listbox.selection_set(clicked_index)
            self.history_listbox.activate(clicked_index)
            interface.create_history_context_menu(self)
            self.history_menu.post(event.x_root, event.y_root)


    def get_selected_filepath(self, file_type="source"):
        """
        Get the filepath of the selected item in the history listbox.

        Args:
            file_type: Either "source" or "duplicate" to indicate which file to return for duplicate entries
        """
        selection = self.history_listbox.curselection()
        if not selection:
            return None
        filename = self.history_listbox.get(selection[0])
        list = self.get_history_list()

        if self.history_mode_var.get() == "Duplicate":
            # For duplicates, return either the source or duplicate path based on file_type
            if file_type == "source":
                return list.get(filename, {}).get("source")
            else:  # duplicate
                return list.get(filename, {}).get("duplicate")
        else:
            # For moved files, return the full path as before
            return list.get(filename)


    def open_selected_file(self):
        filepath = self.get_selected_filepath()
        if filepath and os.path.exists(filepath):
            os.startfile(filepath)
        else:
            messagebox.showerror("Error", "File not found")


    def open_selected_source_file(self):
        filepath = self.get_selected_filepath(file_type="source")
        if filepath and os.path.exists(filepath):
            os.startfile(filepath)
        else:
            messagebox.showerror("Error", "Source file not found")


    def open_selected_duplicate_file(self):
        filepath = self.get_selected_filepath(file_type="duplicate")
        if filepath and os.path.exists(filepath):
            os.startfile(filepath)
        else:
            messagebox.showerror("Error", "Duplicate file not found")


    def show_selected_in_explorer(self):
        filepath = self.get_selected_filepath()
        if filepath and os.path.exists(filepath):
            os.system(f'explorer /select,"{filepath}"')
        else:
            messagebox.showerror("Error", "File not found")


    def show_selected_source_in_explorer(self):
        filepath = self.get_selected_filepath(file_type="source")
        if filepath and os.path.exists(filepath):
            os.system(f'explorer /select,"{filepath}"')
        else:
            messagebox.showerror("Error", "Source file not found")


    def show_selected_duplicate_in_explorer(self):
        filepath = self.get_selected_filepath(file_type="duplicate")
        if filepath and os.path.exists(filepath):
            os.system(f'explorer /select,"{filepath}"')
        else:
            messagebox.showerror("Error", "Duplicate file not found")


    def delete_selected_file(self):
        filepath = self.get_selected_filepath()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "File not found")
            return
        filename = os.path.basename(filepath)
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                os.remove(filepath)
                list = self.get_history_list()
                del list[filename]
                self.history_listbox.delete(self.history_listbox.curselection())
                self.log(f"Deleted file: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file: {str(e)}")


    def delete_selected_duplicate_file(self):
        filepath = self.get_selected_filepath(file_type="duplicate")
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "Duplicate file not found")
            return
        filename = os.path.basename(filepath)
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete duplicate file '{filename}'?"):
            try:
                os.remove(filepath)
                # Only remove from history if we actually want to track deleted duplicates
                # For now, we'll keep it in history but could add a flag to remove it
                self.log(f"Deleted duplicate file: {filename}")
                messagebox.showinfo("Success", f"Duplicate file deleted: {filename}")
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
        self.toggle_indicator(state="start")
        self.sync_watch_folders(silent="initial")
        self._start_folder_watcher()
        self.status_label_var.set("Status: Running")
        self.count_folders_and_files()
        self.move_count = 0
        self.movecount_var.set("Moved: 0")
        self.duplicate_count = 0
        self.update_duplicate_count()
        self.toggle_button_state(state="running")


    def _start_folder_watcher(self):
        """Start watching both the watch folder and source folder for changes"""
        # Stop any existing observers
        self._stop_folder_watcher()
        # Set up watch folder observer
        self.watch_observer = Observer()
        watch_handler = WatchFolderHandler(self)
        self.watch_observer.schedule(watch_handler, path=self.watch_path, recursive=True)
        self.watch_observer.start()
        # Set up source folder observer
        self.source_observer = Observer()
        source_handler = SourceFolderHandler(self)
        self.source_observer.schedule(source_handler, path=self.working_dir_var.get(), recursive=True)
        self.source_observer.start()
        self.log("Ready!\n")


    def stop_folder_watcher(self):
        if not (self.watch_observer or self.source_observer):
            return True
        confirm = messagebox.askokcancel("Stop Process?", "This will stop the Folder-Funnel process and remove the duplicate folder.\n\nContinue?")
        if not confirm:
            return False
        self._stop_folder_watcher()
        self.log("Stopping Folder-Funnel process...")
        self.status_label_var.set("Status: Idle")
        self.toggle_button_state(state="idle")
        if self.watch_path and os.path.exists(self.watch_path):
            shutil.rmtree(self.watch_path)
            self.log(f"Removed watch folder: {self.watch_path}")
        self.toggle_indicator(state="stop")
        return True


    def _stop_folder_watcher(self):
        """Stop all file system observers"""
        if self.watch_observer:
            self.watch_observer.stop()
            self.watch_observer.join()
            self.watch_observer = None
        if self.source_observer:
            self.source_observer.stop()
            self.source_observer.join()
            self.source_observer = None


    def sync_watch_folders(self, silent=False):
        source_path = self.working_dir_var.get()
        if not self.check_working_dir_exists():
            return
        source_folder_name = os.path.basename(source_path)
        parent_dir = os.path.dirname(source_path)
        self.watch_folder_name = f"{self.watch_name_prefix}{source_folder_name}"
        self.watch_path = os.path.normpath(os.path.join(parent_dir, self.watch_folder_name))
        counter_created = 0
        counter_removed = 0
        try:
            # Create watch folder
            os.makedirs(self.watch_path, exist_ok=True)
            if not silent:
                self.log("Initializing synced folder...")
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
            if silent in [False, "semi"]:
                self.log(f"Created: {counter_created}, Removed: {counter_removed}, directories in {self.watch_path}")
            elif silent == "initial":
                folder_count = re.split(" ", self.foldercount_var.get())
                self.log(f"Watching: {folder_count[1]} directories in {self.watch_path}")
        except Exception as e:
            messagebox.showerror("Error: create_watch_folders()", f"{str(e)}")


    def create_duplicate_storage_folder(self):
        """Create a folder to store duplicate files when in 'Move' mode."""
        source_path = self.working_dir_var.get()
        source_folder_name = os.path.basename(source_path)
        parent_dir = os.path.dirname(source_path)
        duplicate_folder_name = f"{self.duplicate_name_prefix}{source_folder_name}"
        self.duplicate_storage_path = os.path.normpath(os.path.join(parent_dir, duplicate_folder_name))
        try:
            os.makedirs(self.duplicate_storage_path, exist_ok=True)
            self.log(f"Created duplicate storage folder: {self.duplicate_storage_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create duplicate storage folder: {str(e)}")
            self.duplicate_storage_path = ""


#endregion
#region - Move/Queue Logic


    def queue_move_file(self, source_path):
        """Add a file or folder to the move queue and start/restart the timer."""
        if os.path.isdir(source_path):
            self._handle_new_folder(source_path)
        elif source_path not in self.move_queue:
            self.move_queue.append(source_path)
            self.log(f"Queued file: {os.path.relpath(source_path, self.watch_path)}")
        # Reset queue timer
        if self.queue_timer_id:
            self.root.after_cancel(self.queue_timer_id)
        # Start new timer
        self.queue_start_time = time.time() * 1000
        self.queue_progressbar['value'] = 0
        self._update_queue_progress()
        self.queue_timer_id = self.root.after(self.move_queue_length_var.get(), self.process_move_queue)


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
        except Exception as e:
            self.log(f"Error handling new folder {source_path}: {str(e)}")


    def _update_queue_progress(self):
        """Update the queue progress bar."""
        if not self.queue_start_time or not self.move_queue:
            self.queue_progressbar['value'] = 0
            return
        current_time = time.time() * 1000
        elapsed = current_time - self.queue_start_time
        progress = (elapsed / self.move_queue_length_var.get()) * 100
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
        self.log(f"Batch move complete: {success_count}/{len(self.move_queue)} files moved successfully\n")
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
            # If file exists, check if it's a duplicate
            if os.path.exists(dest_path):
                # Compare file contents
                if duplicate_handler.are_files_identical(file1=source_path, file2=dest_path, rigorous_check=self.rigorous_duplicate_check_var.get(), method=self.dupe_filter_mode_var.get(), max_files=self.dupe_max_files_var.get()):
                    # Files are identical, handle based on dupe_handle_mode
                    filename = os.path.basename(source_path)

                    if self.dupe_handle_mode_var.get() == "Delete":
                        # Delete the duplicate file
                        os.remove(source_path)
                        self.log(f"Deleted duplicate file: {rel_path}")
                    else:  # "Move" mode
                        if not self.duplicate_storage_path:
                            self.create_duplicate_storage_folder()

                        # Ensure the directory structure exists in the duplicate folder
                        rel_dir = os.path.dirname(rel_path)
                        dup_dir_path = os.path.join(self.duplicate_storage_path, rel_dir)
                        os.makedirs(dup_dir_path, exist_ok=True)

                        # Calculate destination path in duplicate storage
                        dup_file_path = os.path.join(self.duplicate_storage_path, rel_path)

                        # Handle if file already exists in duplicate storage
                        if os.path.exists(dup_file_path):
                            base, ext = os.path.splitext(dup_file_path)
                            counter = 1
                            while os.path.exists(dup_file_path):
                                dup_file_path = f"{base}_{counter}{ext}"
                                counter += 1

                        # Move the duplicate file
                        shutil.move(source_path, dup_file_path)
                        self.log(f"Moved duplicate file: {rel_path} -> {os.path.relpath(dup_file_path, self.duplicate_storage_path)}")

                    # Record the duplicate file
                    # Store both the source (kept) path and duplicate path
                    duplicate_path = source_path
                    if self.dupe_handle_mode_var.get() == "Move":
                        duplicate_path = dup_file_path

                    self.duplicate_history_items[filename] = {"source": dest_path, "duplicate": duplicate_path}
                    self.duplicate_count += 1
                    self.update_duplicate_count()
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
            self.dir_entry_tooltip.config(text=path)
            self.log(f"\nSelected folder: {path}\n")
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
#region - Framework


    def setup_window(self):
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


    def set_appid(self):
        myappid = 'ImgTxtViewer.Nenotriple'
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
        # Process any remaining files
        if self.move_queue:
            self.process_move_queue()
        if self.queue_timer_id:
            self.root.after_cancel(self.queue_timer_id)
            # Process any remaining files
            if self.move_queue:
                self.process_move_queue()
        if not self.stop_folder_watcher():
            return

        # Check if duplicate storage folder exists and ask about removal
        if self.duplicate_storage_path and os.path.exists(self.duplicate_storage_path):
            response = messagebox.askyesnocancel(
                "Remove Duplicate Files?",
                f"Do you want to remove the duplicate files folder?\n{self.duplicate_storage_path}"
            )
            if response is None:  # Cancel was selected
                return
            elif response:  # Yes was selected
                try:
                    shutil.rmtree(self.duplicate_storage_path)
                    self.log(f"Removed duplicate storage folder: {self.duplicate_storage_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to remove duplicate folder: {str(e)}")
            # If No was selected, keep the folder

        self.root.quit()


# Run the application
root = tk.Tk()
app = FolderFunnelApp(root)
interface.create_interface(app)
app.setup_window()
root.mainloop()
