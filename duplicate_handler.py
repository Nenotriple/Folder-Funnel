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
from datetime import datetime

# Standard GUI
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter import scrolledtext

# Local imports
from scalable_image_label import ScalableImageLabel

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
        # Configure main dialog grid
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)

        # Main container
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure main frame grid - make results area expandable
        main_frame.grid_rowconfigure(3, weight=1)  # Results frame row
        main_frame.grid_columnconfigure(0, weight=1)

        # 1. Folder Selection (row 0)
        self.create_folder_selection_frame(main_frame)

        # 2. Scan Configuration (row 1)
        self.create_scan_config_frame(main_frame)

        # 3. Control Panel - Progress & Actions (row 2)
        self.create_control_panel_frame(main_frame)

        # 4. Results Display (row 3) - expandable
        self.create_results_frame(main_frame)

        # 5. Status Bar (row 4)
        self.create_status_bar(main_frame)

    def create_folder_selection_frame(self, parent):
        """Create the folder selection section."""
        folder_frame = ttk.Frame(parent)
        folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        folder_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(folder_frame, text="Scan Folder:").grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.folder_var = tk.StringVar(value=self.app.working_dir_var.get())
        self.selected_folder = self.folder_var.get()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, state="readonly")
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        self.browse_button = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2)

    def create_scan_config_frame(self, parent):
        """Create the scan configuration section."""
        config_frame = ttk.LabelFrame(parent, text="Scan Configuration", padding="8")
        config_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        config_frame.grid_columnconfigure(1, weight=1)
        config_frame.grid_columnconfigure(3, weight=1)

        # Row 0: Matching mode and Include subfolders
        ttk.Label(config_frame, text="Method:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.matching_mode_var = tk.StringVar(value=DuplicateMatchingMode.SIZE_ONLY)
        matching_combo = ttk.Combobox(config_frame, textvariable=self.matching_mode_var,
                                    values=[DuplicateMatchingMode.SIZE_ONLY, DuplicateMatchingMode.SIZE_AND_NAME,
                                           DuplicateMatchingMode.SIZE_AND_MD5, DuplicateMatchingMode.FULL_MD5],
                                    state="readonly", width=20)
        matching_combo.grid(row=0, column=1, sticky="w", padx=(0, 15))

        self.include_subfolders_var = tk.BooleanVar(value=True)
        include_cb = ttk.Checkbutton(config_frame, text="Include subfolders",
                                   variable=self.include_subfolders_var)
        include_cb.grid(row=0, column=2, columnspan=2, sticky="w")

        # Row 1: Minimum file size
        ttk.Label(config_frame, text="Min size (KB):").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(8, 0))
        self.min_size_var = tk.IntVar(value=1)
        min_size_spin = ttk.Spinbox(config_frame, from_=0, to=999999,
                                  textvariable=self.min_size_var, width=12)
        min_size_spin.grid(row=1, column=1, sticky="w", pady=(8, 0))

    def create_control_panel_frame(self, parent):
        """Create the control panel with scan controls, progress, and actions."""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        control_frame.grid_columnconfigure(0, weight=1)

        # Scan Controls Row
        scan_frame = ttk.Frame(control_frame)
        scan_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.scan_button = ttk.Button(scan_frame, text="Start Scan", command=self.start_scan)
        self.scan_button.pack(side="left", padx=(0, 8))

        self.cancel_button = ttk.Button(scan_frame, text="Cancel", command=self.cancel_scan, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 8))

        self.close_button = ttk.Button(scan_frame, text="Close", command=self.on_close)
        self.close_button.pack(side="right")

        # Progress Bar Row
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Action Buttons Row
        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=2, column=0, sticky="ew")
        action_frame.grid_columnconfigure(3, weight=1)

        self.delete_button = ttk.Button(action_frame, text="Delete Duplicates",
                                      command=self.delete_duplicates, state="disabled")
        self.delete_button.grid(row=0, column=0, padx=(0, 8))

        self.move_button = ttk.Button(action_frame, text="Move Duplicates",
                                    command=self.move_duplicates, state="disabled")
        self.move_button.grid(row=0, column=1, padx=(0, 8))

        self.interactive_button = ttk.Button(action_frame, text="Interactive Review",
                                           command=self.interactive_review, state="disabled")
        self.interactive_button.grid(row=0, column=2, padx=(0, 15))

        # Action status info
        self.action_info_var = tk.StringVar(value="Scan for duplicates first")
        action_info_label = ttk.Label(action_frame, textvariable=self.action_info_var,
                                    font=("TkDefaultFont", 8), foreground="gray")
        action_info_label.grid(row=0, column=3, sticky="w")

    def create_results_frame(self, parent):
        """Create the results display section."""
        results_frame = ttk.LabelFrame(parent, text="Scan Results", padding="5")
        results_frame.grid(row=3, column=0, sticky="nsew")
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)

        # Results text with scrollbar
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, height=12)
        self.results_text.grid(row=0, column=0, sticky="nsew")

    def create_status_bar(self, parent):
        """Create the status bar."""
        self.status_var = tk.StringVar(value="Ready to scan")
        status_label = ttk.Label(parent, textvariable=self.status_var,
                               font=("TkDefaultFont", 8), foreground="gray")
        status_label.grid(row=4, column=0, sticky="ew", pady=(8, 0))


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
        # Disable action buttons during scan
        self.delete_button.config(state="disabled")
        self.move_button.config(state="disabled")
        self.interactive_button.config(state="disabled")
        # Update action info to show scanning status
        self.action_info_var.set("Scanning in progress...")
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
            self.interactive_button.config(state="normal")
            self.action_info_var.set(f"{duplicate_count} duplicate files can be processed")
        else:
            self.delete_button.config(state="disabled")
            self.move_button.config(state="disabled")
            self.interactive_button.config(state="disabled")
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


    def interactive_review(self):
        """Open interactive duplicate review dialog."""
        if not self.duplicate_groups:
            messagebox.showwarning("No Duplicates", "No duplicate files to review.")
            return

        # Create and show the interactive review dialog
        review_dialog = InteractiveDuplicateReviewDialog(self.dialog, self.duplicate_groups, self.selected_folder, self.app)


    def perform_file_action(self, action: str, files: List[str], destination: str = None):
        """Perform the specified action on files with progress tracking."""
        total_files = len(files)
        success_count = 0
        error_count = 0
        errors = []
        # Disable buttons during action
        self.delete_button.config(state="disabled")
        self.move_button.config(state="disabled")
        self.interactive_button.config(state="disabled")
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
            self.interactive_button.config(state="normal")
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
            # Reset action info for error case
            self.action_info_var.set("Scan for duplicates first")


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


