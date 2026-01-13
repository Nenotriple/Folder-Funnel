#region - Imports


# Standard
import os
import re
import shutil
import hashlib
import threading
from typing import List, Dict, Tuple, Optional, Any
from difflib import SequenceMatcher

# Third-Party
import nenotk as ntk

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Main


#endregion
#region - Hash Cache


class FileNotReadyError(Exception):
    """Raised when a file can't be reliably read yet (locked / still being written)."""


# Cache key shape:
#   (norm_path, mtime, size, partial_size, partial_mode)
# where partial_size=0 and partial_mode='full' represents full-file hashing.


# Global hash cache: {(file_path, mtime, size): hash_value}
_hash_cache: Dict[Tuple[Any, ...], str] = {}
_HASH_CACHE_MAX_SIZE = 10000  # Maximum number of cached hashes
_hash_cache_lock = threading.Lock()


def get_file_key(filepath: str) -> Optional[Tuple[str, float, int]]:
    """Get a cache key for a file based on path, mtime, and size.
    Returns None if file doesn't exist or can't be accessed."""
    try:
        stat = os.stat(filepath)
        # normcase is important on Windows to avoid duplicate entries due to path casing
        return (os.path.normcase(os.path.normpath(filepath)), stat.st_mtime, stat.st_size)
    except (OSError, IOError):
        return None


def _make_hash_cache_key(filepath: str, partial_size: int, partial_mode: str) -> Optional[Tuple[Any, ...]]:
    key = get_file_key(filepath)
    if key is None:
        return None
    if partial_size > 0:
        return (key[0], key[1], key[2], int(partial_size), str(partial_mode))
    return (key[0], key[1], key[2], 0, "full")


def get_cached_hash(filepath: str, partial_size: int = 0, chunk_size: int = 8192, partial_mode: str = "head_tail") -> Optional[str]:
    """Get hash from cache if available and file hasn't changed.
    Returns None if not cached or file has been modified."""
    # chunk_size is intentionally not part of the cache key
    cache_key = _make_hash_cache_key(filepath, partial_size, partial_mode)
    if cache_key is None:
        return None
    with _hash_cache_lock:
        return _hash_cache.get(cache_key)


