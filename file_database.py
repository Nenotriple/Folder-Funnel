import os
import json
import datetime
from typing import Dict, List, Optional
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FileEntry:
    def __init__(self, path: str, modified: float):
        self.path = path
        self.modified = modified


    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'modified': self.modified
        }


    @classmethod
    def from_dict(cls, data: dict) -> 'FileEntry':
        return cls(data['path'], data['modified'])


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
                    stats.st_mtime
                )


    def partial_update(self, path: str, event_type: str):
        full_path = self.root_path / path
        if event_type == 'created':
            if full_path.is_file():
                stats = full_path.stat()
                self.files[path] = FileEntry(path, stats.st_mtime)
            else:
                self.folders.append(path)
        elif event_type == 'deleted':
            if path in self.files:
                del self.files[path]
            elif path in self.folders:
                self.folders.remove(path)
        elif event_type == 'modified':
            if path in self.files and full_path.exists():
                stats = full_path.stat()
                self.files[path].modified = stats.st_mtime
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


class FolderChangeHandler(FileSystemEventHandler):
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager


    def on_created(self, event):
        self.parent.log(f"Created: {event.src_path}")
        if not event.is_directory:  # Only handle files, not directories
            # Move the file if it's in the watch folder
            if os.path.exists(event.src_path):
                self.parent.move_file(event.src_path)
        self.db_manager.update_database(event)


    def on_deleted(self, event):
        self.db_manager.update_database(event)


    def on_modified(self, event):
        self.db_manager.update_database(event)


    def on_moved(self, event):
        self.db_manager.update_database(event)


class DatabaseManager:
    def __init__(self, parent, database_dir: str):
        self.parent = parent
        self.database_dir = Path(database_dir)
        self.database_dir.mkdir(exist_ok=True)
        self.databases: Dict[str, str] = {}
        self.master_file = self.database_dir / 'master.json'
        self.load_master()
        self.observer = None


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


    def start_watching(self, path_to_watch: str):
        if self.observer:
            self.stop_watching()
        self.observer = Observer()
        handler = FolderChangeHandler(self, self.parent)
        self.observer.schedule(handler, path=path_to_watch, recursive=True)
        self.observer.start()


    def stop_watching(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None


    def update_database(self, event):
        # Identify which database is affected
        db_name = None
        for name, root in self.databases.items():
            if str(self.database_dir / f"{name}.json") in event.src_path:
                db_name = name
                break
        if not db_name:
            return
        folder_db = self.get_database(db_name)
        if not folder_db:
            return
        event_type = event.event_type
        rel_path = str(Path(event.src_path).relative_to(folder_db.root_path))
        folder_db.partial_update(rel_path, event_type)
        # Save changes
        db_file = self.database_dir / f"{db_name}.json"
        folder_db.save_to_file(str(db_file))
