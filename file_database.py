#region - Imports


# Standard imports
import os
import re
import hashlib
from typing import List
from difflib import SequenceMatcher

# Third-party imports
from watchdog.events import FileSystemEventHandler


#endregion
#region - cls WatchFolderHandler


class WatchFolderHandler(FileSystemEventHandler):
    def __init__(self, parent):
        self.parent = parent

    def on_created(self, event):
        # If a new folder is created, sync the watch folders
        if event.is_directory:
            self.parent.sync_watch_folders(silent="semi")
        # Else, queue the file for moving
        else:
            if os.path.exists(event.src_path):
                self.parent.queue_move_file(event.src_path)

    def on_deleted(self, event):
        self.parent.sync_watch_folders(silent="silent")

    def on_modified(self, event):
        # We only care about new files, not modifications
        pass

    def on_moved(self, event):
        # Inform the app that a file was renamed/moved
        self.parent.handle_rename_event(event.src_path, event.dest_path)


#endregion
#region - cls SourceFolderHandler


class SourceFolderHandler(FileSystemEventHandler):
    def __init__(self, parent):
        self.parent = parent

    def on_created(self, event):
        if event.is_directory:
            # Only sync folders when a directory is created in source
            self.parent.sync_watch_folders(silent="semi")
        self.parent.count_folders_and_files()

    def on_deleted(self, event):
        if event.is_directory:
            # Only sync folders when a directory is deleted in source
            self.parent.sync_watch_folders(silent="silent")
        self.parent.count_folders_and_files()

    def on_moved(self, event):
        if event.is_directory:
            # Only sync folders when a directory is moved/renamed in source
            self.parent.sync_watch_folders(silent="semi")
        self.parent.count_folders_and_files()


#endregion
#region - Helper Functions


def are_files_identical(file1, file2, rigorous_check=False, method='Strict', max_files=10, chunk_size=8192):
    """Compare files by size/MD5 or find similar files if rigorous_check is True."""
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
                return True
        if rigorous_check:
            file1_md5 = get_md5(file1)
            for file in similar_files:
                if get_md5(file) == file1_md5:
                    return True
        else:
            if os.path.exists(file2) and get_md5(file1) == get_md5(file2):
                return True
        return False
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False


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


#endregion
