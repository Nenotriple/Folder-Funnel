#region Imports


# Standard
import os
import shutil
from datetime import datetime

# Standard GUI
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

# Third-party
from TkToolTip import TkToolTip as Tip

# Local imports
from .scalable_image_label import ScalableImageLabel

# Set TkToolTip defaults
Tip.DELAY = 250
Tip.PADY = 25
Tip.ORIGIN = "widget"


#endregion
#region InteractiveDuplicateReviewDialog


class InteractiveDuplicateReviewDialog:
    #region GUI Setup
    def __init__(self, parent, duplicate_groups, selected_folder, app):
        self.parent = parent
        self.duplicate_groups = [group for group in duplicate_groups.values() if len(group) > 1]
        self.selected_folder = selected_folder
        self.app = app
        self.current_group_index = 0
        self.preview_sizes = {
            "Small": (128, 128),
            "Medium": (200, 200),
            "Large": (256, 256),
            "Extra Large": (512, 512),
            "Giant": (768, 768)
        }
        self.current_preview_size = tk.StringVar(value="Large")
        self.fast_delete_var = tk.BooleanVar(value=False)
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Interactive Duplicate Review")
        self.dialog.geometry("1000x700")
        self.dialog.resizable(True, True)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
        self.dialog.grid_rowconfigure(1, weight=1)
        self.dialog.grid_columnconfigure(0, weight=1)

        # --- Top ---
        top = ttk.Frame(self.dialog, padding=(8, 4))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        top.grid_columnconfigure(2, weight=0)
        self.group_label = ttk.Label(top)
        self.group_label.grid(row=0, column=0, sticky="w", padx=(0, 12))
        preview_ctrl = ttk.Frame(top)
        preview_ctrl.grid(row=0, column=1, sticky="e")
        ttk.Label(preview_ctrl, text="Preview:").pack(side="left", padx=(0, 2))
        preview_combo = ttk.Combobox(preview_ctrl, textvariable=self.current_preview_size, values=list(self.preview_sizes.keys()), state="readonly", width=12)
        preview_combo.pack(side="left")
        preview_combo.bind("<<ComboboxSelected>>", self.on_preview_size_changed)
        Tip(preview_combo, "Change the size of image previews")
        # Fast delete checkbutton
        fast_delete_cb = ttk.Checkbutton(top, text="Fast delete (no confirm/success)", variable=self.fast_delete_var)
        fast_delete_cb.grid(row=0, column=2, sticky="e", padx=(16, 0))
        Tip(fast_delete_cb, "Delete files immediately without confirmation or success dialogs")

        # --- Center ---
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

        # --- Bottom ---
        bottom = ttk.Frame(self.dialog, padding=(8, 8))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)
        nav = ttk.Frame(bottom)
        nav.grid(row=0, column=0, sticky="w")
        self.prev_button = ttk.Button(nav, text="◀ Prev", command=self.previous_group, width=10)
        self.prev_button.pack(side="left", padx=2)
        Tip(self.prev_button, "Go to previous duplicate group")
        self.next_button = ttk.Button(nav, text="Next ▶", command=self.next_group, width=10)
        self.next_button.pack(side="left", padx=2)
        Tip(self.next_button, "Go to next duplicate group")
        group_actions = ttk.Frame(bottom)
        group_actions.grid(row=0, column=1, sticky="e")
        skip_btn = ttk.Button(group_actions, text="Skip Group", command=self.skip_group, width=14)
        skip_btn.pack(side="left", padx=(0,4))
        Tip(skip_btn, "Skip this group and review it later")
        keep_first_btn = ttk.Button(group_actions, text="Keep First, Delete Rest", command=self.delete_all_but_first, width=22)
        keep_first_btn.pack(side="left", padx=(0,4))
        Tip(keep_first_btn, "Keep the first file and delete all others in this group")
        close_btn = ttk.Button(group_actions, text="Close", command=self.on_close, width=10)
        close_btn.pack(side="left")
        Tip(close_btn, "Close the duplicate review dialog")
        self.center_dialog()
        self.show_current_group()


    # --- Dialog positioning ---
    def center_dialog(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


    # --- Canvas/scroll handling ---
    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def _on_canvas_configure(self, event=None):
        canvas_width = self.canvas.winfo_width()
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)


    def _bind_mousewheel_events(self):
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.grid_frame.bind("<MouseWheel>", _on_mousewheel)
        self.dialog.bind("<MouseWheel>", _on_mousewheel)


    # --- Group display ---
    def show_current_group(self):
        if not self.duplicate_groups or self.current_group_index >= len(self.duplicate_groups):
            self.on_close()
            return
        self.dialog.focus_set()
        current_group = self.duplicate_groups[self.current_group_index]
        total_groups = len(self.duplicate_groups)
        self.group_label.config(text=f"Group {self.current_group_index + 1}/{total_groups} • {len(current_group)} files")
        self.prev_button.config(state="normal" if self.current_group_index > 0 else "disabled")
        self.next_button.config(state="normal" if self.current_group_index < total_groups - 1 else "disabled")
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        # Use side-by-side layout for 2 images
        if len(current_group) == 2 and all(self.is_image_file(fp) for fp in current_group):
            self.create_side_by_side_comparison(current_group)
        else:
            # Original grid layout
            width = self.dialog.winfo_width() or 1000
            img_w, img_h = self.preview_sizes[self.current_preview_size.get()]
            min_card_width = img_w + 60
            cols = max(1, width // min_card_width)
            for idx, file_path in enumerate(current_group):
                row, col = divmod(idx, cols)
                self.create_file_card(self.grid_frame, file_path, idx).grid(row=row, column=col, padx=8, pady=8, sticky="n")
        self.grid_frame.update_idletasks()
        self.canvas.yview_moveto(0)


    def create_side_by_side_comparison(self, file_paths):
        """Create a side-by-side comparison layout for exactly 2 images."""
        # Calculate available space
        dialog_width = self.dialog.winfo_width() or 1000
        dialog_height = self.dialog.winfo_height() or 700
        # Account for UI elements (top bar ~50px, bottom bar ~60px, padding ~50px)
        available_height = dialog_height - 160
        available_width = dialog_width - 40  # Account for padding and scrollbar
        # Each image gets half the width minus some padding
        max_image_width = (available_width - 30) // 2  # 30px for spacing between images
        max_image_height = available_height - 150  # Reserve space for file info and buttons
        # Create main container
        comparison_frame = ttk.Frame(self.grid_frame)
        comparison_frame.pack(fill="both", expand=True, padx=10, pady=10)
        for i, file_path in enumerate(file_paths):
            # Create side frame for each image
            side_frame = ttk.Frame(comparison_frame, relief="ridge", borderwidth=1, padding=8)
            side_frame.grid(row=0, column=i, sticky="nsew", padx=(0, 15) if i == 0 else (15, 0))
            side_frame.grid_rowconfigure(0, weight=1)
            side_frame.grid_columnconfigure(0, weight=1)
            # Image preview with dynamic sizing
            image_frame = ttk.Frame(side_frame)
            image_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
            try:
                image_label = ScalableImageLabel(image_frame, width=max_image_width, height=max_image_height, keep_aspect=True)
                image_label.pack(expand=True, fill="both")
                image_label.set_image(file_path)
                image_label.configure(cursor="hand2")
                image_label.bind("<Button-1>", lambda e, fp=file_path: self.open_image_file(fp))
                if hasattr(image_label, 'label'):
                    image_label.label.configure(cursor="hand2")
                    image_label.label.bind("<Button-1>", lambda e, fp=file_path: self.open_image_file(fp))
            except Exception:
                ttk.Label(image_frame, text="Preview Error", foreground="red").pack()
            # File info
            info_frame = ttk.Frame(side_frame)
            info_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
            self.create_file_info_compact(info_frame, file_path)
            # Action buttons
            actions_frame = ttk.Frame(side_frame)
            actions_frame.grid(row=2, column=0, sticky="ew")
            self.create_action_buttons_compact(actions_frame, file_path)
        # Configure grid weights for equal distribution
        comparison_frame.grid_columnconfigure(0, weight=1)
        comparison_frame.grid_columnconfigure(1, weight=1)


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
            # Filename
            name = filename if len(filename) <= 36 else filename[:33] + "..."
            name_label = ttk.Label(parent, text=name, foreground="blue", cursor="hand2")
            name_label.grid(row=0, column=0, sticky="w")
            name_label.bind("<Button-1>", lambda e: self.open_file_location(file_path))
            # Details
            details = f"{self.format_file_size(file_size)} • {mod_time.strftime('%m/%d/%y %H:%M')}"
            ttk.Label(parent, text=details, foreground="gray").grid(row=1, column=0, sticky="w")
            rel = rel_path if len(rel_path) <= 40 else "..." + rel_path[-37:]
            rel_label = ttk.Label(parent, text=rel, foreground="gray")
            rel_label.grid(row=2, column=0, sticky="w")
            Tip(rel_label, rel_path)
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
        delete_btn = ttk.Button(parent, text="Delete", command=lambda fp=file_path: self.delete_file(fp))
        delete_btn.pack(side="left", fill="x", expand=True, padx=1)
        Tip(delete_btn, "Delete this file")
        move_btn = ttk.Button(parent, text="Move", command=lambda fp=file_path: self.move_file(fp))
        move_btn.pack(side="left", fill="x", expand=True, padx=1)
        Tip(move_btn, "Move this file to another folder")
        skip_btn = ttk.Button(parent, text="Skip", command=lambda fp=file_path: self.ignore_file(fp))
        skip_btn.pack(side="left", fill="x", expand=True, padx=1)
        Tip(skip_btn, "Ignore this file for now")


    def on_preview_size_changed(self, event=None):
        self.show_current_group()


    #endregion
    #region File Operations


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
            self.show_current_group()
        else:
            if messagebox.askyesno("Confirm Bulk Delete", f"Delete {len(files_to_delete)} files?\n\nKeeping: {first_file}", parent=self.dialog):
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


    #endregion
    #region Navigation/Helpers


    def open_file_location(self, file_path):
        try:
            os.startfile(os.path.dirname(file_path))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open location:\n{str(e)}", parent=self.dialog)


    def open_image_file(self, file_path):
        try:
            os.startfile(file_path)
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


    def on_close(self):
        self.dialog.destroy()


    #endregion
#endregion