class InteractiveDuplicateReviewDialog:
    """Dialog for interactive review of duplicate files, focused on images and responsive layout."""

    def __init__(self, parent, duplicate_groups, selected_folder, app):
        self.parent = parent
        self.duplicate_groups = [group for group in duplicate_groups.values() if len(group) > 1]
        self.selected_folder = selected_folder
        self.app = app
        self.current_group_index = 0

        self.preview_sizes = {
            "Small": (80, 80),
            "Medium": (140, 140),
            "Large": (200, 200),
            "Extra Large": (300, 300)
        }
        self.current_preview_size = tk.StringVar(value="Medium")

        # Add variable for fast delete mode
        self.fast_delete_var = tk.BooleanVar(value=False)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Interactive Duplicate Review")
        self.dialog.geometry("1000x700")
        self.dialog.resizable(True, True)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)

        # Main layout: group info (top), image grid (center), navigation/actions (bottom)
        self.dialog.grid_rowconfigure(1, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)

        # --- Top: Group info (top), preview size, and fast delete toggle ---
        top = ttk.Frame(self.dialog, padding=(8, 4))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        top.grid_columnconfigure(2, weight=0)

        self.group_label = ttk.Label(top)
        self.group_label.grid(row=0, column=0, sticky="w", padx=(0, 12))

        preview_ctrl = ttk.Frame(top)
        preview_ctrl.grid(row=0, column=1, sticky="e")
        ttk.Label(preview_ctrl, text="Preview:").pack(side="left", padx=(0, 2))
        preview_combo = ttk.Combobox(preview_ctrl, textvariable=self.current_preview_size,
                                     values=list(self.preview_sizes.keys()), state="readonly", width=12)
        preview_combo.pack(side="left")
        preview_combo.bind("<<ComboboxSelected>>", self.on_preview_size_changed)

        # Fast delete checkbutton
        fast_delete_cb = ttk.Checkbutton(top, text="Fast delete (no confirm/success)", variable=self.fast_delete_var)
        fast_delete_cb.grid(row=0, column=2, sticky="e", padx=(16, 0))

        # --- Center: Scrollable image grid ---
        center = ttk.Frame(self.dialog)
        center.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        center.grid_rowconfigure(0, weight=1)
        center.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(center, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar = ttk.Scrollbar(center, orient="vertical", command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel_events()

        # --- Bottom: Navigation and group actions ---
        bottom = ttk.Frame(self.dialog, padding=(8, 8))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        nav = ttk.Frame(bottom)
        nav.grid(row=0, column=0, sticky="w")
        self.prev_button = ttk.Button(nav, text="◀ Prev", command=self.previous_group, width=10)
        self.prev_button.pack(side="left", padx=2)
        self.next_button = ttk.Button(nav, text="Next ▶", command=self.next_group, width=10)
        self.next_button.pack(side="left", padx=2)

        group_actions = ttk.Frame(bottom)
        group_actions.grid(row=0, column=1, sticky="e")
        ttk.Button(group_actions, text="Skip Group", command=self.skip_group, width=14).pack(side="left", padx=(0,4))
        ttk.Button(group_actions, text="Keep First, Delete Rest", command=self.delete_all_but_first, width=22).pack(side="left", padx=(0,4))
        ttk.Button(group_actions, text="Close", command=self.on_close, width=10).pack(side="left")

        self.center_dialog()
        self.show_current_group()

    def center_dialog(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        canvas_width = self.canvas.winfo_width()
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        self.show_current_group(redraw_only=True)

    def _bind_mousewheel_events(self):
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.grid_frame.bind("<MouseWheel>", _on_mousewheel)
        self.dialog.bind("<MouseWheel>", _on_mousewheel)

    def show_current_group(self, redraw_only=False):
        if not self.duplicate_groups or self.current_group_index >= len(self.duplicate_groups):
            self.on_close()
            return

        current_group = self.duplicate_groups[self.current_group_index]
        total_groups = len(self.duplicate_groups)
        self.group_label.config(text=f"Group {self.current_group_index + 1}/{total_groups} • {len(current_group)} files")
        self.prev_button.config(state="normal" if self.current_group_index > 0 else "disabled")
        self.next_button.config(state="normal" if self.current_group_index < total_groups - 1 else "disabled")

        # Clear grid if not just redrawing
        if not redraw_only:
            for widget in self.grid_frame.winfo_children():
                widget.destroy()

        # Determine columns based on window width and preview size
        width = self.dialog.winfo_width() or 1000
        img_w, img_h = self.preview_sizes[self.current_preview_size.get()]
        min_card_width = img_w + 60
        cols = max(1, width // min_card_width)

        # Place file cards in grid
        for idx, file_path in enumerate(current_group):
            row, col = divmod(idx, cols)
            self.create_file_card(self.grid_frame, file_path, idx).grid(row=row, column=col, padx=8, pady=8, sticky="n")

        self.grid_frame.update_idletasks()
        self.canvas.yview_moveto(0)

    def create_file_card(self, parent, file_path, index):
        card = ttk.Frame(parent, relief="ridge", borderwidth=1, padding=4)
        card.grid_columnconfigure(0, weight=1)

        # Image preview (top)
        if self.is_image_file(file_path):
            preview_frame = ttk.Frame(card)
            preview_frame.grid(row=0, column=0, sticky="n", pady=(0, 4))
            self.create_image_preview_compact(preview_frame, file_path)
        else:
            ttk.Label(card, text="No Preview", foreground="gray").grid(row=0, column=0, sticky="n", pady=(0, 4))

        # File info (middle)
        info_frame = ttk.Frame(card)
        info_frame.grid(row=1, column=0, sticky="ew")
        self.create_file_info_compact(info_frame, file_path)

        # Actions (bottom)
        actions_frame = ttk.Frame(card)
        actions_frame.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        self.create_action_buttons_compact(actions_frame, file_path)

        return card

    def create_file_info_compact(self, parent, file_path):
        try:
            stat = os.stat(file_path)
            file_size = stat.st_size
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            filename = os.path.basename(file_path)
            rel_path = os.path.relpath(file_path, self.selected_folder)
            # Filename (clickable, truncated if too long)
            name = filename if len(filename) <= 36 else filename[:33] + "..."
            name_label = ttk.Label(parent, text=name, foreground="blue", cursor="hand2")
            name_label.grid(row=0, column=0, sticky="w")
            name_label.bind("<Button-1>", lambda e: self.open_file_location(file_path))
            # Details
            details = f"{self.format_file_size(file_size)} • {mod_time.strftime('%m/%d/%y %H:%M')}"
            ttk.Label(parent, text=details, foreground="gray").grid(row=1, column=0, sticky="w")
            # Relative path (truncated)
            rel = rel_path if len(rel_path) <= 40 else "..." + rel_path[-37:]
            ttk.Label(parent, text=rel, foreground="gray").grid(row=2, column=0, sticky="w")
        except (OSError, IOError):
            ttk.Label(parent, text="⚠ Error reading file", foreground="red").grid(row=0, column=0, sticky="w")

    def create_image_preview_compact(self, parent, file_path):
        try:
            width, height = self.preview_sizes[self.current_preview_size.get()]
            image_label = ScalableImageLabel(parent, width=width, height=height, keep_aspect=True)
            image_label.pack()
            image_label.set_image(file_path)
            image_label.configure(cursor="hand2")
            image_label.bind("<Button-1>", lambda e: self.open_image_file(file_path))
            if hasattr(image_label, 'label'):
                image_label.label.configure(cursor="hand2")
                image_label.label.bind("<Button-1>", lambda e: self.open_image_file(file_path))
        except Exception:
            pass

    def create_action_buttons_compact(self, parent, file_path):
        ttk.Button(parent, text="Delete", width=7,
                  command=lambda: self.delete_file(file_path)).pack(side="left", padx=1)
        ttk.Button(parent, text="Move", width=6,
                  command=lambda: self.move_file(file_path)).pack(side="left", padx=1)
        ttk.Button(parent, text="Skip", width=6,
                  command=lambda: self.ignore_file(file_path)).pack(side="left", padx=1)

    def on_preview_size_changed(self, event=None):
        self.show_current_group()

    def format_file_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def is_image_file(self, file_path):
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.ico'}
        return os.path.splitext(file_path.lower())[1] in image_extensions

    def delete_file(self, file_path):
        filename = os.path.basename(file_path)
        if self.fast_delete_var.get():
            try:
                os.remove(file_path)
                self.remove_file_from_group(file_path)
                self.app.log(f"Deleted duplicate: {filename}")
                # No success message
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete file:\n{str(e)}", parent=self.dialog)
        else:
            if messagebox.askyesno("Confirm Delete", f"Delete this file?\n\n{filename}", parent=self.dialog):
                try:
                    os.remove(file_path)
                    self.remove_file_from_group(file_path)
                    self.app.log(f"Deleted duplicate: {filename}")
                    messagebox.showinfo("Success", f"Deleted: {filename}", parent=self.dialog)
                except Exception as e:
                    messagebox.showerror("Error", f"Could not delete file:\n{str(e)}", parent=self.dialog)

    def move_file(self, file_path):
        destination = filedialog.askdirectory(title="Select destination folder", parent=self.dialog)
        if destination:
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(destination, filename)
                counter = 1
                base_name, ext = os.path.splitext(dest_path)
                while os.path.exists(dest_path):
                    dest_path = f"{base_name}_{counter}{ext}"
                    counter += 1
                shutil.move(file_path, dest_path)
                self.remove_file_from_group(file_path)
                self.app.log(f"Moved duplicate: {filename}")
                messagebox.showinfo("Success", f"Moved to:\n{os.path.basename(dest_path)}", parent=self.dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Could not move file:\n{str(e)}", parent=self.dialog)

    def ignore_file(self, file_path):
        self.remove_file_from_group(file_path)

    def remove_file_from_group(self, file_path):
        current_group = self.duplicate_groups[self.current_group_index]
        if file_path in current_group:
            current_group.remove(file_path)
        if len(current_group) <= 1:
            self.duplicate_groups.pop(self.current_group_index)
            if self.current_group_index >= len(self.duplicate_groups):
                self.current_group_index = max(0, len(self.duplicate_groups) - 1)
        self.show_current_group()

    def open_file_location(self, file_path):
        try:
            if os.name == 'nt':
                os.startfile(os.path.dirname(file_path))
            elif os.name == 'posix':
                import subprocess
                if os.uname().sysname == 'Darwin':
                    subprocess.run(['open', os.path.dirname(file_path)])
                else:
                    subprocess.run(['xdg-open', os.path.dirname(file_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open location:\n{str(e)}", parent=self.dialog)

    def open_image_file(self, file_path):
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            elif os.name == 'posix':
                import subprocess
                if os.uname().sysname == 'Darwin':
                    subprocess.run(['open', file_path])
                else:
                    subprocess.run(['xdg-open', file_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image:\n{str(e)}", parent=self.dialog)

    def previous_group(self):
        if self.current_group_index > 0:
            self.current_group_index -= 1
            self.show_current_group()

    def next_group(self):
        if self.current_group_index < len(self.duplicate_groups) - 1:
            self.current_group_index += 1
            self.show_current_group()

    def skip_group(self):
        if self.current_group_index < len(self.duplicate_groups) - 1:
            self.next_group()
        else:
            self.on_close()

    def delete_all_but_first(self):
        current_group = self.duplicate_groups[self.current_group_index]
        if len(current_group) < 2:
            return
        files_to_delete = current_group[1:]
        first_file = os.path.basename(current_group[0])
        if self.fast_delete_var.get():
            deleted_count = 0
            errors = []
            for file_path in files_to_delete[:]:
                try:
                    os.remove(file_path)
                    current_group.remove(file_path)
                    deleted_count += 1
                    self.app.log(f"Deleted duplicate: {os.path.basename(file_path)}")
                except Exception as e:
                    errors.append(f"{os.path.basename(file_path)}: {str(e)}")
            self.duplicate_groups.pop(self.current_group_index)
            if self.current_group_index >= len(self.duplicate_groups):
                self.current_group_index = max(0, len(self.duplicate_groups) - 1)
            if errors:
                error_msg = f"Deleted {deleted_count} files.\n\nErrors:\n" + "\n".join(errors[:3])
                if len(errors) > 3:
                    error_msg += f"\n... and {len(errors) - 3} more"
                messagebox.showwarning("Partial Success", error_msg, parent=self.dialog)
            # No success message if no errors
            self.show_current_group()
        else:
            if messagebox.askyesno("Confirm Bulk Delete",
                                  f"Delete {len(files_to_delete)} files?\n\nKeeping: {first_file}",
                                  parent=self.dialog):
                deleted_count = 0
                errors = []
                for file_path in files_to_delete[:]:
                    try:
                        os.remove(file_path)
                        current_group.remove(file_path)
                        deleted_count += 1
                        self.app.log(f"Deleted duplicate: {os.path.basename(file_path)}")
                    except Exception as e:
                        errors.append(f"{os.path.basename(file_path)}: {str(e)}")
                self.duplicate_groups.pop(self.current_group_index)
                if self.current_group_index >= len(self.duplicate_groups):
                    self.current_group_index = max(0, len(self.duplicate_groups) - 1)
                if errors:
                    error_msg = f"Deleted {deleted_count} files.\n\nErrors:\n" + "\n".join(errors[:3])
                    if len(errors) > 3:
                        error_msg += f"\n... and {len(errors) - 3} more"
                    messagebox.showwarning("Partial Success", error_msg, parent=self.dialog)
                else:
                    messagebox.showinfo("Success", f"Deleted {deleted_count} files.", parent=self.dialog)
                self.show_current_group()

    def on_close(self):
        self.dialog.destroy()


def show_duplicate_scanner(app: 'Main'):
    """Show the duplicate scanner dialog."""
    if not app.working_dir_var.get():
        messagebox.showwarning("No Source Folder", "Please select a source folder first from File > Select Source Path...")
        return
    scanner = DuplicateScannerDialog(app.root, app)


#endregion