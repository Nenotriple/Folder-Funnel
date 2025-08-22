#region Imports


# Standard
import os
import shutil
import hashlib
import threading
import time
from collections import defaultdict
from typing import List, Dict

# Standard GUI
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter import scrolledtext

# Local imports
from .duplicate_review_dialog import InteractiveDuplicateReviewDialog
from TkToolTip import TkToolTip as Tip

# Set TkToolTip defaults
Tip.DELAY = 250
Tip.PADY = 25
Tip.ORIGIN = "widget"


# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region DuplicateScannerDialog


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
        self.duplicate_groups = {}
        self.create_dialog()


    #region GUI


    # --- Dialog Creation ---
    def create_dialog(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Duplicate File Scanner")
        self.dialog.geometry("700x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_all_widgets()
        self.center_dialog()


    # --- Center Dialog ---
    def center_dialog(self):
        self.dialog.update_idletasks()
        x = (self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2))
        y = (self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2))
        self.dialog.geometry(f"+{x}+{y}")


    # --- All Widgets ---
    def create_all_widgets(self):
        # Configure main dialog grid
        self.dialog.grid_rowconfigure(0, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)
        # Main container
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(3, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        # 1. Folder Selection (row 0)
        self.create_folder_selection_frame(main_frame)
        # 2. Scan Configuration (row 1)
        self.create_scan_config_frame(main_frame)
        # 3. Control Panel (row 2)
        self.create_control_panel_frame(main_frame)
        # 4. Results Display (row 3)
        self.create_results_frame(main_frame)
        # 5. Status Bar (row 4)
        self.create_status_bar(main_frame)


    # --- Folder Selection ---
    def create_folder_selection_frame(self, parent):
        folder_frame = ttk.Frame(parent)
        folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        folder_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(folder_frame, text="Scan Folder:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.folder_var = tk.StringVar(value=self.app.working_dir_var.get())
        self.selected_folder = self.folder_var.get()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, state="readonly")
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        Tip(self.folder_entry, "Folder to scan for duplicate files")
        self.browse_button = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2)
        Tip(self.browse_button, "Browse for folder to scan")


    # --- Scan Config ---
    def create_scan_config_frame(self, parent):
        config_frame = ttk.LabelFrame(parent, text="Scan Configuration", padding="8")
        config_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        config_frame.grid_columnconfigure(1, weight=1)
        config_frame.grid_columnconfigure(3, weight=1)
        ttk.Label(config_frame, text="Method:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.duplicate_scan_modes = {
            "SIZE_ONLY": "Size Only (Fast)",
            "SIZE_AND_NAME": "Size + Filename",
            "SIZE_AND_MD5": "Size + MD5 Hash",
            "SIZE_AND_PARTIAL_HASH": "Size + Partial Hash (Recommended)",
            "PARTIAL_HASH": "Partial Hash Only (Fastest)",
            "FULL_MD5": "Full MD5 Hash (Slowest)"
        }
        # Organize scan modes for combobox
        scan_mode_order = [
            self.duplicate_scan_modes["SIZE_ONLY"],
            self.duplicate_scan_modes["SIZE_AND_NAME"],
            self.duplicate_scan_modes["SIZE_AND_PARTIAL_HASH"],
            self.duplicate_scan_modes["PARTIAL_HASH"],
            self.duplicate_scan_modes["SIZE_AND_MD5"],
            self.duplicate_scan_modes["FULL_MD5"]
        ]
        self.matching_mode_var = tk.StringVar(value=self.duplicate_scan_modes["SIZE_AND_PARTIAL_HASH"])
        matching_combo = ttk.Combobox(config_frame, textvariable=self.matching_mode_var, values=scan_mode_order, state="readonly", width=28)
        matching_combo.grid(row=0, column=1, sticky="w", padx=(0, 15))
        Tip(matching_combo, "Choose how to match duplicate files")
        self.include_subfolders_var = tk.BooleanVar(value=True)
        include_cb = ttk.Checkbutton(config_frame, text="Include subfolders", variable=self.include_subfolders_var)
        include_cb.grid(row=0, column=2, sticky="w")
        Tip(include_cb, "Include files in subfolders during scan")
        self.same_folder_only_var = tk.BooleanVar(value=False)
        same_folder_cb = ttk.Checkbutton(config_frame, text="Match only within same folder", variable=self.same_folder_only_var)
        same_folder_cb.grid(row=1, column=2, sticky="w", padx=(0, 0))
        Tip(same_folder_cb, "Only match duplicates within the same folder")
        ttk.Label(config_frame, text="Min size (KB):").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.min_size_var = tk.IntVar(value=1)
        min_size_spin = ttk.Spinbox(config_frame, from_=0, to=999999, textvariable=self.min_size_var, width=12)
        min_size_spin.grid(row=1, column=1, sticky="w", pady=(8, 0))
        Tip(min_size_spin, "Minimum file size (in KB) to include")
        ttk.Label(config_frame, text="Max size (MB):").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.max_size_var = tk.IntVar(value=0)
        max_size_spin = ttk.Spinbox(config_frame, from_=0, to=1024*1024, textvariable=self.max_size_var, width=12)
        max_size_spin.grid(row=2, column=1, sticky="w", pady=(8, 0))
        Tip(max_size_spin, "Maximum file size (in MB) to include (0 = no max)")
        # --- File Type Filtering ---
        self.filetype_filtering_var = tk.BooleanVar(value=False)
        filetype_cb = ttk.Checkbutton(config_frame, text="Type Filtering", variable=self.filetype_filtering_var, command=self.toggle_filetype_entry)
        filetype_cb.grid(row=3, column=0, sticky="w", pady=(8, 0))
        Tip(filetype_cb, "Enabled to filter files by extensions")
        self.filetype_entry_var = tk.StringVar(value=".png, .webp, .jpg")
        self.filetype_entry = ttk.Entry(config_frame, textvariable=self.filetype_entry_var, state="disabled", width=30)
        self.filetype_entry.grid(row=3, column=1, sticky="w", pady=(8, 0), padx=(0, 5))
        Tip(self.filetype_entry, "Separate extensions with a comma and space: (.png, .webp, .jpg)")
        # --- Partial Hash Size Selection ---
        self.partial_sizes = [256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
        self.partial_size_labels = [
            "256 bytes (super fast)",
            "512 bytes",
            "1 KB",
            "2 KB",
            "4 KB (default)",
            "8 KB",
            "16 KB",
            "32 KB (most accurate)"
        ]
        self.partial_size_map = dict(zip(self.partial_size_labels, self.partial_sizes))
        self.partial_size_var = tk.StringVar(value="4 KB (default)")
        ttk.Label(config_frame, text="Partial Hash Size:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.partial_size_combo = ttk.Combobox(config_frame, textvariable=self.partial_size_var, values=self.partial_size_labels, state="readonly", width=20)
        self.partial_size_combo.grid(row=4, column=1, sticky="w", pady=(8, 0))
        Tip(self.partial_size_combo, "Partial hash size for 'Partial Hash (Fast)' mode")
        # Only enable when Partial Hash mode is selected
        def on_mode_change(*args):
            mode = self.matching_mode_var.get()
            if mode in [self.duplicate_scan_modes["PARTIAL_HASH"], self.duplicate_scan_modes["SIZE_AND_PARTIAL_HASH"]]:
                self.partial_size_combo.config(state="readonly")
            else:
                self.partial_size_combo.config(state="disabled")
        self.matching_mode_var.trace_add("write", on_mode_change)
        on_mode_change()


    def toggle_filetype_entry(self):
        if self.filetype_filtering_var.get():
            self.filetype_entry.config(state="normal")
        else:
            self.filetype_entry.config(state="disabled")


    # --- Control Panel ---
    def create_control_panel_frame(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        control_frame.grid_columnconfigure(0, weight=1)
        # Scan Controls Row
        scan_frame = ttk.Frame(control_frame)
        scan_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.scan_button = ttk.Button(scan_frame, text="Start Scan", command=self.start_scan)
        self.scan_button.pack(side="left", padx=(0, 8))
        Tip(self.scan_button, "Start scanning for duplicate files")
        self.cancel_button = ttk.Button(scan_frame, text="Cancel", command=self.cancel_scan, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 8))
        Tip(self.cancel_button, "Cancel the current scan")
        self.close_button = ttk.Button(scan_frame, text="Close", command=self.on_close)
        self.close_button.pack(side="right")
        Tip(self.close_button, "Close this dialog")
        # Progress Bar Row
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress_bar = ttk.Progressbar(control_frame, variable=self.overall_progress_var, mode='determinate')
        self.overall_progress_bar.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        self.overall_progress_bar.grid_remove()
        # Action Buttons Row
        action_frame = ttk.Frame(control_frame)
        action_frame.grid(row=4, column=0, sticky="ew")
        action_frame.grid_columnconfigure(3, weight=1)
        self.delete_button = ttk.Button(action_frame, text="Delete Duplicates", command=self.delete_duplicates, state="disabled")
        self.delete_button.grid(row=0, column=0, padx=(0, 8))
        Tip(self.delete_button, "Delete all but one file in each duplicate group")
        self.move_button = ttk.Button(action_frame, text="Move Duplicates", command=self.move_duplicates, state="disabled")
        self.move_button.grid(row=0, column=1, padx=(0, 8))
        Tip(self.move_button, "Move duplicate files to a separate folder")
        self.interactive_button = ttk.Button(action_frame, text="Interactive Review", command=self.open_interactive_review, state="disabled")
        self.interactive_button.grid(row=0, column=2, padx=(0, 15))
        Tip(self.interactive_button, "Review and process duplicates interactively")
        # Action status info
        self.action_info_var = tk.StringVar(value="Scan for duplicates first")
        action_info_label = ttk.Label(action_frame, textvariable=self.action_info_var, foreground="gray")
        action_info_label.grid(row=0, column=3, sticky="w")


    # --- Results Frame ---
    def create_results_frame(self, parent):
        results_frame = ttk.LabelFrame(parent, text="Scan Results", padding="5")
        results_frame.grid(row=3, column=0, sticky="nsew")
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        # Results text
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, height=12)
        self.results_text.grid(row=0, column=0, sticky="nsew")
        Tip(self.results_text, "Results of the duplicate scan")


    # --- Status Bar ---
    def create_status_bar(self, parent):
        self.status_var = tk.StringVar(value="Ready to scan")
        self.overall_eta_var = tk.StringVar(value="")
        status_bar_frame = ttk.Frame(parent)
        status_bar_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        status_bar_frame.grid_columnconfigure(0, weight=1)
        status_bar_frame.grid_columnconfigure(1, minsize=10)
        status_bar_frame.grid_columnconfigure(2, weight=1)
        status_label = ttk.Label(status_bar_frame, textvariable=self.status_var, foreground="gray")
        status_label.grid(row=0, column=0, sticky="w")
        Tip(status_label, "Current scan status")
        self.overall_eta_label = ttk.Label(status_bar_frame, textvariable=self.overall_eta_var, foreground="gray")
        self.overall_eta_label.grid(row=0, column=2, sticky="e")
        self.overall_eta_label.grid_remove()
        Tip(self.overall_eta_label, "Overall scan progress and ETA")


    #endregion
    #region Scan Logic


    # --- Scan Control ---
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder to scan for duplicates", initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
            self.selected_folder = folder


    def start_scan(self):
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
        self.scan_start_time = time.time()
        # Hide overall progress widgets at start
        self.overall_progress_bar.grid_remove()
        self.overall_eta_label.grid_remove()
        # Start scan in separate thread
        self.scan_thread = threading.Thread(target=self.perform_scan, daemon=True)
        self.scan_thread.start()


    def cancel_scan(self):
        self.is_scanning = False
        self.status_var.set("Cancelling scan...")


    def perform_scan(self):
        try:
            self.scan_start_time = time.time()
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
            same_folder_mode = getattr(self, "same_folder_only_var", None) and self.same_folder_only_var.get()
            if same_folder_mode:
                self.dialog.after(0, self.overall_progress_bar.grid)
                self.dialog.after(0, self.overall_eta_label.grid)
            else:
                self.dialog.after(0, self.overall_progress_bar.grid_remove)
                self.dialog.after(0, self.overall_eta_label.grid_remove)
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


    def scan_complete(self, message: str, is_error: bool = False):
        self.is_scanning = False
        self.scan_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.browse_button.config(state="normal")
        self.progress_var.set(100 if not is_error else 0)
        self.status_var.set(message)
        self.overall_eta_var.set("Done!")
        if is_error:
            messagebox.showerror("Scan Error", message)
            self.update_action_buttons(False)
            # Reset action info for error case
            self.action_info_var.set("Scan for duplicates first")


    def on_close(self):
        if self.is_scanning:
            if messagebox.askyesno("Cancel Scan", "A scan is in progress. Cancel and close?"):
                self.is_scanning = False
                if self.scan_thread and self.scan_thread.is_alive():
                    self.scan_thread.join(timeout=1.0)
            else:
                return
        self.dialog.destroy()


    # --- File Gathering ---
    def get_all_files(self) -> List[str]:
        files = []
        min_size_bytes = self.min_size_var.get() * 1024  # Min in KB -> bytes
        max_size_mb = self.max_size_var.get()
        max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb > 0 else None  # Max in MB -> bytes
        file_count = 0
        folder_count = 0
        # --- File type filtering logic ---
        filter_enabled = getattr(self, 'filetype_filtering_var', None) and self.filetype_filtering_var.get()
        allowed_exts = set()
        if filter_enabled:
            raw = self.filetype_entry_var.get()
            # Split by comma and/or space, strip, and ensure extensions start with .
            parts = [p.strip() for p in raw.replace(',', ' ').split() if p.strip()]
            allowed_exts = set()
            for ext in parts:
                if not ext.startswith('.'):
                    ext = '.' + ext
                allowed_exts.add(ext.lower())
        if self.include_subfolders_var.get():
            for root, dirs, filenames in os.walk(self.selected_folder):
                if not self.is_scanning:
                    break
                folder_count += 1
                self.status_var.set(f"Scanning for files... Folder: {os.path.relpath(root, self.selected_folder)} ({folder_count})")
                self.progress_var.set(0)
                self.app.root.update()
                for filename in filenames:
                    if not self.is_scanning:
                        break
                    filepath = os.path.join(root, filename)
                    try:
                        size = os.path.getsize(filepath)
                        # File type filter check
                        if filter_enabled:
                            ext = os.path.splitext(filename)[1].lower()
                            if ext not in allowed_exts:
                                continue
                        if size >= min_size_bytes and (max_size_bytes is None or size <= max_size_bytes):
                            files.append(filepath)
                            file_count += 1
                            if file_count % 25 == 0:
                                self.status_var.set(f"Scanning for files... {file_count} found (Current: {os.path.relpath(filepath, self.selected_folder)})")
                                self.progress_var.set(min(100, file_count / 10))
                                self.app.root.update()
                    except (OSError, IOError):
                        continue
        else:
            try:
                for filename in os.listdir(self.selected_folder):
                    if not self.is_scanning:
                        break
                    filepath = os.path.join(self.selected_folder, filename)
                    if os.path.isfile(filepath):
                        try:
                            size = os.path.getsize(filepath)
                            # File type filter check
                            if filter_enabled:
                                ext = os.path.splitext(filename)[1].lower()
                                if ext not in allowed_exts:
                                    continue
                            if size >= min_size_bytes and (max_size_bytes is None or size <= max_size_bytes):
                                files.append(filepath)
                                file_count += 1
                                if file_count % 25 == 0:
                                    self.status_var.set(f"Scanning for files... {file_count} found (Current: {os.path.relpath(filepath, self.selected_folder)})")
                                    self.progress_var.set(min(100, file_count / 10))
                                    self.app.root.update()
                        except (OSError, IOError):
                            continue
            except (OSError, IOError):
                pass
        self.status_var.set(f"Scanning for files... {file_count} found.")
        self.progress_var.set(100)
        self.app.root.update()
        return files


    # --- Duplicate Finding ---
    def _find_duplicates_by_mode(self, files: List[str], matching_mode: str, total_files: int) -> Dict[str, List[str]]:
        if matching_mode == self.duplicate_scan_modes["SIZE_ONLY"]:
            return self.find_duplicates_by_size(files, total_files)
        elif matching_mode == self.duplicate_scan_modes["SIZE_AND_NAME"]:
            return self.find_duplicates_by_size_and_name(files, total_files)
        elif matching_mode == self.duplicate_scan_modes["SIZE_AND_MD5"]:
            return self.find_duplicates_by_size_then_md5(files, total_files)
        elif matching_mode == self.duplicate_scan_modes["FULL_MD5"]:
            return self.find_duplicates_by_md5(files, total_files)
        elif matching_mode == self.duplicate_scan_modes["PARTIAL_HASH"]:
            # Get selected partial size from combobox
            selected_label = getattr(self, 'partial_size_var', None)
            if selected_label:
                size_label = self.partial_size_var.get()
                partial_size = self.partial_size_map.get(size_label, 4096)
            else:
                partial_size = 4096
            return self.find_duplicates_by_partial_hash(files, total_files, partial_size=partial_size)
        elif matching_mode == self.duplicate_scan_modes["SIZE_AND_PARTIAL_HASH"]:
            # Get selected partial size from combobox
            selected_label = getattr(self, 'partial_size_var', None)
            if selected_label:
                size_label = self.partial_size_var.get()
                partial_size = self.partial_size_map.get(size_label, 4096)
            else:
                partial_size = 4096
            return self.find_duplicates_by_size_and_partial_hash(files, total_files, partial_size=partial_size)
        else:
            return {}


    def find_duplicates(self, files: List[str]) -> Dict[str, List[str]]:
        duplicates = {}
        matching_mode = self.matching_mode_var.get()
        total_files = len(files)
        if getattr(self, "same_folder_only_var", None) and self.same_folder_only_var.get():
            duplicates = self.find_duplicates_same_folder(files, matching_mode, total_files)
        else:
            duplicates = self._find_duplicates_by_mode(files, matching_mode, total_files)
        # Filter out groups with only one file
        return {key: file_list for key, file_list in duplicates.items() if len(file_list) > 1}


    def find_duplicates_same_folder(self, files: List[str], matching_mode: str, total_files: int) -> Dict[str, List[str]]:
        folder_groups = defaultdict(list)
        for filepath in files:
            folder = os.path.dirname(filepath)
            folder_groups[folder].append(filepath)
        all_duplicates = {}
        group_idx = 0
        total_groups = len(folder_groups)
        overall_start_time = time.time()
        for folder, group_files in folder_groups.items():
            if not self.is_scanning:
                break
            # Update overall progress and ETA
            self.update_overall_progress(group_idx, total_groups, overall_start_time)
            dups = self._find_duplicates_by_mode(group_files, matching_mode, len(group_files))
            # Prefix keys with folder to avoid collisions
            for key, val in dups.items():
                all_duplicates[f"{folder}|{key}"] = val
            group_idx += 1
        # Final update to 100%
        self.update_overall_progress(total_groups, total_groups, overall_start_time)
        return all_duplicates


    def find_duplicates_by_size(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        size_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                size_groups[f"size_{size}"].append(filepath)
                if i % 10 == 0:
                    self.update_progress(i + 1, total_files, self.scan_start_time, "Checking file sizes...")
            except (OSError, IOError):
                continue
        return dict(size_groups)


    def find_duplicates_by_size_and_name(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        size_name_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                filename = os.path.basename(filepath).lower()
                key = f"size_{size}_name_{filename}"
                size_name_groups[key].append(filepath)
                if i % 10 == 0:
                    self.update_progress(i + 1, total_files, self.scan_start_time, "Checking size and names...")
            except (OSError, IOError):
                continue
        return dict(size_name_groups)


    def find_duplicates_by_size_then_md5(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        # First group by size
        size_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                size_groups[size].append(filepath)
                if i % 10 == 0:
                    self.update_progress(i + 1, total_files, self.scan_start_time, "Grouping by size...", percent=0.5)
            except (OSError, IOError):
                continue
        # Now check MD5 for groups with more than one file
        md5_groups = {}
        processed_files = 0
        files_to_hash = sum(len(group) for group in size_groups.values() if len(group) > 1)
        hash_start_time = time.time()
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
                        if processed_files % 5 == 0:
                            self.update_progress(processed_files, files_to_hash, hash_start_time, "Computing hashes...")
                    except (OSError, IOError):
                        continue
                md5_groups.update(hash_groups)
            else:
                # Single file, add with unique key
                md5_groups[f"size_{size}_single_{file_group[0]}"] = file_group
        return md5_groups


    def find_duplicates_by_md5(self, files: List[str], total_files: int) -> Dict[str, List[str]]:
        md5_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                md5_hash = self.get_md5_hash(filepath)
                md5_groups[f"md5_{md5_hash}"].append(filepath)
                if i % 5 == 0:
                    self.update_progress(i + 1, total_files, self.scan_start_time, "Computing MD5 hashes...")
            except (OSError, IOError):
                continue
        return dict(md5_groups)


    def find_duplicates_by_partial_hash(self, files: List[str], total_files: int, partial_size: int = 1024) -> Dict[str, List[str]]:
        """Find duplicates by hashing only the first partial_size bytes of each file."""
        partial_hash_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                partial_hash = self.get_partial_hash(filepath, partial_size)
                key = f"partial_{partial_size}_{partial_hash}"
                partial_hash_groups[key].append(filepath)
                if i % 10 == 0:
                    self.update_progress(i + 1, total_files, self.scan_start_time, f"Computing partial hashes ({partial_size} bytes)...")
            except (OSError, IOError):
                continue
        return dict(partial_hash_groups)


    def find_duplicates_by_size_and_partial_hash(self, files: List[str], total_files: int, partial_size: int = 4096) -> Dict[str, List[str]]:
        """Find duplicates by grouping by size, then by partial hash of the file."""
        size_groups = defaultdict(list)
        for i, filepath in enumerate(files):
            if not self.is_scanning:
                break
            try:
                size = os.path.getsize(filepath)
                size_groups[size].append(filepath)
            except (OSError, IOError):
                continue
        # Now check partial hash for groups with more than one file
        partial_hash_groups = {}
        processed_files = 0
        files_to_hash = sum(len(group) for group in size_groups.values() if len(group) > 1)
        hash_start_time = time.time()
        for size, file_group in size_groups.items():
            if not self.is_scanning:
                break
            if len(file_group) > 1:
                hash_groups = defaultdict(list)
                for filepath in file_group:
                    if not self.is_scanning:
                        break
                    try:
                        partial_hash = self.get_partial_hash(filepath, partial_size)
                        key = f"size_{size}_partial_{partial_size}_{partial_hash}"
                        hash_groups[key].append(filepath)
                        processed_files += 1
                        if processed_files % 5 == 0:
                            self.update_progress(processed_files, files_to_hash, hash_start_time, f"Computing partial hashes ({partial_size} bytes)...")
                    except (OSError, IOError):
                        continue
                partial_hash_groups.update(hash_groups)
            else:
                # Single file, add with unique key
                partial_hash_groups[f"size_{size}_single_{file_group[0]}"] = file_group
        return partial_hash_groups


    def get_partial_hash(self, filepath: str, partial_size: int = 1024) -> str:
        """Compute MD5 hash of the first partial_size bytes of a file."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            chunk = f.read(partial_size)
            hash_md5.update(chunk)
        return hash_md5.hexdigest()


    def update_overall_progress(self, current, total, start_time):
        progress = (current / total) * 100 if total else 0
        self.overall_progress_var.set(progress)
        eta = self.get_eta(current, total, start_time)
        self.overall_eta_var.set(f"Overall: {current}/{total} folders ({eta})")
        self.app.root.update()


    # --- Progress & Display ---
    def update_progress(self, current, total, start_time, status_prefix, percent=1.0):
        progress = (current / total) * (100 * percent)
        self.progress_var.set(progress)
        eta = self.get_eta(current, total, start_time, percent)
        self.status_var.set(f"{status_prefix} {current}/{total} ({eta})")
        self.app.root.update()


    def display_results(self, duplicates: Dict[str, List[str]], total_files: int):
        self.results_text.delete(1.0, tk.END)
        self.duplicate_groups = duplicates
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
        self.update_action_buttons(True, duplicate_files - duplicate_groups)


    def update_action_buttons(self, enable: bool, duplicate_count: int = 0):
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


    # --- File Actions ---
    def delete_duplicates(self):
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
        total_files = len(files)
        success_count = 0
        error_count = 0
        errors = []
        action_start_time = time.time()
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
                        self.app.log(f"Deleted duplicate: {os.path.basename(filepath)}", mode="info")
                    elif action == "move" and destination:
                        # Preserve directory structure
                        rel_path = os.path.relpath(filepath, self.selected_folder)
                        dest_path = os.path.join(destination, rel_path)
                        dest_dir = os.path.dirname(dest_path)
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.move(filepath, dest_path)
                        self.app.log(f"Moved duplicate: {os.path.basename(filepath)} -> {rel_path}", mode="info")
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    error_msg = f"{os.path.basename(filepath)}: {str(e)}"
                    errors.append(error_msg)
                progress = (i + 1) / total_files * 100
                self.progress_var.set(progress)
                action_text = "Deleting" if action == "delete" else "Moving"
                eta = self.get_eta(i + 1, total_files, action_start_time)
                self.status_var.set(f"{action_text} files... {i+1}/{total_files} ({eta})")
                self.action_info_var.set(f"{action_text}... {i+1}/{total_files} ({eta})")
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


    # --- Utility ---
    def get_md5_hash(self, filepath: str, chunk_size: int = 8192) -> str:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


    def format_file_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


    def get_eta(self, current: int, total: int, start_time: float, percent: float = 1.0) -> str:
        if current == 0:
            return "estimating..."
        elapsed = time.time() - start_time
        if elapsed < 0.1:
            return "estimating..."
        total_est = elapsed / current * (total * percent)
        remaining = max(total_est - elapsed, 0)
        if remaining < 2:
            return "less than 2s"
        mins, secs = divmod(int(remaining), 60)
        if mins:
            return f"ETA {mins}m {secs}s"
        return f"ETA {secs}s"


    def open_interactive_review(self):
        if not self.duplicate_groups:
            messagebox.showwarning("No Duplicates", "No duplicate files to review.")
            return
        # Create and show the interactive review dialog
        review_dialog = InteractiveDuplicateReviewDialog(self.dialog, self.duplicate_groups, self.selected_folder, self.app)


    #endregion


#endregion
#region show_duplicate_scanner


def show_duplicate_scanner(app: 'Main'):
    scanner = DuplicateScannerDialog(app.root, app)


#endregion