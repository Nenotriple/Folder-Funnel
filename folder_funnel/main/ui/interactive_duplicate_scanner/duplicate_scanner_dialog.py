#region Imports


# Standard
import os
import time
import shutil
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Standard GUI
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter import scrolledtext

# Third-party
import nenotk as ntk
from nenotk import ToolTip as Tip

# Local imports
from .duplicate_review_dialog import InteractiveDuplicateReviewDialog
from main.utils.duplicate_handler import get_md5 as cached_get_md5

# Type checking
from typing import TYPE_CHECKING, List, Dict, Tuple, Union
if TYPE_CHECKING:
    from app import Main


#endregion
#region ScanStage Classes


class ScanStage(ABC):
    """
    Abstract base class for modular scan pipeline stages.

    Each stage takes groups of files and refines them by adding criteria to the grouping key.
    Stages can be chained in any order to create custom scanning pipelines.
    """
    name: str = "Base Stage"
    key_prefix: str = "base"


    def __init__(self, scanner: 'DuplicateScannerDialog', step_num: int, total_steps: int):
        self.scanner = scanner
        self.step_num = step_num
        self.total_steps = total_steps


    @abstractmethod
    def process(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        """
        Process file groups and return refined groups.

        Args:
            groups: Dict mapping group key tuples to lists of (filepath, size) tuples.
                   Initial input is {(): [(filepath, size), ...]} containing all files.

        Returns:
            Dict with refined group keys, filtering out singleton groups.
        """
        pass


    def _filter_singletons(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        """Remove groups with only one file (not duplicates)."""
        return {key: files for key, files in groups.items() if len(files) > 1}


    def _get_status_prefix(self) -> str:
        """Get status prefix showing current step in pipeline."""
        return f"Step {self.step_num}/{self.total_steps}: {self.name}"


#endregion
#region SizeStage


class SizeStage(ScanStage):
    """Group files by size."""
    name = "Size"
    key_prefix = "size"

    def process(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        new_groups = defaultdict(list)
        total_files = sum(len(files) for files in groups.values())
        processed = 0
        start_time = time.time()
        last_update_time = start_time
        for base_key, files in groups.items():
            if not self.scanner.is_scanning:
                break
            for filepath, size in files:
                if not self.scanner.is_scanning:
                    break
                # Append size to existing key
                new_key = base_key + (self.key_prefix, size)
                new_groups[new_key].append((filepath, size))
                processed += 1
                # Time-based progress throttling (every 200ms)
                current_time = time.time()
                if current_time - last_update_time >= 0.2:
                    unique_groups = len(new_groups)
                    self.scanner.update_progress(processed, total_files, start_time, f"{self._get_status_prefix()} | {unique_groups:,} unique sizes |")
                    last_update_time = current_time
        return self._filter_singletons(dict(new_groups))


#endregion
#region NameStage


class NameStage(ScanStage):
    """Group files by filename (case-insensitive)."""
    name = "Filename"
    key_prefix = "name"


    def process(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        new_groups = defaultdict(list)
        total_files = sum(len(files) for files in groups.values())
        processed = 0
        start_time = time.time()
        last_update_time = start_time
        for base_key, files in groups.items():
            if not self.scanner.is_scanning:
                break
            for filepath, size in files:
                if not self.scanner.is_scanning:
                    break
                filename = os.path.basename(filepath).lower()
                new_key = base_key + (self.key_prefix, filename)
                new_groups[new_key].append((filepath, size))
                processed += 1
                current_time = time.time()
                if current_time - last_update_time >= 0.2:
                    unique_groups = len(new_groups)
                    self.scanner.update_progress(processed, total_files, start_time, f"{self._get_status_prefix()} | {unique_groups:,} unique names |")
                    last_update_time = current_time
        return self._filter_singletons(dict(new_groups))


#endregion
#region PartialHashStage


class PartialHashStage(ScanStage):
    """Group files by partial MD5 hash (first N bytes)."""
    name = "Partial Hash"
    key_prefix = "partial"


    def __init__(self, scanner: 'DuplicateScannerDialog', step_num: int, total_steps: int, partial_size: int = 4096):
        super().__init__(scanner, step_num, total_steps)
        self.partial_size = partial_size


    def process(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        # Flatten groups to get files to hash
        files_to_hash = []
        for base_key, files in groups.items():
            for filepath, size in files:
                files_to_hash.append((base_key, filepath, size))
        if not files_to_hash:
            return {}
        partial_size_str = self.scanner.format_file_size(self.partial_size)
        self.scanner._update_status(f"{self._get_status_prefix()} | Hashing {len(files_to_hash):,} files (first {partial_size_str})...")
        # Use parallel hashing
        hash_input = [((base_key, size), filepath) for base_key, filepath, size in files_to_hash]
        hash_results = self.scanner._hash_files_parallel(hash_input, partial_size=self.partial_size, status_prefix=f"{self._get_status_prefix()} |")
        # Group by hash
        new_groups = defaultdict(list)
        for filepath, (context, hash_value) in hash_results.items():
            base_key, size = context
            new_key = base_key + (self.key_prefix, self.partial_size, hash_value)
            new_groups[new_key].append((filepath, size))
        return self._filter_singletons(dict(new_groups))


#endregion
#region FullMD5Stage


class FullMD5Stage(ScanStage):
    """Group files by full MD5 hash."""
    name = "Full MD5"
    key_prefix = "md5"


    def process(self, groups: Dict[tuple, List[Tuple[str, int]]]) -> Dict[tuple, List[Tuple[str, int]]]:
        # Flatten groups to get files to hash
        files_to_hash = []
        total_size = 0
        for base_key, files in groups.items():
            for filepath, size in files:
                files_to_hash.append((base_key, filepath, size))
                total_size += size
        if not files_to_hash:
            return {}
        total_size_str = self.scanner.format_file_size(total_size)
        self.scanner._update_status(f"{self._get_status_prefix()} | Hashing {len(files_to_hash):,} files ({total_size_str})...")
        # Use parallel hashing with partial_size=0 for full hash
        hash_input = [((base_key, size), filepath) for base_key, filepath, size in files_to_hash]
        hash_results = self.scanner._hash_files_parallel(hash_input, partial_size=0, status_prefix=f"{self._get_status_prefix()} |")
        # Group by hash
        new_groups = defaultdict(list)
        for filepath, (context, hash_value) in hash_results.items():
            base_key, size = context
            new_key = base_key + (self.key_prefix, hash_value)
            new_groups[new_key].append((filepath, size))
        return self._filter_singletons(dict(new_groups))


# Registry of available scan stages
SCAN_STAGE_REGISTRY: Dict[str, type] = {
    "None": None,
    "Size": SizeStage,
    "Filename": NameStage,
    "Partial Hash": PartialHashStage,
    "Full MD5": FullMD5Stage,
}


#endregion
#region DuplicateScannerDialog


class DuplicateScannerDialog:
    """Dialog for comprehensive duplicate file scanning with configurable options."""
    def __init__(self, parent, app: 'Main'):
        self.parent = parent
        self.app = app
        self.dialog = None
        self.scan_thread = None
        self._scan_lock = threading.Lock()  # Lock for thread-safe access to shared state
        self._is_scanning = False
        self.scan_results = {}
        self.selected_folder = ""
        self.duplicate_groups = {}
        self._hash_executor = None  # ThreadPoolExecutor for parallel hashing
        self._eta_tracker = None  # Rolling ETA tracker for accurate estimates
        self.create_dialog()


    @property
    def is_scanning(self) -> bool:
        """Thread-safe getter for scanning state."""
        with self._scan_lock:
            return self._is_scanning


    @is_scanning.setter
    def is_scanning(self, value: bool) -> None:
        """Thread-safe setter for scanning state."""
        with self._scan_lock:
            self._is_scanning = value


#endregion
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
        self.folder_var = tk.StringVar(value=self.app.source_dir_var.get())
        self.selected_folder = self.folder_var.get()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, state="readonly")
        self.folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ntk.bind_helpers(self.folder_entry)
        Tip(widget=self.folder_entry, text="Folder to scan for duplicate files", widget_anchor="sw", pady=2)
        self.browse_button = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2)
        Tip(widget=self.browse_button, text="Browse for folder to scan", widget_anchor="sw", pady=2)


    # --- Scan Config ---
    def create_scan_config_frame(self, parent):
        config_frame = ttk.LabelFrame(parent, text="Scan Configuration", padding="8")
        config_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        config_frame.grid_columnconfigure(1, weight=1)
        config_frame.grid_columnconfigure(3, weight=1)
        # --- Pipeline Step Selection (4 comboboxes) ---
        pipeline_frame = ttk.Frame(config_frame)
        pipeline_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(pipeline_frame, text="Scan Pipeline:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        # Available stage options
        self.stage_options = list(SCAN_STAGE_REGISTRY.keys())  # ["None", "Size", "Filename", "Partial Hash", "Full MD5"]
        # Create 4 step variables and comboboxes
        self.step_vars: List[tk.StringVar] = []
        self.step_combos: List[ttk.Combobox] = []
        # Default pipeline: Size → Partial Hash (similar to recommended mode)
        default_steps = ["Size", "Partial Hash", "None", "None"]
        steps_frame = ttk.Frame(pipeline_frame)
        steps_frame.grid(row=0, column=1, sticky="w")
        for i in range(4):
            step_var = tk.StringVar(value=default_steps[i])
            self.step_vars.append(step_var)
            # Label for step
            ttk.Label(steps_frame, text=f"{i+1}:").grid(row=0, column=i*2, sticky="w", padx=(10 if i > 0 else 0, 2))
            # Combobox for step
            step_combo = ttk.Combobox(steps_frame, textvariable=step_var, values=self.stage_options, state="readonly", width=12)
            step_combo.grid(row=0, column=i*2+1, sticky="w", padx=(0, 5))
            self.step_combos.append(step_combo)
            Tip(widget=step_combo, text=f"Step {i+1} of the scan pipeline. Select 'None' to skip.", tooltip_anchor="sw", pady=-2)
        # Bind trace to update partial hash size visibility
        for step_var in self.step_vars:
            step_var.trace_add("write", self._on_pipeline_change)
        # --- Checkboxes row ---
        self.include_subfolders_var = tk.BooleanVar(value=True)
        include_cb = ttk.Checkbutton(config_frame, text="Include subfolders", variable=self.include_subfolders_var)
        include_cb.grid(row=1, column=2, sticky="w")
        Tip(widget=include_cb, text="Include files in subfolders during scan", tooltip_anchor="sw", pady=-2)
        self.same_folder_only_var = tk.BooleanVar(value=False)
        same_folder_cb = ttk.Checkbutton(config_frame, text="Match only within same folder", variable=self.same_folder_only_var)
        same_folder_cb.grid(row=2, column=2, sticky="w", padx=(0, 0))
        Tip(widget=same_folder_cb, text="Only match duplicates within the same folder", tooltip_anchor="sw", pady=-2)
        # --- Size filters ---
        ttk.Label(config_frame, text="Min size (KB):").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.min_size_var = tk.IntVar(value=1)
        min_size_spin = ttk.Spinbox(config_frame, from_=0, to=999999, textvariable=self.min_size_var, width=12)
        min_size_spin.grid(row=1, column=1, sticky="w", pady=(8, 0))
        Tip(widget=min_size_spin, text="Minimum file size (in KB) to include", tooltip_anchor="sw", pady=-2)
        ttk.Label(config_frame, text="Max size (MB):").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        self.max_size_var = tk.IntVar(value=0)
        max_size_spin = ttk.Spinbox(config_frame, from_=0, to=1024*1024, textvariable=self.max_size_var, width=12)
        max_size_spin.grid(row=2, column=1, sticky="w", pady=(8, 0))
        Tip(widget=max_size_spin, text="Maximum file size (in MB) to include (0 = no max)", tooltip_anchor="sw", pady=-2)
        # --- File Type Filtering ---
        self.filetype_filtering_var = tk.BooleanVar(value=False)
        filetype_cb = ttk.Checkbutton(config_frame, text="Type Filtering", variable=self.filetype_filtering_var, command=self.toggle_filetype_entry)
        filetype_cb.grid(row=3, column=0, sticky="w", pady=(8, 0))
        Tip(widget=filetype_cb, text="Enabled to filter files by extensions", tooltip_anchor="sw", pady=-2)
        self.filetype_entry_var = tk.StringVar(value=".png, .webp, .jpg")
        self.filetype_entry = ttk.Entry(config_frame, textvariable=self.filetype_entry_var, state="disabled", width=30)
        self.filetype_entry.grid(row=3, column=1, sticky="w", pady=(8, 0), padx=(0, 5))
        ntk.bind_helpers(self.filetype_entry)
        Tip(widget=self.filetype_entry, text="Separate extensions with a comma and space: (.png, .webp, .jpg)", tooltip_anchor="sw", pady=-2)
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
        Tip(widget=self.partial_size_combo, text="Partial hash size for 'Partial Hash' stages in the pipeline", tooltip_anchor="sw", pady=-2)
        # Initial update of partial hash size visibility
        self._on_pipeline_change()


    def _on_pipeline_change(self, *args):
        """Update UI when pipeline configuration changes (e.g., show/hide partial hash size)."""
        # Check if any step uses Partial Hash
        uses_partial_hash = any(var.get() == "Partial Hash" for var in self.step_vars)
        if uses_partial_hash:
            self.partial_size_combo.config(state="readonly")
        else:
            self.partial_size_combo.config(state="disabled")


    def _get_active_stages(self) -> List[str]:
        """Get list of active (non-None) stage names from the pipeline configuration."""
        return [var.get() for var in self.step_vars if var.get() != "None"]


    def _build_pipeline(self) -> List[ScanStage]:
        """Build the scan pipeline from current step selections."""
        active_stages = self._get_active_stages()
        total_steps = len(active_stages)
        pipeline = []
        # Get partial hash size for PartialHashStage
        partial_size = self.partial_size_map.get(self.partial_size_var.get(), 4096)
        for i, stage_name in enumerate(active_stages, start=1):
            stage_class = SCAN_STAGE_REGISTRY.get(stage_name)
            if stage_class is None:
                continue
            if stage_class == PartialHashStage:
                stage = stage_class(self, i, total_steps, partial_size=partial_size)
            else:
                stage = stage_class(self, i, total_steps)
            pipeline.append(stage)
        return pipeline


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
        Tip(widget=self.scan_button, text="Start scanning for duplicate files", tooltip_anchor="sw", pady=-2)
        self.cancel_button = ttk.Button(scan_frame, text="Cancel", command=self.cancel_scan, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 8))
        Tip(widget=self.cancel_button, text="Cancel the current scan", tooltip_anchor="sw", pady=-2)
        self.close_button = ttk.Button(scan_frame, text="Close", command=self.on_close)
        self.close_button.pack(side="right")
        Tip(widget=self.close_button, text="Close this dialog", tooltip_anchor="sw", pady=-2)
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
        Tip(widget=self.delete_button, text="Delete all but one file in each duplicate group", tooltip_anchor="sw", pady=-2)
        self.move_button = ttk.Button(action_frame, text="Move Duplicates", command=self.move_duplicates, state="disabled")
        self.move_button.grid(row=0, column=1, padx=(0, 8))
        Tip(widget=self.move_button, text="Move duplicate files to a separate folder", tooltip_anchor="sw", pady=-2)
        self.interactive_button = ttk.Button(action_frame, text="Interactive Review", command=self.open_interactive_review, state="disabled")
        self.interactive_button.grid(row=0, column=2, padx=(0, 15))
        Tip(widget=self.interactive_button, text="Review and process duplicates interactively", tooltip_anchor="sw", pady=-2)
        # Action status info
        self.action_info_var = tk.StringVar(value="Scan for duplicates first")
        action_info_label = ttk.Label(action_frame, textvariable=self.action_info_var, foreground="gray")
        action_info_label.grid(row=0, column=3, sticky="w")


    # --- Results Frame ---
    def create_results_frame(self, parent):
        results_frame = ttk.LabelFrame(parent, text="Scan Results", padding="5")
        results_frame.grid(row=3, column=0, sticky="nsew")
        results_frame.grid_rowconfigure(1, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        # Results text
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, height=12)
        self.results_text.grid(row=1, column=0, sticky="nsew")
        Tip(widget=self.results_text, text="Results of the duplicate scan", tooltip_anchor="sw", pady=-2)
        # Search
        text_search = ntk.FindReplaceEntry(results_frame, self.results_text, show_replace=False)
        text_search.grid(row=0, column=0, sticky="ew")
        text_search.grid_remove()
        # Bind keyboard shortcuts from the text widget to the find/replace widget
        self.results_text.bind("<Control-f>", text_search.show_widget)
        self.results_text.bind("<KeyRelease>", text_search.perform_search)
        self.results_text.bind("<Escape>", text_search.hide_widget)


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
        Tip(widget=status_label, text="Current scan status", tooltip_anchor="sw", pady=-2)
        self.overall_eta_label = ttk.Label(status_bar_frame, textvariable=self.overall_eta_var, foreground="gray")
        self.overall_eta_label.grid(row=0, column=2, sticky="e")
        self.overall_eta_label.grid_remove()
        Tip(widget=self.overall_eta_label, text="Overall scan progress and ETA", tooltip_anchor="sw", pady=-2)


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
        # Validate pipeline has at least one active stage
        active_stages = self._get_active_stages()
        if not active_stages:
            messagebox.showerror("Error", "Please select at least one scan method in the pipeline.")
            return
        self.is_scanning = True
        self._set_scan_buttons_state(scanning=True)
        self._set_action_buttons_state(enabled=False)
        self.action_info_var.set("Scanning in progress...")
        self.results_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        self.scan_start_time = time.time()
        self._eta_tracker = None  # Reset ETA tracker for new scan
        # Hide overall progress widgets at start
        self.overall_progress_bar.grid_remove()
        self.overall_eta_label.grid_remove()
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start(10)
        # Start scan in separate thread
        self.scan_thread = threading.Thread(target=self.perform_scan, daemon=True)
        self.scan_thread.start()


    def cancel_scan(self):
        self.is_scanning = False
        self.status_var.set("Cancelling scan...")


    def perform_scan(self):
        try:
            self.scan_start_time = time.time()
            self._update_status("Discovering files...")
            # Get all files with cached sizes: List[(filepath, size)]
            files_with_sizes = self.get_all_files()
            # Stop indeterminate animation and switch to determinate mode
            self.dialog.after(0, self._switch_to_determinate_progress)
            if not files_with_sizes:
                self.dialog.after(0, lambda: self.scan_complete("No files found to scan."))
                return
            total_files = len(files_with_sizes)
            # Calculate total size from cached sizes (no extra stat calls)
            total_size = sum(size for _, size in files_with_sizes)
            total_size_str = self.format_file_size(total_size)
            # Get pipeline description for status
            active_stages = self._get_active_stages()
            pipeline_desc = " → ".join(active_stages)
            self._update_status(f"Found {total_files:,} files ({total_size_str}). Pipeline: {pipeline_desc}")
            same_folder_mode = getattr(self, "same_folder_only_var", None) and self.same_folder_only_var.get()
            if same_folder_mode:
                self.dialog.after(0, self.overall_progress_bar.grid)
                self.dialog.after(0, self.overall_eta_label.grid)
                # Count unique folders for same-folder mode
                unique_folders = len(set(os.path.dirname(fp) for fp, _ in files_with_sizes))
                self._update_status(f"Analyzing {total_files:,} files across {unique_folders:,} folders...")
            else:
                self.dialog.after(0, self.overall_progress_bar.grid_remove)
                self.dialog.after(0, self.overall_eta_label.grid_remove)
            # Reset analysis start time for accurate ETA during duplicate finding
            self.analysis_start_time = time.time()
            # Group files and find duplicates using the modular pipeline
            duplicates = self.find_duplicates(files_with_sizes)
            if not self.is_scanning:
                self.dialog.after(0, lambda: self.scan_complete("Scan cancelled."))
                return
            # Display results
            self.dialog.after(0, lambda: self.display_results(duplicates, total_files))
        except Exception as e:
            error_msg = f"Error during scan: {str(e)}"
            self.dialog.after(0, lambda: self.scan_complete(error_msg, is_error=True))
        finally:
            # Clean up thread pool executor
            if self._hash_executor:
                self._hash_executor.shutdown(wait=False)
                self._hash_executor = None


    def _switch_to_determinate_progress(self) -> None:
        """Switch progress bar from indeterminate to determinate mode."""
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_var.set(0)


    def _update_status(self, message: str) -> None:
        """Thread-safe status update via dialog.after()."""
        self.dialog.after(0, lambda: self.status_var.set(message))


    def _update_progress(self, value: float) -> None:
        """Thread-safe progress update via dialog.after()."""
        self.dialog.after(0, lambda: self.progress_var.set(value))


    def _update_overall_progress(self, value: float) -> None:
        """Thread-safe overall progress update via dialog.after()."""
        self.dialog.after(0, lambda: self.overall_progress_var.set(value))


    def _update_overall_eta(self, message: str) -> None:
        """Thread-safe overall ETA update via dialog.after()."""
        self.dialog.after(0, lambda: self.overall_eta_var.set(message))


    def _validate_file_exists(self, filepath: str) -> bool:
        """Check if file exists and log warning if not. Returns True if file exists."""
        if not os.path.exists(filepath):
            self.app.log(f"File no longer exists: {filepath}", mode="warning")
            return False
        return True


    def _set_scan_buttons_state(self, scanning: bool) -> None:
        """Set button states based on whether a scan is in progress."""
        scan_state = "disabled" if scanning else "normal"
        cancel_state = "normal" if scanning else "disabled"
        self.scan_button.config(state=scan_state)
        self.cancel_button.config(state=cancel_state)
        self.browse_button.config(state=scan_state)


    def _set_action_buttons_state(self, enabled: bool) -> None:
        """Enable or disable all action buttons."""
        state = "normal" if enabled else "disabled"
        self.delete_button.config(state=state)
        self.move_button.config(state=state)
        self.interactive_button.config(state=state)


    def _group_files_by_size(self, files_with_sizes: List[Tuple[str, int]], total_files: int, status_prefix: str, progress_weight: float = 1.0) -> Dict[int, List[str]]:
        """Group files by size with progress updates. Returns dict of size -> [filepaths]."""
        size_groups = defaultdict(list)
        start_time = getattr(self, 'analysis_start_time', time.time())
        last_update_time = start_time
        for i, (filepath, size) in enumerate(files_with_sizes):
            if not self.is_scanning:
                break
            size_groups[size].append(filepath)
            # Time-based progress throttling (every 200ms)
            current_time = time.time()
            if current_time - last_update_time >= 0.2:
                unique_sizes = len(size_groups)
                self.update_progress(i + 1, total_files, start_time, f"{status_prefix} {unique_sizes:,} unique sizes |", percent=progress_weight)
                last_update_time = current_time
        return dict(size_groups)


    def _hash_files_parallel(self, files_with_context: List[tuple], partial_size: int, status_prefix: str) -> Dict[str, tuple]:
        """
        Hash files in parallel using ThreadPoolExecutor.

        Args:
            files_with_context: List of (context_data, filepath) tuples. Context is returned with hash result.
            partial_size: Bytes to hash (0 for full hash).
            status_prefix: Status message prefix for progress updates.

        Returns:
            Dict of {filepath: (context_data, hash_value)} for successful hashes.
        """
        if not files_with_context:
            return {}
        # Dynamic thread pool sizing based on CPU count (I/O bound, so more than CPU count)
        max_workers = min(32, (os.cpu_count() or 4) + 4)
        self._hash_executor = ThreadPoolExecutor(max_workers=max_workers)
        hash_results = {}
        futures = {}
        for context_data, filepath in files_with_context:
            if not self.is_scanning:
                break
            if not self._validate_file_exists(filepath):
                continue
            future = self._hash_executor.submit(self._compute_hash_safe, filepath, partial_size)
            futures[future] = (context_data, filepath)
        hash_start_time = time.time()
        last_update_time = hash_start_time
        processed = 0
        total_to_hash = len(futures)
        unique_hashes = set()
        for future in as_completed(futures):
            if not self.is_scanning:
                break
            context_data, filepath = futures[future]
            try:
                hash_value = future.result()
                if hash_value:
                    hash_results[filepath] = (context_data, hash_value)
                    unique_hashes.add(hash_value)
            except Exception as e:
                self.app.log(f"Error hashing {filepath}: {e}", mode="warning")
            processed += 1
            # Time-based progress throttling (every 200ms)
            current_time = time.time()
            if current_time - last_update_time >= 0.2:
                self.update_progress(processed, total_to_hash, hash_start_time, f"{status_prefix} {len(unique_hashes):,} unique |")
                last_update_time = current_time
        return hash_results


    def scan_complete(self, message: str, is_error: bool = False):
        self.is_scanning = False
        self._set_scan_buttons_state(scanning=False)
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
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
                # Shutdown executor if running
                if self._hash_executor:
                    self._hash_executor.shutdown(wait=False)
                    self._hash_executor = None
                if self.scan_thread and self.scan_thread.is_alive():
                    self.scan_thread.join(timeout=1.0)
            else:
                return
        self.dialog.destroy()


    # --- File Gathering ---
    def get_all_files(self) -> List[Tuple[str, int]]:
        """Gather all files with their sizes. Returns List[(filepath, size)]."""
        files = []  # List of (filepath, size) tuples
        min_size_bytes = self.min_size_var.get() * 1024  # Min in KB -> bytes
        max_size_mb = self.max_size_var.get()
        max_size_bytes = max_size_mb * 1024 * 1024 if max_size_mb > 0 else None  # Max in MB -> bytes
        file_count = 0
        folder_count = 0
        error_count = 0
        last_update_time = time.time()
        # --- File type filtering logic ---
        filter_enabled = getattr(self, 'filetype_filtering_var', None) and self.filetype_filtering_var.get()
        allowed_exts = set()
        if filter_enabled:
            raw = self.filetype_entry_var.get()
            # Split by comma and/or space, strip, and ensure extensions start with .
            parts = [p.strip() for p in raw.replace(',', ' ').split() if p.strip()]
            for ext in parts:
                if not ext.startswith('.'):
                    ext = '.' + ext
                allowed_exts.add(ext.lower())
        if self.include_subfolders_var.get():
            # Initialize counters for recursive scan
            self._folder_count = 0
            self._error_count = 0
            # Use os.scandir recursively for better performance
            self._scan_directory_recursive(self.selected_folder, files, min_size_bytes, max_size_bytes,
                                           filter_enabled, allowed_exts, last_update_time)
            file_count = len(files)
            error_count = self._error_count
        else:
            # Single folder scan using os.scandir
            try:
                with os.scandir(self.selected_folder) as entries:
                    for entry in entries:
                        if not self.is_scanning:
                            break
                        if entry.is_file(follow_symlinks=False):
                            # Check extension BEFORE stat call to avoid unnecessary I/O
                            if filter_enabled:
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext not in allowed_exts:
                                    continue
                            try:
                                # Use cached stat from DirEntry
                                stat_info = entry.stat(follow_symlinks=False)
                                size = stat_info.st_size
                                if size >= min_size_bytes and (max_size_bytes is None or size <= max_size_bytes):
                                    files.append((entry.path, size))
                                    file_count += 1
                                    # Update status periodically
                                    current_time = time.time()
                                    if current_time - last_update_time >= 0.1:
                                        self._update_status(f"Discovering: {file_count:,} files")
                                        last_update_time = current_time
                            except (OSError, IOError) as e:
                                error_count += 1
                                self.app.log(f"Error accessing file {entry.path}: {e}", mode="warning")
                                continue
            except (OSError, IOError) as e:
                self.app.log(f"Error reading directory {self.selected_folder}: {e}", mode="error")
        if error_count > 0:
            self.app.log(f"Scan encountered {error_count} file access errors", mode="warning")
        # Final status update with total counts
        elapsed = time.time() - self.scan_start_time
        folder_count = getattr(self, '_folder_count', 1)
        self._update_status(f"Found {len(files):,} files in {folder_count:,} folders ({elapsed:.1f}s)")
        return files


    def _scan_directory_recursive(self, directory: str, files: List[Tuple[str, int]],
                                   min_size_bytes: int, max_size_bytes: Union[int, None],
                                   filter_enabled: bool, allowed_exts: set,
                                   last_update_time: float) -> float:
        """Recursively scan directory using os.scandir. Returns updated last_update_time."""
        folder_count = getattr(self, '_folder_count', 0)
        error_count = getattr(self, '_error_count', 0)
        try:
            with os.scandir(directory) as entries:
                subdirs = []
                for entry in entries:
                    if not self.is_scanning:
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            subdirs.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            # Check extension BEFORE stat call to avoid unnecessary I/O
                            if filter_enabled:
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext not in allowed_exts:
                                    continue
                            # Use cached stat from DirEntry
                            stat_info = entry.stat(follow_symlinks=False)
                            size = stat_info.st_size
                            if size >= min_size_bytes and (max_size_bytes is None or size <= max_size_bytes):
                                files.append((entry.path, size))
                    except (OSError, IOError) as e:
                        error_count += 1
                        self.app.log(f"Error accessing {entry.path}: {e}", mode="warning")
                        continue
                folder_count += 1
                self._folder_count = folder_count
                self._error_count = error_count
                # Update status periodically
                current_time = time.time()
                if current_time - last_update_time >= 0.1:
                    rel_path = os.path.relpath(directory, self.selected_folder)
                    if rel_path == '.':
                        display_path = os.path.basename(self.selected_folder)
                    else:
                        display_path = rel_path if len(rel_path) <= 40 else "..." + rel_path[-37:]
                    self._update_status(f"Discovering: {len(files):,} files | {folder_count:,} folders | {display_path}")
                    last_update_time = current_time
                # Recurse into subdirectories
                for subdir in subdirs:
                    if not self.is_scanning:
                        break
                    last_update_time = self._scan_directory_recursive(
                        subdir, files, min_size_bytes, max_size_bytes,
                        filter_enabled, allowed_exts, last_update_time
                    )
        except (OSError, IOError) as e:
            self.app.log(f"Error reading directory {directory}: {e}", mode="warning")
        return last_update_time


    # --- Duplicate Finding (Pipeline-based) ---
    def find_duplicates(self, files_with_sizes: List[Tuple[str, int]]) -> Dict[tuple, List[str]]:
        """
        Find duplicate files using the modular pipeline system.

        The pipeline processes files through a series of stages, each refining
        the groupings. Files that end up in groups with >1 member are duplicates.
        """
        total_files = len(files_with_sizes)
        # Check for same-folder mode
        if getattr(self, "same_folder_only_var", None) and self.same_folder_only_var.get():
            duplicates = self._find_duplicates_same_folder_pipeline(files_with_sizes)
        else:
            duplicates = self._run_pipeline(files_with_sizes)
        # Convert from Dict[tuple, List[Tuple[str, int]]] to Dict[tuple, List[str]]
        # (strip size info for final result)
        result = {}
        for key, files in duplicates.items():
            file_paths = [fp for fp, _ in files]
            if len(file_paths) > 1:
                result[key] = file_paths
        return result


    def _run_pipeline(self, files_with_sizes: List[Tuple[str, int]]) -> Dict[tuple, List[Tuple[str, int]]]:
        """
        Run the modular scan pipeline on the given files.

        Returns Dict[tuple, List[Tuple[str, int]]] with groups of (filepath, size) tuples.
        """
        # Build the pipeline from user configuration
        pipeline = self._build_pipeline()
        if not pipeline:
            return {}
        # Initialize with all files in a single group (empty key tuple)
        groups: Dict[tuple, List[Tuple[str, int]]] = {(): files_with_sizes}
        # Run each stage in sequence
        for stage in pipeline:
            if not self.is_scanning:
                break
            # Reset ETA tracker for each stage
            self._eta_tracker = None
            self.analysis_start_time = time.time()
            groups = stage.process(groups)
            # Early exit if no potential duplicates remain
            if not groups:
                break
        return groups


    def _find_duplicates_same_folder_pipeline(self, files_with_sizes: List[Tuple[str, int]]) -> Dict[tuple, List[Tuple[str, int]]]:
        """
        Find duplicates within same folder only, using the modular pipeline.

        Groups files by folder first, then runs the pipeline on each folder's files separately.
        """
        # Group files by their parent folder
        folder_groups = defaultdict(list)
        for filepath, size in files_with_sizes:
            folder = os.path.dirname(filepath)
            folder_groups[folder].append((filepath, size))
        all_duplicates = {}
        total_folders = len(folder_groups)
        overall_start_time = time.time()
        for folder_idx, (folder, folder_files) in enumerate(folder_groups.items()):
            if not self.is_scanning:
                break
            # Update overall progress
            self.update_overall_progress(folder_idx, total_folders, overall_start_time)
            # Run pipeline on this folder's files
            folder_duplicates = self._run_pipeline(folder_files)
            # Prefix keys with folder to avoid collisions
            for key, files in folder_duplicates.items():
                prefixed_key = (folder,) + key
                all_duplicates[prefixed_key] = files
        # Final progress update
        self.update_overall_progress(total_folders, total_folders, overall_start_time)
        return all_duplicates


    # --- Legacy duplicate finding methods (kept for reference, may be removed later) ---
    def find_duplicates_by_size(self, files_with_sizes: List[Tuple[str, int]], total_files: int) -> Dict[tuple, List[str]]:
        size_groups = defaultdict(list)
        start_time = getattr(self, 'analysis_start_time', time.time())
        last_update_time = start_time
        for i, (filepath, size) in enumerate(files_with_sizes):
            if not self.is_scanning:
                break
            size_groups[("size", size)].append(filepath)
            # Time-based progress throttling (every 200ms)
            current_time = time.time()
            if current_time - last_update_time >= 0.2:
                unique_sizes = len(size_groups)
                self.update_progress(i + 1, total_files, start_time, f"Grouping by size... {unique_sizes:,} unique sizes found |")
                last_update_time = current_time
        # Final status with results
        potential_dups = sum(1 for g in size_groups.values() if len(g) > 1)
        self._update_status(f"Size analysis complete: {len(size_groups):,} unique sizes, {potential_dups:,} potential duplicate groups")
        return dict(size_groups)


    def find_duplicates_by_size_and_name(self, files_with_sizes: List[Tuple[str, int]], total_files: int) -> Dict[tuple, List[str]]:
        size_name_groups = defaultdict(list)
        start_time = getattr(self, 'analysis_start_time', time.time())
        last_update_time = start_time
        for i, (filepath, size) in enumerate(files_with_sizes):
            if not self.is_scanning:
                break
            filename = os.path.basename(filepath).lower()
            key = ("size_name", size, filename)
            size_name_groups[key].append(filepath)
            # Time-based progress throttling (every 200ms)
            current_time = time.time()
            if current_time - last_update_time >= 0.2:
                unique_combos = len(size_name_groups)
                self.update_progress(i + 1, total_files, start_time, f"Comparing size + name... {unique_combos:,} unique combinations |")
                last_update_time = current_time
        # Final status with results
        potential_dups = sum(1 for g in size_name_groups.values() if len(g) > 1)
        self._update_status(f"Size+name analysis complete: {len(size_name_groups):,} unique, {potential_dups:,} potential duplicate groups")
        return dict(size_name_groups)


    def find_duplicates_by_size_then_md5(self, files_with_sizes: List[Tuple[str, int]], total_files: int) -> Dict[tuple, List[str]]:
        # First group by size using cached sizes
        self._update_status("Phase 1/2: Grouping files by size...")
        size_groups = self._group_files_by_size(files_with_sizes, total_files, "Phase 1/2: Grouping by size...", progress_weight=0.3)
        # Prepare files to hash (only groups with more than one file)
        files_to_hash = [(size, fp) for size, group in size_groups.items() if len(group) > 1 for fp in group]
        # Report size grouping results before hashing
        potential_dup_groups = sum(1 for g in size_groups.values() if len(g) > 1)
        skipped_unique = sum(1 for g in size_groups.values() if len(g) == 1)
        self._update_status(f"Size grouping done: {potential_dup_groups:,} groups need hashing, {skipped_unique:,} unique files skipped")
        md5_groups = {}
        if files_to_hash:
            total_hash_size = sum(size for size, _ in files_to_hash)
            total_hash_size_str = self.format_file_size(total_hash_size)
            self._update_status(f"Phase 2/2: Hashing {len(files_to_hash):,} files ({total_hash_size_str})...")
            # Use common parallel hashing method
            hash_results = self._hash_files_parallel(files_to_hash, partial_size=0, status_prefix="Phase 2/2: Hashing...")
            # Group by size and hash (using tuple keys)
            for filepath, (size, md5_hash) in hash_results.items():
                key = ("size_md5", size, md5_hash)
                if key not in md5_groups:
                    md5_groups[key] = []
                md5_groups[key].append(filepath)
        # Skip adding single-file groups (they're not duplicates)
        return md5_groups


    def _compute_hash_safe(self, filepath: str, partial_size: int = 0) -> str:
        """Safely compute hash with error handling. Returns empty string on error."""
        try:
            if not os.path.exists(filepath):
                return ""
            return cached_get_md5(filepath, partial_size=partial_size)
        except (OSError, IOError) as e:
            self.app.log(f"Error hashing {filepath}: {e}", mode="warning")
            return ""


    def find_duplicates_by_md5(self, files_with_sizes: List[Tuple[str, int]], total_files: int) -> Dict[tuple, List[str]]:
        # Calculate total size from cached sizes (no extra stat calls)
        total_size = sum(size for _, size in files_with_sizes)
        total_size_str = self.format_file_size(total_size)
        self._update_status(f"Hashing {total_files:,} files ({total_size_str}) with full MD5...")
        # Prepare files with None context (no size grouping needed)
        files_to_hash = [(None, fp) for fp, _ in files_with_sizes]
        hash_results = self._hash_files_parallel(files_to_hash, partial_size=0, status_prefix="Full MD5 hashing...")
        # Group by hash only (using tuple keys)
        md5_groups = defaultdict(list)
        for filepath, (_, md5_hash) in hash_results.items():
            md5_groups[("md5", md5_hash)].append(filepath)
        return dict(md5_groups)


    def find_duplicates_by_partial_hash(self, files_with_sizes: List[Tuple[str, int]], total_files: int, partial_size: int = 1024) -> Dict[tuple, List[str]]:
        """Find duplicates by hashing only the first partial_size bytes of each file."""
        partial_size_str = self.format_file_size(partial_size)
        self._update_status(f"Hashing {total_files:,} files (first {partial_size_str} each)...")
        # Prepare files with partial_size as context
        files_to_hash = [(partial_size, fp) for fp, _ in files_with_sizes]
        hash_results = self._hash_files_parallel(files_to_hash, partial_size=partial_size, status_prefix="Partial hashing...")
        # Group by partial hash (using tuple keys)
        partial_hash_groups = defaultdict(list)
        for filepath, (ps, partial_hash) in hash_results.items():
            key = ("partial", ps, partial_hash)
            partial_hash_groups[key].append(filepath)
        return dict(partial_hash_groups)


    def find_duplicates_by_size_and_partial_hash(self, files_with_sizes: List[Tuple[str, int]], total_files: int, partial_size: int = 4096) -> Dict[tuple, List[str]]:
        """Find duplicates by grouping by size, then by partial hash of the file."""
        self._update_status("Phase 1/2: Grouping files by size...")
        size_groups = self._group_files_by_size(files_with_sizes, total_files, "Phase 1/2: Grouping by size...", progress_weight=0.2)
        # Prepare files to hash (only groups with more than one file)
        files_to_hash = [(size, fp) for size, group in size_groups.items() if len(group) > 1 for fp in group]
        # Report size grouping results
        potential_dup_groups = sum(1 for g in size_groups.values() if len(g) > 1)
        skipped_unique = sum(1 for g in size_groups.values() if len(g) == 1)
        self._update_status(f"Size grouping done: {potential_dup_groups:,} groups need hashing, {skipped_unique:,} unique files skipped")
        partial_hash_groups = {}
        if files_to_hash:
            partial_size_str = self.format_file_size(partial_size)
            self._update_status(f"Phase 2/2: Hashing {len(files_to_hash):,} files (first {partial_size_str} each)...")
            # Use common parallel hashing method
            hash_results = self._hash_files_parallel(files_to_hash, partial_size=partial_size, status_prefix="Phase 2/2: Partial hashing...")
            # Group by size and partial hash (using tuple keys)
            for filepath, (size, partial_hash) in hash_results.items():
                key = ("size_partial", size, partial_size, partial_hash)
                if key not in partial_hash_groups:
                    partial_hash_groups[key] = []
                partial_hash_groups[key].append(filepath)
        # Skip adding single-file groups (they're not duplicates)
        return partial_hash_groups


    def get_partial_hash(self, filepath: str, partial_size: int = 1024) -> str:
        """Compute MD5 hash of the first partial_size bytes of a file using cached version."""
        return cached_get_md5(filepath, partial_size=partial_size)


    def update_overall_progress(self, current, total, start_time):
        progress = (current / total) * 100 if total else 0
        eta = self.get_eta(current, total, start_time)
        self._update_overall_progress(progress)
        self._update_overall_eta(f"Overall: {current}/{total} folders ({eta})")


    # --- Progress & Display ---
    def update_progress(self, current, total, start_time, status_prefix, percent=1.0):
        progress = (current / total) * (100 * percent)
        eta = self.get_eta(current, total, start_time, percent)
        self._update_progress(progress)
        self._update_status(f"{status_prefix} {current}/{total} ({eta})")


    def display_results(self, duplicates: Dict[tuple, List[str]], total_files: int):
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
        pipeline_desc = " → ".join(self._get_active_stages())
        self.results_text.insert(tk.END, f"Pipeline used: {pipeline_desc}\n")
        self.scan_complete(f"Scan completed - found {duplicate_groups} duplicate groups")
        self.update_action_buttons(True, duplicate_files - duplicate_groups)


    def update_action_buttons(self, enable: bool, duplicate_count: int = 0):
        if enable and duplicate_count > 0:
            self._set_action_buttons_state(enabled=True)
            self.action_info_var.set(f"{duplicate_count} duplicate files can be processed")
        else:
            self._set_action_buttons_state(enabled=False)
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
        self._set_action_buttons_state(enabled=False)
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
            self._set_action_buttons_state(enabled=True)
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
        """Get full MD5 hash using cached version from duplicate_handler."""
        return cached_get_md5(filepath, chunk_size=chunk_size)


    def format_file_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


    def get_eta(self, current: int, total: int, start_time: float, percent: float = 1.0) -> str:
        """
        Calculate ETA using a rolling window of recent speeds for quick adaptation.

        Tracks the last N time/count samples and uses the average speed from those
        samples to estimate remaining time. This adapts quickly when speed changes.
        """
        if current == 0:
            return "estimating..."
        current_time = time.time()
        elapsed = current_time - start_time
        if elapsed < 0.1:
            return "estimating..."
        adjusted_total = total * percent
        remaining_items = adjusted_total - current
        if remaining_items <= 0:
            return "almost done..."
        # Initialize or reset tracker if start_time changed (new operation)
        if self._eta_tracker is None or self._eta_tracker.get('start_time') != start_time:
            self._eta_tracker = {
                'start_time': start_time,
                'samples': [],  # List of (timestamp, count) samples
                'max_samples': 10,  # Keep last N samples for rolling average
                'last_sample_time': start_time,
            }
        tracker = self._eta_tracker
        # Add a new sample if enough time has passed (at least 100ms between samples)
        if current_time - tracker['last_sample_time'] >= 0.1:
            tracker['samples'].append((current_time, current))
            tracker['last_sample_time'] = current_time
            # Keep only the last N samples
            if len(tracker['samples']) > tracker['max_samples']:
                tracker['samples'] = tracker['samples'][-tracker['max_samples']:]
        # Calculate speed from rolling window
        samples = tracker['samples']
        if len(samples) >= 2:
            # Use the oldest and newest samples in our window to calculate speed
            oldest_time, oldest_count = samples[0]
            newest_time, newest_count = samples[-1]
            time_span = newest_time - oldest_time
            count_span = newest_count - oldest_count
            if time_span > 0 and count_span > 0:
                rolling_speed = count_span / time_span  # items per second
                remaining_seconds = remaining_items / rolling_speed
            else:
                # Fallback to overall average
                overall_speed = current / elapsed
                remaining_seconds = remaining_items / overall_speed if overall_speed > 0 else 0
        else:
            # Not enough samples yet, use overall average
            overall_speed = current / elapsed
            remaining_seconds = remaining_items / overall_speed if overall_speed > 0 else 0
        remaining_seconds = max(remaining_seconds, 0)
        if remaining_seconds < 2:
            return "less than 2s"
        mins, secs = divmod(int(remaining_seconds), 60)
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
#region show_duplicate_scanner


def show_duplicate_scanner(app: 'Main'):
    scanner = DuplicateScannerDialog(app.root, app)


#endregion