def set_cached_hash(filepath: str, hash_value: str, partial_size: int = 0, partial_mode: str = "head_tail") -> None:
    """Store a hash in the cache."""
    global _hash_cache
    with _hash_cache_lock:
        # Evict oldest entries if cache is too large
        if len(_hash_cache) >= _HASH_CACHE_MAX_SIZE:
            # Remove 20% of oldest entries (simple eviction strategy)
            to_remove = list(_hash_cache.keys())[:_HASH_CACHE_MAX_SIZE // 5]
            for k in to_remove:
                del _hash_cache[k]
        cache_key = _make_hash_cache_key(filepath, partial_size, partial_mode)
        if cache_key is None:
            return
        _hash_cache[cache_key] = hash_value


def clear_hash_cache() -> None:
    """Clear the entire hash cache."""
    global _hash_cache
    with _hash_cache_lock:
        _hash_cache.clear()


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about the hash cache."""
    with _hash_cache_lock:
        return {
            "size": len(_hash_cache),
            "max_size": _HASH_CACHE_MAX_SIZE
        }


#endregion
#region - Directory Cache


# Global directory cache: {dir_path: (mtime, [file_list])}
_dir_cache: Dict[str, Tuple[float, List[str]]] = {}
_dir_cache_lock = threading.Lock()


def get_cached_dir_listing(dir_path: str) -> List[str]:
    """Get cached directory listing, or refresh if directory has changed."""
    global _dir_cache
    dir_path = os.path.normpath(dir_path)
    try:
        current_mtime = os.stat(dir_path).st_mtime
        with _dir_cache_lock:
            cached = _dir_cache.get(dir_path)
            if cached and cached[0] == current_mtime:
                return cached[1]
        # Refresh cache outside lock when hitting filesystem
        files = os.listdir(dir_path)
        with _dir_cache_lock:
            _dir_cache[dir_path] = (current_mtime, files)
        return files
    except (OSError, IOError):
        return []


def invalidate_dir_cache(dir_path: str = None) -> None:
    """Invalidate directory cache for a specific path or all paths."""
    global _dir_cache
    with _dir_cache_lock:
        if dir_path:
            dir_path = os.path.normpath(dir_path)
            _dir_cache.pop(dir_path, None)
        else:
            _dir_cache.clear()


#endregion
#region - File Operations


def get_md5(
    filename: str,
    chunk_size: int = 8192,
    partial_size: int = 0,
    use_cache: bool = True,
    partial_mode: str = "head_tail",
) -> str:
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
        cached = get_cached_hash(filename, partial_size, chunk_size, partial_mode=partial_mode)
        if cached:
            return cached
    try:
        file_size = os.path.getsize(filename)
    except (OSError, IOError) as exc:
        raise FileNotReadyError(str(exc)) from exc
    m = hashlib.md5()
    try:
        with open(filename, 'rb') as f:
            if partial_size > 0:
                # Head
                remaining = min(int(partial_size), int(file_size))
                bytes_read = 0
                while remaining > 0:
                    to_read = min(chunk_size, remaining)
                    chunk = f.read(to_read)
                    if not chunk:
                        break
                    m.update(chunk)
                    bytes_read += len(chunk)
                    remaining -= len(chunk)
                # Tail (reduces collisions vs header-only; still cheap)
                if partial_mode == "head_tail" and file_size > (2 * int(partial_size)):
                    try:
                        f.seek(-int(partial_size), os.SEEK_END)
                        tail = f.read(int(partial_size))
                        if tail:
                            m.update(tail)
                    except (OSError, IOError):
                        # If seeking fails for any reason, fall back to header-only
                        pass
            else:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    m.update(chunk)
    except (PermissionError, OSError, IOError) as exc:
        raise FileNotReadyError(str(exc)) from exc
    hash_value = m.hexdigest()
    # Store in cache
    if use_cache:
        set_cached_hash(filename, hash_value, partial_size, partial_mode=partial_mode)
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
        file1_size = get_file_size(file1)
        if file1_size < 0:
            return False, None
        target_dir = os.path.dirname(file2)
        file1_partial_hash: Optional[str] = None
        file1_full_hash: Optional[str] = None

        def _partial_hash(path: str) -> str:
            return get_md5(path, chunk_size, partial_size=partial_hash_size, partial_mode="head_tail")

        def _full_hash(path: str) -> str:
            return get_md5(path, chunk_size)

        # Fast path: always check the exact destination file first (most likely candidate)
        if os.path.exists(file2) and get_file_size(file2) == file1_size:
            if partial_hash_size > 0:
                if file1_partial_hash is None:
                    file1_partial_hash = _partial_hash(file1)
                if _partial_hash(file2) == file1_partial_hash:
                    file1_full_hash = file1_full_hash or _full_hash(file1)
                    if _full_hash(file2) == file1_full_hash:
                        return True, file2
            else:
                file1_full_hash = file1_full_hash or _full_hash(file1)
                if _full_hash(file2) == file1_full_hash:
                    return True, file2
        # Single mode: only check the exact destination file
        if check_mode == "Single":
            return False, None
        # Find other similar files (name-first, then size filter) and check if limit was exceeded
        similar_files, was_truncated = find_similar_files(file1, target_dir, method, max_files, return_truncation_info=True, source_size=file1_size)
        if was_truncated and app:
            app.log(f"Warning: max_files limit ({max_files}) reached in {os.path.basename(target_dir)}, some duplicates may be missed", mode="warning", verbose=2)
        checked = 0
        full_md5_computes = 0
        for candidate in similar_files:
            if candidate == file2:
                continue  # already checked
            if not os.path.exists(candidate):
                continue
            # Size is pre-filtered (when source_size >= 0)
            if partial_hash_size > 0:
                if file1_partial_hash is None:
                    file1_partial_hash = _partial_hash(file1)
                try:
                    if _partial_hash(candidate) != file1_partial_hash:
                        continue
                except FileNotReadyError:
                    continue
            if file1_full_hash is None:
                file1_full_hash = _full_hash(file1)
                full_md5_computes += 1
            if _full_hash(candidate) == file1_full_hash:
                return True, candidate
            checked += 1
        if app and getattr(app, "log_verbosity_var", None) and app.log_verbosity_var.get() >= 4:
            app.log(f"Dupe check stats: candidates={len(similar_files)}, checked={checked}, full_md5_source={full_md5_computes}", mode="simple", verbose=4)
        return False, None
    except FileNotReadyError:
        # Let the caller decide how/when to retry.
        raise
    except Exception as e:
        if app:
            app.log(f"Error comparing files: {e}", mode="warning", verbose=2)
        else:
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
    base_lower = base_name.lower()
    ext = os.path.splitext(filename)[1].lower()
    # Use cached directory listing
    dir_contents = get_cached_dir_listing(target_dir)
    exact: List[str] = []
    suffix: List[str] = []
    other: List[str] = []
    # Flexible base cleanup is used only when method == 'Flexible'
    base_name_clean = base_name
    if method == 'Flexible':
        # Remove common suffix patterns: _1, _01, -1, (1), etc.
        base_name_clean = re.sub(r'[ _\-]?\(?\d+\)?$', '', base_name_clean)
        # Only strip last underscore segment if it looks like a numeric suffix (avoid over-broad trimming)
        if '_' in base_name_clean:
            last_segment = base_name_clean.rsplit('_', 1)[-1]
            if last_segment.isdigit():
                base_name_clean = base_name_clean.rsplit('_', 1)[0]
    base_clean_lower = base_name_clean.lower()

    def _is_numeric_suffix(rest: str) -> bool:
        if not rest:
            return False
        if rest.startswith((' ', '_', '-')):
            rest = rest[1:]
        if not rest:
            return False
        if rest.startswith('(') and rest.endswith(')'):
            rest = rest[1:-1]
        return rest.isdigit()

    # First pass: cheap name-based filtering only
    for f in dir_contents:
        # Fast extension check
        if not f.lower().endswith(ext):
            continue
        full_path = os.path.join(target_dir, f)
        if not os.path.isfile(full_path):
            continue
        f_base, _ = os.path.splitext(f)
        f_base_lower = f_base.lower()
        if f_base_lower == base_lower:
            exact.append(full_path)
            continue
        if method == 'Strict':
            if f_base_lower.startswith(base_lower):
                rest = f_base_lower[len(base_lower):]
                if _is_numeric_suffix(rest):
                    suffix.append(full_path)
                    continue
        else:  # Flexible
            if f_base_lower.startswith(base_clean_lower) or base_clean_lower.startswith(f_base_lower):
                suffix.append(full_path)
                continue
            # Only compute similarity for plausible candidates
            if f_base_lower[:3] == base_clean_lower[:3] and abs(len(f_base_lower) - len(base_clean_lower)) <= 12:
                if SequenceMatcher(None, base_clean_lower, f_base_lower).ratio() >= 0.85:
                    other.append(full_path)
                    continue
    # Size pre-filter (do it after name filtering to avoid stat'ing huge directories)
    if source_size >= 0:
        def _size_ok(p: str) -> bool:
            return get_file_size(p) == source_size
        exact = [p for p in exact if _size_ok(p)]
        suffix = [p for p in suffix if _size_ok(p)]
        other = [p for p in other if _size_ok(p)]
    # Rank only the non-obvious candidates by similarity to keep things fast
    ranked_other: List[str] = []
    if other:
        ranked_other = sorted(other, key=lambda x: SequenceMatcher(None, base_clean_lower, os.path.splitext(os.path.basename(x))[0].lower()).ratio(), reverse=True)
    ordered: List[str] = []
    seen: set[str] = set()
    for group in (exact, suffix, ranked_other):
        for p in group:
            if p not in seen:
                ordered.append(p)
                seen.add(p)
    was_truncated = len(ordered) > max_files
    result = ordered[:max_files]
    if return_truncation_info:
        return result, was_truncated
    return result


def confirm_duplicate_storage_removal(app: 'Main'):
    """Ask the user if they want to remove the duplicate storage folder.
    Returns True if closing should continue, False if cancelled."""
    if app.duplicate_storage_path and os.path.exists(app.duplicate_storage_path):
        response = ntk.askyesnocancel("Remove Duplicate Files?", prompt="Remove duplicate files folder?", detail=app.duplicate_storage_path)
        if response is None:  # Cancel was selected
            return False  # Stop closing
        elif response:  # Yes was selected
            try:
                shutil.rmtree(app.duplicate_storage_path)
                app.log(f"Removed duplicate storage folder: {app.duplicate_storage_path}", mode="info", verbose=1)
            except Exception as e:
                app.log(f"Failed to remove duplicate folder: {str(e)}", mode="error", verbose=1)
                ntk.showinfo("Error", f"Failed to remove duplicate folder: {str(e)}")
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
        app.log(f"Created duplicate storage folder: {app.duplicate_storage_path}", mode="info", verbose=2)
    except Exception as e:
        app.log(f"Failed to create duplicate storage folder: {str(e)}", mode="error", verbose=1)
        ntk.showinfo("Error", f"Failed to create duplicate storage folder: {str(e)}")
        app.duplicate_storage_path = ""


def show_duplicate_scanner(app: 'Main'):
    """Show the duplicate scanner dialog."""
    from main.ui.interactive_duplicate_scanner import duplicate_scanner_dialog
    scanner = duplicate_scanner_dialog.DuplicateScannerDialog(app.root, app)


#endregion