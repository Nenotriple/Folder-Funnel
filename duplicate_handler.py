#region - Imports


# Standard
import os
import re
import shutil
import hashlib
import threading
from collections import defaultdict
from typing import List, Dict
from difflib import SequenceMatcher

# Standard GUI
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter import scrolledtext

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - File Operations


def are_files_identical(file1, file2, check_mode="Similar", method='Strict', max_files=10, chunk_size=8192):
    """Compare files by size/MD5 and/or check similar files in the target directory.
    Returns tuple (is_identical, matching_file_path)"""
    def get_md5(filename):
        m = hashlib.md5()
        with open(filename, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                m.update(chunk)
        return m.hexdigest()
    try:
        target_dir = os.path.dirname(file2)
        similar_files = find_similar_files(file1, target_dir, method, max_files)
        for file in similar_files:
            if os.path.exists(file) and os.path.getsize(file1) == os.path.getsize(file):
                return True, file
        if check_mode == "Similar":
            file1_md5 = get_md5(file1)
            for file in similar_files:
                if get_md5(file) == file1_md5:
                    return True, file
        elif check_mode == "Single":
            if os.path.exists(file2) and get_md5(file1) == get_md5(file2):
                return True, file2
        return False, None
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False, None


def find_similar_files(filename, target_dir, method='Strict', max_files=10) -> List[str]:
    """Return a list of files in target_dir similar to filename based on 'method'."""
    base_name = os.path.splitext(os.path.basename(filename))[0]
    ext = os.path.splitext(filename)[1].lower()
    similar_files = []
    if method == 'Strict':
        pattern = re.escape(base_name) + r'([ _\-]\(\d+\)|[ _\-]\d+)?$'
        for f in os.listdir(target_dir):
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                f_base, f_ext = os.path.splitext(f)
                if f_ext.lower() == ext and re.match(pattern, f_base, re.IGNORECASE):
                    similar_files.append(full_path)
        similar_files.sort(key=lambda x: SequenceMatcher(None, base_name.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
    elif method == 'Flexible':
        base_name_clean = base_name.rsplit('_', 1)[0] if '_' in base_name else base_name
        for f in os.listdir(target_dir):
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                f_base, f_ext = os.path.splitext(f)
                if f_ext.lower() == ext and base_name_clean.lower() in f_base.lower():
                    similar_files.append(full_path)
        similar_files.sort(key=lambda x: SequenceMatcher(None, base_name_clean.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
    return similar_files[:max_files]


def confirm_duplicate_storage_removal(app: 'Main'):
    """Ask the user if they want to remove the duplicate storage folder."""
    if app.duplicate_storage_path and os.path.exists(app.duplicate_storage_path):
        response = messagebox.askyesnocancel("Remove Duplicate Files?", f"Do you want to remove the duplicate files folder?\n{app.duplicate_storage_path}")
        if response is None:  # Cancel was selected
            return
        elif response:  # Yes was selected
            try:
                shutil.rmtree(app.duplicate_storage_path)
                app.log(f"Removed duplicate storage folder: {app.duplicate_storage_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove duplicate folder: {str(e)}")
        # If No was selected, keep the folder


def create_duplicate_storage_folder(app: 'Main'):
    """Create a folder to store duplicate files when in 'Move' mode."""
    source_path = app.working_dir_var.get()
    source_folder_name = os.path.basename(source_path)
    parent_dir = os.path.dirname(source_path)
    duplicate_folder_name = f"{app.duplicate_name_prefix}{source_folder_name}"
    app.duplicate_storage_path = os.path.normpath(os.path.join(parent_dir, duplicate_folder_name))
    try:
        os.makedirs(app.duplicate_storage_path, exist_ok=True)
        app.log(f"Created duplicate storage folder: {app.duplicate_storage_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create duplicate storage folder: {str(e)}")
        app.duplicate_storage_path = ""


#endregion
#region - Duplicate Scanning Tool


class DuplicateMatchingMode:
    """Enumeration of available duplicate matching modes."""
    SIZE_ONLY = "Size Only (Fast)"
    SIZE_AND_NAME = "Size + Filename"
    SIZE_AND_MD5 = "Size + MD5 Hash"
    FULL_MD5 = "Full MD5 Hash"


class DuplicateScannerDialog:
    """Dialog for comprehensive duplicate file scanning with configurable options."""
    def __init__(self, parent, app: 'Main'):
        self.parent = parent
        self.app = app
        self.dialog = None
        self.scan_thread = None
        self.is_scanning = False
        self.scan_results = {}
        self.selected_folder = ""
        self.duplicate_groups = {}  # Store found duplicates
        self.create_dialog()


    def create_dialog(self):
        """Create and configure the duplicate scanner dialog."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Duplicate File Scanner")
        self.dialog.geometry("700x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_widgets()
        self.center_dialog()


    def center_dialog(self):
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()
        x = (self.parent.winfo_x() + (self.parent.winfo_width() // 2) -
             (self.dialog.winfo_width() // 2))
        y = (self.parent.winfo_y() + (self.parent.winfo_height() // 2) -
             (self.dialog.winfo_height() // 2))
        self.dialog.geometry(f"+{x}+{y}")


    def create_widgets(self):
        """Create all widgets for the dialog."""
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        # Folder selection frame
        folder_frame = ttk.LabelFrame(main_frame, text="Scan Location", padding="5")
        folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        folder_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(folder_frame, text="Folder:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.folder_var = tk.StringVar(value=self.app.working_dir_var.get())
        self.selected_folder = self.folder_var.get()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, state="readonly")
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.browse_button = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2)
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Scan Options", padding="5")
        options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        options_frame.grid_columnconfigure(1, weight=1)
        # Matching mode
        ttk.Label(options_frame, text="Matching Mode:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.matching_mode_var = tk.StringVar(value=DuplicateMatchingMode.SIZE_ONLY)
        matching_combo = ttk.Combobox(options_frame, textvariable=self.matching_mode_var, values=[DuplicateMatchingMode.SIZE_ONLY, DuplicateMatchingMode.SIZE_AND_NAME, DuplicateMatchingMode.SIZE_AND_MD5, DuplicateMatchingMode.FULL_MD5], state="readonly")
        matching_combo.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        # Include subfolders
        self.include_subfolders_var = tk.BooleanVar(value=True)
        include_cb = ttk.Checkbutton(options_frame, text="Include subfolders", variable=self.include_subfolders_var)
        include_cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        # Minimum file size
        ttk.Label(options_frame, text="Min file size (KB):").grid(row=2, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.min_size_var = tk.IntVar(value=1)
        min_size_spin = ttk.Spinbox(options_frame, from_=0, to=999999, textvariable=self.min_size_var, width=10)
        min_size_spin.grid(row=2, column=1, sticky="w", pady=(5, 0))
        # Control buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        button_frame.grid_columnconfigure(0, weight=1)
        self.scan_button = ttk.Button(button_frame, text="Start Scan", command=self.start_scan)
        self.scan_button.grid(row=0, column=0, padx=(0, 5))
        self.cancel_button = ttk.Button(button_frame, text="Cancel Scan", command=self.cancel_scan, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(0, 5))
        self.close_button = ttk.Button(button_frame, text="Close", command=self.on_close)
        self.close_button.grid(row=0, column=2)
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(button_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        # Action buttons frame (new)
        action_frame = ttk.LabelFrame(main_frame, text="Actions", padding="5")
        action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        action_frame.grid_columnconfigure(2, weight=1)
        self.delete_button = ttk.Button(action_frame, text="Delete Duplicates", command=self.delete_duplicates, state="disabled")
        self.delete_button.grid(row=0, column=0, padx=(0, 5))
        self.move_button = ttk.Button(action_frame, text="Move Duplicates", command=self.move_duplicates, state="disabled")
        self.move_button.grid(row=0, column=1, padx=(0, 5))
        # Action info label
        self.action_info_var = tk.StringVar(value="Scan for duplicates first")
        action_info_label = ttk.Label(action_frame, textvariable=self.action_info_var, font=("TkDefaultFont", 8), foreground="gray")
        action_info_label.grid(row=0, column=2, sticky="w", padx=(10, 0))
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Scan Results", padding="5")
        results_frame.grid(row=4, column=0, sticky="nsew")  # Changed from row=3 to row=4
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        # Results text area
        self.results_text = scrolledtext.ScrolledText(results_frame, height=15, wrap=tk.WORD)
        self.results_text.grid(row=0, column=0, sticky="nsew")
        # Status label
        self.status_var = tk.StringVar(value="Ready to scan")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("TkDefaultFont", 8))
        status_label.grid(row=5, column=0, sticky="ew", pady=(5, 0))  # Changed from row=4 to row=5


    def browse_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(title="Select folder to scan for duplicates", initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.selected_folder = folder


    def start_scan(self):
        """Start the duplicate scanning process."""
        if not self.selected_folder or not os.path.exists(self.selected_folder):
            messagebox.showerror("Error", "Please select a valid folder to scan.")
            return
        self.is_scanning = True
        self.scan_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.browse_button.config(state="disabled")
        self.results_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        # Start scan in separate thread
        self.scan_thread = threading.Thread(target=self.perform_scan, daemon=True)
        self.scan_thread.start()


    def cancel_scan(self):
        """Cancel the current scan."""
        self.is_scanning = False
        self.status_var.set("Cancelling scan...")


    def perform_scan(self):
        """Perform the actual duplicate scan."""
        try:
            self.status_var.set("Scanning for files...")
            self.app.root.update()
            # Get all files
            all_files = self.get_all_files()
            if not all_files:
                self.dialog.after(0, lambda: self.scan_complete("No files found to scan."))
                return
            total_files = len(all_files)
            self.status_var.set(f"Found {total_files} files. Analyzing...")
            self.app.root.update()
            # Group files and find duplicates based on selected mode
            duplicates = self.find_duplicates(all_files)
            if not self.is_scanning:
                self.dialog.after(0, lambda: self.scan_complete("Scan cancelled."))
                return
            # Display results
            self.dialog.after(0, lambda: self.display_results(duplicates, total_files))
        except Exception as e:
            error_msg = f"Error during scan: {str(e)}"
            self.dialog.after(0, lambda: self.scan_complete(error_msg, is_error=True))


    def get_all_files(self) -> List[str]:
        """Get all files to be scanned."""
        files = []
        min_size_bytes = self.min_size_var.get() * 1024  # Convert KB to bytes
        if self.include_subfolders_var.get():
            for root, dirs, filenames in os.walk(self.selected_folder):
                if not self.is_scanning:
                    break
                for filename in filenames:
                    if not self.is_scanning:
                        break
                    filepath = os.path.join(root, filename)
                    try:
                        if os.path.getsize(filepath) >= min_size_bytes:
                            files.append(filepath)
                    except (OSError, IOError):
                        continue  # Skip files we can't access
        else:
            try:
                for filename in os.listdir(self.selected_folder):
                    if not self.is_scanning:
                        break
                    filepath = os.path.join(self.selected_folder, filename)
                    if os.path.isfile(filepath):
                        try:
                            if os.path.getsize(filepath) >= min_size_bytes:
                                files.append(filepath)
                        except (OSError, IOError):
                            continue
            except (OSError, IOError):
                pass
        return files


    def find_duplicates(self, files: List[str]) -> Dict[str, List[str]]:
        """Find duplicate files based on the selected matching mode."""
        duplicates = {}
        matching_mode = self.matching_mode_var.get()
        total_files = len(files)
        if matching_mode == DuplicateMatchingMode.SIZE_ONLY:
            duplicates = self.find_duplicates_by_size(files, total_files)
        elif matching_mode == DuplicateMatchingMode.SIZE_AND_NAME:
            duplicates = self.find_duplicates_by_size_and_name(files, total_files)
        elif matching_mode == DuplicateMatchingMode.SIZE_AND_MD5:
            duplicates = self.find_duplicates_by_size_then_md5(files, total_files)
        elif matching_mode == DuplicateMatchingMode.FULL_MD5:
            duplicates = self.find_duplicates_by_md5(files, total_files)
        # Filter out groups with only one file
        return {key: file_list for key, file_list in duplicates.items() if len(file_list) > 1}


    def find_duplicates_by_size(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        """Find duplicates based on file size only."""
        size_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                size_groups[f"size_{size}"].append(filepath)
                # Update progress
                progress = (i + 1) / total_files * 100
                self.progress_var.set(progress)
                if i % 10 == 0:  # Update status every 10 files
                    self.status_var.set(f"Checking file sizes... {i+1}/{total_files}")
                    self.app.root.update()
            except (OSError, IOError):
                continue
        return dict(size_groups)


    def find_duplicates_by_size_and_name(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        """Find duplicates based on file size and filename."""
        size_name_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                filename = os.path.basename(filepath).lower()
                key = f"size_{size}_name_{filename}"
                size_name_groups[key].append(filepath)
                # Update progress
                progress = (i + 1) / total_files * 100
                self.progress_var.set(progress)
                if i % 10 == 0:
                    self.status_var.set(f"Checking size and names... {i+1}/{total_files}")
                    self.app.root.update()
            except (OSError, IOError):
                continue
        return dict(size_name_groups)


    def find_duplicates_by_size_then_md5(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        """Find duplicates by first grouping by size, then checking MD5 for same-size files."""
        # First group by size
        size_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                size_groups[size].append(filepath)
                # Update progress for first pass
                progress = (i + 1) / total_files * 50  # First 50% for size grouping
                self.progress_var.set(progress)
                if i % 10 == 0:
                    self.status_var.set(f"Grouping by size... {i+1}/{total_files}")
                    self.app.root.update()
            except (OSError, IOError):
                continue
        # Now check MD5 for groups with more than one file
        md5_groups = {}
        processed_files = 0
        files_to_hash = sum(len(group) for group in size_groups.values() if len(group) > 1)
        for size, file_group in size_groups.items():
            if not self.is_scanning:
                break
            if len(file_group) > 1:  # Only check MD5 if there are potential duplicates
                hash_groups = defaultdict(list)
                for filepath in file_group:
                    if not self.is_scanning:
                        break
                    try:
                        md5_hash = self.get_md5_hash(filepath)
                        hash_groups[f"size_{size}_md5_{md5_hash}"].append(filepath)
                        processed_files += 1
                        # Update progress for second pass
                        progress = 50 + (processed_files / files_to_hash * 50)
                        self.progress_var.set(progress)
                        if processed_files % 5 == 0:
                            self.status_var.set(f"Computing hashes... {processed_files}/{files_to_hash}")
                            self.app.root.update()
                    except (OSError, IOError):
                        continue
                md5_groups.update(hash_groups)
            else:
                # Single file, add with unique key
                md5_groups[f"size_{size}_single_{file_group[0]}"] = file_group
        return md5_groups


    def find_duplicates_by_md5(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        """Find duplicates based on full MD5 hash."""
        md5_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                md5_hash = self.get_md5_hash(filepath)
                md5_groups[f"md5_{md5_hash}"].append(filepath)
                # Update progress
                progress = (i + 1) / total_files * 100
                self.progress_var.set(progress)
                if i % 5 == 0:  # Update more frequently for MD5 since it's slower
                    self.status_var.set(f"Computing MD5 hashes... {i+1}/{total_files}")
                    self.app.root.update()
            except (OSError, IOError):
                continue


        return dict(md5_groups)
    def get_md5_hash(self, filepath: str, chunk_size: int = 8192) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


    def display_results(self, duplicates: Dict[str, List[str]], total_files: int):
        """Display the scan results."""
        self.results_text.delete(1.0, tk.END)
        self.duplicate_groups = duplicates  # Store for actions
        if not duplicates:
            self.results_text.insert(tk.END, f"No duplicate files found!\n\n")
            self.results_text.insert(tk.END, f"Scanned {total_files} files in total.\n")
            self.scan_complete("Scan completed - no duplicates found.")
            self.update_action_buttons(False)
            return
        duplicate_files = sum(len(group) for group in duplicates.values())
        duplicate_groups = len(duplicates)
        self.results_text.insert(tk.END, f"DUPLICATE FILES FOUND:\n")
        self.results_text.insert(tk.END, f"{'='*50}\n\n")
        self.results_text.insert(tk.END, f"Found {duplicate_files} duplicate files in {duplicate_groups} groups.\n")
        self.results_text.insert(tk.END, f"Scanned {total_files} files total.\n\n")
        group_num = 1
        total_wasted_space = 0
        for key, file_group in duplicates.items():
            if len(file_group) <= 1:
                continue
            self.results_text.insert(tk.END, f"Group {group_num} ({len(file_group)} files):\n")
            self.results_text.insert(tk.END, f"{'-'*30}\n")
            # Calculate wasted space (size of duplicates beyond the first)
            try:
                file_size = os.path.getsize(file_group[0])
                wasted_space = file_size * (len(file_group) - 1)
                total_wasted_space += wasted_space
                self.results_text.insert(tk.END, f"File size: {self.format_file_size(file_size)}\n")
                self.results_text.insert(tk.END, f"Wasted space: {self.format_file_size(wasted_space)}\n\n")
            except (OSError, IOError):
                self.results_text.insert(tk.END, f"File size: Unable to determine\n\n")
            for filepath in file_group:
                rel_path = os.path.relpath(filepath, self.selected_folder)
                self.results_text.insert(tk.END, f"  {rel_path}\n")
            self.results_text.insert(tk.END, f"\n")
            group_num += 1
        self.results_text.insert(tk.END, f"{'='*50}\n")
        self.results_text.insert(tk.END, f"SUMMARY:\n")
        self.results_text.insert(tk.END, f"Total wasted space: {self.format_file_size(total_wasted_space)}\n")
        self.results_text.insert(tk.END, f"Matching mode used: {self.matching_mode_var.get()}\n")
        self.scan_complete(f"Scan completed - found {duplicate_groups} duplicate groups")
        self.update_action_buttons(True, duplicate_files - duplicate_groups)  # Subtract originals


    def update_action_buttons(self, enable: bool, duplicate_count: int = 0):
        """Enable or disable action buttons based on scan results."""
        if enable and duplicate_count > 0:
            self.delete_button.config(state="normal")
            self.move_button.config(state="normal")
            self.action_info_var.set(f"{duplicate_count} duplicate files can be processed")
        else:
            self.delete_button.config(state="disabled")
            self.move_button.config(state="disabled")
            if duplicate_count == 0:
                self.action_info_var.set("No duplicates found to process")
            else:
                self.action_info_var.set("Scan for duplicates first")


    def delete_duplicates(self):
        """Delete duplicate files, keeping the first file in each group."""
        if not self.duplicate_groups:
            messagebox.showwarning("No Duplicates", "No duplicate files to delete.")
            return
        # Count files to be deleted
        files_to_delete = []
        for group in self.duplicate_groups.values():
            if len(group) > 1:
                files_to_delete.extend(group[1:])  # Skip first file in each group
        if not files_to_delete:
            messagebox.showinfo("No Action Needed", "No duplicate files to delete.")
            return
        # Confirm deletion
        response = messagebox.askyesno("Confirm Delete", f"This will permanently delete {len(files_to_delete)} duplicate files.\n\nThe first file in each duplicate group will be kept.\n\nThis action cannot be undone. Continue?", icon="warning")
        if not response:
            return
        # Perform deletion
        self.perform_file_action("delete", files_to_delete)


    def move_duplicates(self):
        """Move duplicate files to a storage folder."""
        if not self.duplicate_groups:
            messagebox.showwarning("No Duplicates", "No duplicate files to move.")
            return
        # Count files to be moved
        files_to_move = []
        for group in self.duplicate_groups.values():
            if len(group) > 1:
                files_to_move.extend(group[1:])  # Skip first file in each group
        if not files_to_move:
            messagebox.showinfo("No Action Needed", "No duplicate files to move.")
            return
        # Create storage folder name
        folder_name = os.path.basename(self.selected_folder)
        parent_dir = os.path.dirname(self.selected_folder)
        storage_folder = os.path.join(parent_dir, f"Duplicates_{folder_name}")
        # Confirm move
        response = messagebox.askyesno("Confirm Move", f"This will move {len(files_to_move)} duplicate files to:\n{storage_folder}\n\nThe first file in each duplicate group will remain in place.\n\nContinue?", icon="question")
        if not response:
            return
        # Create storage folder
        try:
            os.makedirs(storage_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create storage folder:\n{str(e)}")
            return
        # Perform move
        self.perform_file_action("move", files_to_move, storage_folder)


    def perform_file_action(self, action: str, files: List[str], destination: str = None):
        """Perform the specified action on files with progress tracking."""
        total_files = len(files)
        success_count = 0
        error_count = 0
        errors = []
        # Disable buttons during action
        self.delete_button.config(state="disabled")
        self.move_button.config(state="disabled")
        self.scan_button.config(state="disabled")
        try:
            for i, filepath in enumerate(files):
                try:
                    if action == "delete":
                        os.remove(filepath)
                        self.app.log(f"Deleted duplicate: {os.path.basename(filepath)}")
                    elif action == "move" and destination:
                        # Preserve directory structure
                        rel_path = os.path.relpath(filepath, self.selected_folder)
                        dest_path = os.path.join(destination, rel_path)
                        dest_dir = os.path.dirname(dest_path)
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.move(filepath, dest_path)
                        self.app.log(f"Moved duplicate: {os.path.basename(filepath)} -> {rel_path}")
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    error_msg = f"{os.path.basename(filepath)}: {str(e)}"
                    errors.append(error_msg)
                # Update progress
                progress = (i + 1) / total_files * 100
                self.progress_var.set(progress)
                action_text = "Deleting" if action == "delete" else "Moving"
                self.status_var.set(f"{action_text} files... {i+1}/{total_files}")
                self.app.root.update()
        finally:
            # Re-enable buttons
            self.delete_button.config(state="normal")
            self.move_button.config(state="normal")
            self.scan_button.config(state="normal")
            self.progress_var.set(0)
        # Show results
        action_past = "deleted" if action == "delete" else "moved"
        message = f"Action completed!\n\n"
        message += f"Successfully {action_past}: {success_count} files\n"
        if error_count > 0:
            message += f"Errors: {error_count} files\n\n"
            if len(errors) <= 5:
                message += "Errors:\n" + "\n".join(errors)
            else:
                message += f"First 5 errors:\n" + "\n".join(errors[:5])
                message += f"\n... and {len(errors) - 5} more"
            messagebox.showwarning("Action Completed with Errors", message)
        else:
            messagebox.showinfo("Action Completed", message)
        self.status_var.set(f"Action completed - {success_count} files {action_past}")
        # Clear duplicate groups since files have been processed
        self.duplicate_groups = {}
        self.update_action_buttons(False)


    def scan_complete(self, message: str, is_error: bool = False):
        """Called when scan is complete or cancelled."""
        self.is_scanning = False
        self.scan_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.browse_button.config(state="normal")
        self.progress_var.set(100 if not is_error else 0)
        self.status_var.set(message)
        if is_error:
            messagebox.showerror("Scan Error", message)
            self.update_action_buttons(False)


    def on_close(self):
        """Handle dialog close event."""
        if self.is_scanning:
            if messagebox.askyesno("Cancel Scan", "A scan is in progress. Cancel and close?"):
                self.is_scanning = False
                if self.scan_thread and self.scan_thread.is_alive():
                    self.scan_thread.join(timeout=1.0)
            else:
                return
        self.dialog.destroy()


def show_duplicate_scanner(app: 'Main'):
    """Show the duplicate scanner dialog."""
    if not app.working_dir_var.get():
        messagebox.showwarning("No Source Folder", "Please select a source folder first from File > Select Source Path...")
        return
    scanner = DuplicateScannerDialog(app.root, app)


#endregion