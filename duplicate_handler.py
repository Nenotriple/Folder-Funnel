#region - Imports


# Standard
import os
import re
import shutil
import hashlib
from typing import List
from difflib import SequenceMatcher

# Standard GUI
from tkinter import messagebox

# Local imports
from duplicate_scanner_dialog import DuplicateScannerDialog

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - File Operations


def get_md5(filename, chunk_size=8192):
    """Calculate MD5 hash of a file."""
    m = hashlib.md5()
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            m.update(chunk)
    return m.hexdigest()


def are_files_identical(file1, file2, check_mode="Similar", method='Strict', max_files=10, chunk_size=8192):
    """Compare files by size/MD5 and/or check similar files in the target directory.
    Returns tuple (is_identical, matching_file_path)"""
    try:
        target_dir = os.path.dirname(file2)
        similar_files = find_similar_files(file1, target_dir, method, max_files)
        for file in similar_files:
            if os.path.exists(file) and os.path.getsize(file1) == os.path.getsize(file):
                return True, file
        if check_mode == "Similar":
            file1_md5 = get_md5(file1, chunk_size)
            for file in similar_files:
                if get_md5(file, chunk_size) == file1_md5:
                    return True, file
        elif check_mode == "Single":
            if os.path.exists(file2) and get_md5(file1, chunk_size) == get_md5(file2, chunk_size):
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


def show_duplicate_scanner(app: 'Main'):
    """Show the duplicate scanner dialog."""
    if not app.working_dir_var.get():
        messagebox.showwarning("No Source Folder", "Please select a source folder first from File > Select Source Path...")
        return
    scanner = DuplicateScannerDialog(app.root, app)


#endregion