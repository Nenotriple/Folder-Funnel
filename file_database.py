#region - Imports


# Standard imports
import os
import re
import json
import hashlib
import datetime
from pathlib import Path
from difflib import SequenceMatcher
from typing import Dict, List, Optional

# Third-party imports
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


#endregion
#region - cls FileEntry


class FileEntry:
    def __init__(self, path: str, modified: float, size: float):
        self.path = path
        self.modified = modified
        self.size = size


    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'modified': self.modified,
            'size': self.size
        }


    @classmethod
    def from_dict(cls, data: dict) -> 'FileEntry':
        return cls(data['path'], data['modified'], data.get('size', 0))


#endregion
#region - cls FolderDatabase


class FolderDatabase:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.files: Dict[str, FileEntry] = {}
        self.folders: List[str] = []


    def scan_directory(self) -> None:
        self.files.clear()
        self.folders.clear()
        for root, dirs, files in os.walk(self.root_path):
            rel_root = str(Path(root).relative_to(self.root_path))
            if rel_root != '.':
                self.folders.append(rel_root)
            for file in files:
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(self.root_path))
                stats = full_path.stat()
                self.files[rel_path] = FileEntry(
                    rel_path,
                    stats.st_mtime,
                    stats.st_size
                )


    def partial_update(self, path: str, event_type: str):
        full_path = self.root_path / path
        if event_type == 'created':
            if full_path.is_file():
                stats = full_path.stat()
                self.files[path] = FileEntry(
                    path,
                    stats.st_mtime,
                    stats.st_size
                )
            else:
                self.folders.append(path)
        elif event_type == 'deleted':
            if path in self.files:
                del self.files[path]
            elif path in self.folders:
                # Remove this folder and all subfolders
                self.folders = [f for f in self.folders if not (f == path or f.startswith(path + os.sep))]
        elif event_type == 'modified':
            if path in self.files and full_path.exists():
                stats = full_path.stat()
                self.files[path].modified = stats.st_mtime
                self.files[path].size = stats.st_size
        elif event_type == 'moved':
            # Handle rename/move logic
            pass


    def save_to_file(self, filepath: str) -> None:
        data = {
            'root_path': str(self.root_path),
            'scan_time': datetime.datetime.now().isoformat(),
            'folders': self.folders,
            'files': {path: entry.to_dict() for path, entry in self.files.items()}
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


    @classmethod
    def load_from_file(cls, filepath: str) -> 'FolderDatabase':
        with open(filepath, 'r') as f:
            data = json.load(f)
        db = cls(data['root_path'])
        db.folders = data['folders']
        db.files = {
            path: FileEntry.from_dict(entry_data)
            for path, entry_data in data['files'].items()
        }
        return db


#endregion
#region - cls DatabaseManager


class DatabaseManager:
    def __init__(self, parent, database_dir: str):
        self.parent = parent
        self.database_dir = Path(database_dir)
        self.database_dir.mkdir(exist_ok=True)
        self.databases: Dict[str, str] = {}
        self.master_file = self.database_dir / 'master.json'
        self.load_master()
        self.watch_observer = None
        self.source_observer = None


    def load_master(self) -> None:
        if self.master_file.exists():
            with open(self.master_file, 'r') as f:
                self.databases = json.load(f)


    def save_master(self) -> None:
        with open(self.master_file, 'w') as f:
            json.dump(self.databases, f, indent=2)


    def add_database(self, name: str, root_path: str) -> None:
        db = FolderDatabase(root_path)
        db.scan_directory()
        db_file = self.database_dir / f"{name}.json"
        db.save_to_file(str(db_file))
        self.databases[name] = str(root_path)
        self.save_master()


    def get_database(self, name: str) -> Optional[FolderDatabase]:
        if name not in self.databases:
            return None
        db_file = self.database_dir / f"{name}.json"
        if not db_file.exists():
            return None
        return FolderDatabase.load_from_file(str(db_file))


    def start_watching(self, watch_path: str, source_path: str = None):
        # Stop any existing observers
        self.stop_watching()
        # Set up watch path observer
        self.watch_observer = Observer()
        watch_handler = WatchFolderHandler(self.parent, self)
        self.watch_observer.schedule(watch_handler, path=watch_path, recursive=True)
        self.watch_observer.start()
        # Set up source path observer (if provided)
        if source_path:
            self.source_observer = Observer()
            source_handler = SourceFolderHandler(self.parent)
            self.source_observer.schedule(source_handler, path=source_path, recursive=True)
            self.source_observer.start()


    def stop_watching(self):
        if self.watch_observer:
            self.watch_observer.stop()
            self.watch_observer.join()
            self.watch_observer = None
        if self.source_observer:
            self.source_observer.stop()
            self.source_observer.join()
            self.source_observer = None


    def update_database(self, event):
        # Identify which database is affected
        db_name = None
        p_event = Path(event.src_path)
        for name, root_str in self.databases.items():
            p_root = Path(root_str)
            try:
                p_event.relative_to(p_root)
                db_name = name
                break
            except ValueError:
                continue
        # If no database is affected, return
        if not db_name:
            return
        folder_db = self.get_database(db_name)
        if not folder_db:
            return
        # Update the database
        event_type = event.event_type
        rel_path = str(p_event.relative_to(folder_db.root_path))
        folder_db.partial_update(rel_path, event_type)
        # Save changes
        db_file = self.database_dir / f"{db_name}.json"
        folder_db.save_to_file(str(db_file))


#endregion
#region - cls FolderChangeHandler


class WatchFolderHandler(FileSystemEventHandler):
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager


    def on_created(self, event):
        self.parent.log(f"Created: {event.src_path}")
        # If a new folder is created, sync the watch folders
        if event.is_directory:
            self.parent.sync_watch_folders(silent="semi")
        # Else, queue the file for moving
        else:
            if os.path.exists(event.src_path):
                self.parent.queue_move_file(event.src_path)
        self.db_manager.update_database(event)


    def on_deleted(self, event):
        self.parent.sync_watch_folders(silent="silent")
        self.db_manager.update_database(event)


    def on_modified(self, event):
        self.db_manager.update_database(event)


    def on_moved(self, event):
        # Inform the app that a file was renamed/moved
        self.parent.handle_rename_event(event.src_path, event.dest_path)
        self.db_manager.update_database(event)


#endregion
#region - cls SourceFolderHandler


class SourceFolderHandler(FileSystemEventHandler):
    def __init__(self, parent):
        self.parent = parent


    def on_created(self, event):
        if event.is_directory:
            # Only sync folders when a directory is created in source
            self.parent.sync_watch_folders(silent="semi")


    def on_deleted(self, event):
        if event.is_directory:
            # Only sync folders when a directory is deleted in source
            self.parent.sync_watch_folders(silent="silent")


    def on_moved(self, event):
        if event.is_directory:
            # Only sync folders when a directory is moved/renamed in source
            self.parent.sync_watch_folders(silent="semi")


#endregion
#region - Helper Functions


def are_files_identical(file1, file2, rigorous_check=False, method='Strict', max_files=10, chunk_size=8192, db_manager=None):
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

    def get_file_size(filepath, db_manager=None):
        """Get file size from database if available, otherwise from filesystem"""
        if db_manager:
            # Try to find the file in any known database
            for db_name in db_manager.databases:
                db = db_manager.get_database(db_name)
                if not db:
                    continue
                # Check if file is in this database's root path
                try:
                    rel_path = str(Path(filepath).relative_to(db.root_path))
                    if rel_path in db.files:
                        return db.files[rel_path].size
                except (ValueError, KeyError):
                    # File not in this database, continue to next one
                    pass
        # Fallback to direct filesystem access
        return os.path.getsize(filepath) if os.path.exists(filepath) else None

    try:
        target_dir = os.path.dirname(file2)
        similar = find_similar_files(file1, target_dir, method, max_files)
        print(f"Similar files: {similar}")
        for sf in similar:
            file1_size = get_file_size(file1, db_manager)
            sf_size = get_file_size(sf, db_manager)
            if file1_size is not None and sf_size is not None and file1_size == sf_size:
                return True
        if rigorous_check:
            file1_md5 = get_md5(file1)
            for sf in similar:
                if get_md5(sf) == file1_md5:
                    return True
        else:
            if os.path.exists(file2) and get_md5(file1) == get_md5(file2):
                return True
        return False
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False


def find_similar_files(filename, target_dir, method='Strict', max_files=10):
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
