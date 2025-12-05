#region - Imports


# Standard
import os
import re
import shutil
import hashlib
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
from functools import lru_cache

# Standard GUI
from tkinter import messagebox

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Hash Cache


# Global hash cache: {(file_path, mtime, size): hash_value}
_hash_cache: Dict[Tuple[str, float, int], str] = {}
_HASH_CACHE_MAX_SIZE = 10000  # Maximum number of cached hashes


def get_file_key(filepath: str) -> Optional[Tuple[str, float, int]]:
    """Get a cache key for a file based on path, mtime, and size.
    Returns None if file doesn't exist or can't be accessed."""
    try:
        stat = os.stat(filepath)
        return (os.path.normpath(filepath), stat.st_mtime, stat.st_size)
    except (OSError, IOError):
        return None


def get_cached_hash(filepath: str, partial_size: int = 0, chunk_size: int = 8192) -> Optional[str]:
    """Get hash from cache if available and file hasn't changed.
    Returns None if not cached or file has been modified."""
    key = get_file_key(filepath)
    if key is None:
        return None
    # For partial hashes, include the partial_size in the key
    if partial_size > 0:
        cache_key = (key[0], key[1], key[2], partial_size)
    else:
        cache_key = key
    return _hash_cache.get(cache_key)


def set_cached_hash(filepath: str, hash_value: str, partial_size: int = 0) -> None:
    """Store a hash in the cache."""
    global _hash_cache
    key = get_file_key(filepath)
    if key is None:
        return
    # Evict oldest entries if cache is too large
    if len(_hash_cache) >= _HASH_CACHE_MAX_SIZE:
        # Remove 20% of oldest entries (simple eviction strategy)
        to_remove = list(_hash_cache.keys())[:_HASH_CACHE_MAX_SIZE // 5]
        for k in to_remove:
            del _hash_cache[k]
    # For partial hashes, include the partial_size in the key
    if partial_size > 0:
        cache_key = (key[0], key[1], key[2], partial_size)
    else:
        cache_key = key
    _hash_cache[cache_key] = hash_value


def clear_hash_cache() -> None:
    """Clear the entire hash cache."""
    global _hash_cache
    _hash_cache.clear()


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about the hash cache."""
    return {
        "size": len(_hash_cache),
        "max_size": _HASH_CACHE_MAX_SIZE
    }


#endregion
#region - Directory Cache


# Global directory cache: {dir_path: (mtime, [file_list])}
_dir_cache: Dict[str, Tuple[float, List[str]]] = {}


def get_cached_dir_listing(dir_path: str) -> List[str]:
    """Get cached directory listing, or refresh if directory has changed."""
    global _dir_cache
    dir_path = os.path.normpath(dir_path)
    try:
        current_mtime = os.stat(dir_path).st_mtime
        cached = _dir_cache.get(dir_path)
        if cached and cached[0] == current_mtime:
            return cached[1]
        # Refresh cache
        files = os.listdir(dir_path)
        _dir_cache[dir_path] = (current_mtime, files)
        return files
    except (OSError, IOError):
        return []


def invalidate_dir_cache(dir_path: str = None) -> None:
    """Invalidate directory cache for a specific path or all paths."""
    global _dir_cache
    if dir_path:
        dir_path = os.path.normpath(dir_path)
        _dir_cache.pop(dir_path, None)
    else:
        _dir_cache.clear()


#endregion
#region - File Operations


def get_md5(filename: str, chunk_size: int = 8192, partial_size: int = 0, use_cache: bool = True) -> str:
    """Calculate MD5 hash of a file.

    Args:
        filename: Path to the file to hash
        chunk_size: Size of chunks to read at a time
        partial_size: If > 0, only hash the first N bytes (for quick comparison)
        use_cache: Whether to use the hash cache

    Returns:
        MD5 hash as hex string
    """
    # Try to get from cache first
    if use_cache:
        cached = get_cached_hash(filename, partial_size, chunk_size)
        if cached:
            return cached
    m = hashlib.md5()
    bytes_read = 0
    with open(filename, 'rb') as f:
        while True:
            # If partial_size is set, limit how much we read
            if partial_size > 0:
                remaining = partial_size - bytes_read
                if remaining <= 0:
                    break
                to_read = min(chunk_size, remaining)
            else:
                to_read = chunk_size

            chunk = f.read(to_read)
            if not chunk:
                break
            m.update(chunk)
            bytes_read += len(chunk)
    hash_value = m.hexdigest()
    # Store in cache
    if use_cache:
        set_cached_hash(filename, hash_value, partial_size)
    return hash_value


def get_file_size(filepath: str) -> int:
    """Get file size, returns -1 if file doesn't exist."""
    try:
        return os.path.getsize(filepath)
    except (OSError, IOError):
        return -1


def are_files_identical(file1: str, file2: str, check_mode: str = "Similar",
                        method: str = 'Strict', max_files: int = 10,
                        chunk_size: int = 8192, partial_hash_size: int = 0,
                        app: 'Main' = None) -> Tuple[bool, Optional[str]]:
    """Compare files by size/MD5 and/or check similar files in the target directory.

    Args:
        file1: Source file path
        file2: Target file path (used to determine target directory)
        check_mode: "Similar" to check multiple similar files, "Single" for exact match only
        method: "Strict" or "Flexible" filename matching
        max_files: Maximum number of similar files to check
        chunk_size: Chunk size for MD5 calculation
        partial_hash_size: If > 0, use partial hash for initial comparison (bytes to read)
        app: Main app instance for logging warnings

    Returns:
        Tuple of (is_identical, matching_file_path)
    """
    try:
        target_dir = os.path.dirname(file2)
        file1_size = get_file_size(file1)
        if file1_size < 0:
            return False, None
        # Find similar files and check if limit was exceeded
        # Pass source file size to pre-filter by size before max_files limit is applied
        similar_files, was_truncated = find_similar_files(file1, target_dir, method, max_files, return_truncation_info=True, source_size=file1_size )
        # Log warning if max_files limit was exceeded
        if was_truncated and app:
            app.log(f"Warning: max_files limit ({max_files}) exceeded in {os.path.basename(target_dir)}. Some potential duplicates may be missed.", mode="warning")
        # Calculate source file hash (use partial hash first if enabled)
        if partial_hash_size > 0:
            file1_partial_hash = get_md5(file1, chunk_size, partial_size=partial_hash_size)
        file1_full_hash = None  # Lazy compute full hash only if needed
        for file in similar_files:
            if not os.path.exists(file):
                continue
            # Size already pre-filtered in find_similar_files, proceed to hash comparison
            # If using partial hash, check that first
            if partial_hash_size > 0:
                file_partial_hash = get_md5(file, chunk_size, partial_size=partial_hash_size)
                if file_partial_hash != file1_partial_hash:
                    continue
            # Compute full hash for final comparison
            if file1_full_hash is None:
                file1_full_hash = get_md5(file1, chunk_size)
            if get_md5(file, chunk_size) == file1_full_hash:
                return True, file
        # Single mode: also check exact filename match
        if check_mode == "Single" and os.path.exists(file2):
            if get_file_size(file2) == file1_size:
                if file1_full_hash is None:
                    file1_full_hash = get_md5(file1, chunk_size)
                if get_md5(file2, chunk_size) == file1_full_hash:
                    return True, file2
        return False, None
    except Exception as e:
        print(f"Error comparing files: {e}")
        return False, None


def find_similar_files(filename: str, target_dir: str, method: str = 'Strict',
                       max_files: int = 10, return_truncation_info: bool = False,
                       source_size: int = -1) -> List[str]:
    """Return a list of files in target_dir similar to filename based on 'method'.

    Args:
        filename: Source filename to match against
        target_dir: Directory to search in
        method: "Strict" for exact name matching with numeric suffixes,
                "Flexible" for prefix-based matching
        max_files: Maximum number of files to return
        return_truncation_info: If True, return tuple (files, was_truncated)
        source_size: If >= 0, only include files with this exact size (pre-filter
                     before max_files limit to avoid filling limit with non-matching sizes)

    Returns:
        List of similar file paths, or tuple (files, was_truncated) if return_truncation_info=True
    """
    base_name = os.path.splitext(os.path.basename(filename))[0]
    ext = os.path.splitext(filename)[1].lower()
    similar_files = []
    # Use cached directory listing
    dir_contents = get_cached_dir_listing(target_dir)
    if method == 'Strict':
        # Match exact name or name with numeric suffixes like _1, (2), -3
        pattern = re.escape(base_name) + r'([ _\-]\(\d+\)|[ _\-]\d+)?$'
        for f in dir_contents:
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                f_base, f_ext = os.path.splitext(f)
                if f_ext.lower() == ext and re.match(pattern, f_base, re.IGNORECASE):
                    # Pre-filter by size if source_size is provided
                    if source_size >= 0 and get_file_size(full_path) != source_size:
                        continue
                    similar_files.append(full_path)
        similar_files.sort(key=lambda x: SequenceMatcher(None, base_name.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
    elif method == 'Flexible':
        # Clean the base name by removing trailing numeric suffixes
        base_name_clean = base_name
        # Remove common suffix patterns: _1, _01, -1, (1), etc.
        base_name_clean = re.sub(r'[ _\-]?\(?\d+\)?$', '', base_name_clean)
        # Also try removing last underscore segment if it looks like a suffix
        if '_' in base_name_clean:
            last_segment = base_name_clean.rsplit('_', 1)[-1]
            if last_segment.isdigit() or len(last_segment) <= 3:
                base_name_clean = base_name_clean.rsplit('_', 1)[0]
        # Use prefix matching instead of substring matching to reduce false positives
        # Also match files that start with the same prefix
        for f in dir_contents:
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                f_base, f_ext = os.path.splitext(f)
                if f_ext.lower() != ext:
                    continue
                f_base_lower = f_base.lower()
                base_clean_lower = base_name_clean.lower()
                # Match if:
                # 1. File starts with our base name (prefix match)
                # 2. Our base name starts with file's base (reverse prefix)
                # 3. High similarity ratio (for cases like small edits)
                if (f_base_lower.startswith(base_clean_lower) or
                    base_clean_lower.startswith(f_base_lower) or
                    SequenceMatcher(None, base_clean_lower, f_base_lower).ratio() >= 0.8):
                    # Pre-filter by size if source_size is provided
                    if source_size >= 0 and get_file_size(full_path) != source_size:
                        continue
                    similar_files.append(full_path)
        similar_files.sort(key=lambda x: SequenceMatcher(None, base_name_clean.lower(), os.path.basename(x).lower()).ratio(), reverse=True)
    # Check if we're truncating results
    was_truncated = len(similar_files) > max_files
    result = similar_files[:max_files]
    if return_truncation_info:
        return result, was_truncated
    return result


def confirm_duplicate_storage_removal(app: 'Main'):
    """Ask the user if they want to remove the duplicate storage folder.
    Returns True if closing should continue, False if cancelled."""
    if app.duplicate_storage_path and os.path.exists(app.duplicate_storage_path):
        response = messagebox.askyesnocancel("Remove Duplicate Files?", f"Do you want to remove the duplicate files folder?\n{app.duplicate_storage_path}")
        if response is None:  # Cancel was selected
            return False  # Stop closing
        elif response:  # Yes was selected
            try:
                shutil.rmtree(app.duplicate_storage_path)
                app.log(f"Removed duplicate storage folder: {app.duplicate_storage_path}", mode="info")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove duplicate folder: {str(e)}")
        # If No was selected, keep the folder
    return True  # Continue closing


def create_duplicate_storage_folder(app: 'Main'):
    """Create a folder to store duplicate files when in 'Move' mode."""
    source_path = app.source_dir_var.get()
    source_folder_name = os.path.basename(source_path)
    parent_dir = os.path.dirname(source_path)
    duplicate_folder_name = f"{app.duplicate_name_prefix}{source_folder_name}"
    app.duplicate_storage_path = os.path.normpath(os.path.join(parent_dir, duplicate_folder_name))
    try:
        os.makedirs(app.duplicate_storage_path, exist_ok=True)
        app.log(f"Created duplicate storage folder: {app.duplicate_storage_path}", mode="info")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create duplicate storage folder: {str(e)}")
        app.duplicate_storage_path = ""


def show_duplicate_scanner(app: 'Main'):
    """Show the duplicate scanner dialog."""
    from main.ui.interactive_duplicate_scanner import duplicate_scanner_dialog
    scanner = duplicate_scanner_dialog.DuplicateScannerDialog(app.root, app)


#endregion