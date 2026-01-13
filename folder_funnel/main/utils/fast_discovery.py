#region - Imports


# Standard
from __future__ import annotations

import os
import sys
import struct
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


#endregion
#region - Public API


VolumeSupport = str  # "ntfs_mft" | "usn_journal" | "stat_walk" | "unsupported"


class FastDiscoveryError(Exception):
    """Base exception for fast discovery failures."""


class PrivilegeError(FastDiscoveryError):
    """Raised when required privileges/permissions are missing."""


def detect_volume_support(path: str) -> VolumeSupport:
    """Return the best supported discovery mode for the given path.

    Returns:
        "usn_journal" when Windows NTFS + optional pywin32 USN access is available.
        "stat_walk" for safe portable scanning via os.scandir/os.walk.
        "unsupported" only when path is invalid/unreadable.

    Notes:
        - On non-Windows platforms, always returns "stat_walk".
        - This module intentionally keeps dependencies optional and fails safe.
    """
    root_path = (path or "").strip()
    if not root_path:
        return "unsupported"
    if not os.path.exists(root_path):
        return "unsupported"
    if sys.platform != "win32":
        return "stat_walk"
    vol_root = _get_volume_root(root_path)
    if not vol_root:
        return "stat_walk"
    # Network/UNC paths: prefer safe scanning.
    if vol_root.startswith("\\\\"):
        return "stat_walk"
    fs_name = _get_fs_name_windows(vol_root)
    if not fs_name:
        return "stat_walk"
    if fs_name.upper() != "NTFS":
        return "stat_walk"
    # Prefer USN journal if pywin32 is available and accessible.
    try:
        _win32 = _try_import_pywin32()
        if _win32 is None:
            return "stat_walk"
        with _open_volume_handle(_win32, vol_root) as vol_handle:
            _query_usn_journal(_win32, vol_handle)
        return "usn_journal"
    except PrivilegeError:
        return "stat_walk"
    except Exception:
        return "stat_walk"


def enumerate_paths_via_mft(
    root_path: str,
    include_dirs: bool = True,
    batch_size: int = 1000,
    batch_callback: Optional[Callable[[list[str]], None]] = None,
) -> list[str] | None:
    """Enumerate paths under root_path using the fastest available backend.

    This is a streaming-oriented API:
        - If batch_callback is provided, it is invoked with lists of *absolute* paths.
        - If batch_callback is None, this returns a list of paths (may be large).

    Current backends:
        - Windows NTFS: USN journal (when available) for directory enumeration.
        - Fallback: scandir-based traversal.

    Args:
        root_path: Directory to enumerate.
        include_dirs: When True, enumerates directories. When False, enumerates files.
        batch_size: Max items per callback batch.
        batch_callback: Optional callback for streaming batches.

    Returns:
        List of absolute paths if batch_callback is None, otherwise None.

    Safety:
        - Never raises on transient file system changes (deleted paths).
        - Falls back to safe scanning when fast backend is unavailable.
    """
    mode = detect_volume_support(root_path)
    if batch_size <= 0:
        batch_size = 1000
    if mode == "usn_journal" and include_dirs:
        try:
            return _enumerate_dirs_via_usn(
                root_path,
                batch_size=batch_size,
                batch_callback=batch_callback,
            )
        except Exception:
            # Fail safe.
            return _enumerate_paths_via_scandir(
                root_path,
                include_dirs=include_dirs,
                batch_size=batch_size,
                batch_callback=batch_callback,
            )
    return _enumerate_paths_via_scandir(
        root_path,
        include_dirs=include_dirs,
        batch_size=batch_size,
        batch_callback=batch_callback,
    )


def get_counts_via_mft(root_path: str) -> tuple[int, int]:
    """Return (folder_count, file_count) quickly where possible.

    On Windows NTFS with USN access:
        - Counts directories/files in the subtree using USN records.

    Otherwise:
        - Uses a scandir-based walk.

    Counts match the app's existing os.walk behavior:
        - folder_count: number of subdirectories (excluding root)
        - file_count: number of files
    """
    mode = detect_volume_support(root_path)
    if mode == "usn_journal":
        try:
            return _get_counts_via_usn(root_path)
        except Exception:
            return _get_counts_via_scandir(root_path)
    return _get_counts_via_scandir(root_path)


def safe_fallback_walk(root_path: str) -> Iterable[tuple[str, list[str], list[str]]]:
    """Safe fallback walk that mirrors os.walk output.

    Uses os.walk but is wrapped so callers can rely on it not throwing
    when directories disappear mid-walk.
    """
    try:
        for dirpath, dirnames, filenames in os.walk(root_path):
            yield dirpath, dirnames, filenames
    except Exception:
        return


#endregion
#region - Windows helpers (volume + fs)


def _get_volume_root(path: str) -> str:
    try:
        abspath = os.path.abspath(path)
    except Exception:
        return ""
    drive, _ = os.path.splitdrive(abspath)
    if not drive:
        # UNC or relative; best effort.
        if abspath.startswith("\\\\"):
            parts = abspath.strip("\\").split("\\")
            if len(parts) >= 2:
                return "\\\\" + parts[0] + "\\" + parts[1] + "\\"
        return ""
    if not drive.endswith("\\"):
        drive += "\\"
    return drive


def _get_fs_name_windows(volume_root: str) -> str:
    """Best-effort filesystem name (e.g., NTFS). Returns '' on failure."""
    try:
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        GetVolumeInformationW = kernel32.GetVolumeInformationW
        GetVolumeInformationW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_wchar_p,
            ctypes.c_uint,
        ]
        GetVolumeInformationW.restype = ctypes.c_int
        fs_buf = ctypes.create_unicode_buffer(64)
        vol_buf = ctypes.create_unicode_buffer(260)
        serial = ctypes.c_uint(0)
        max_comp_len = ctypes.c_uint(0)
        flags = ctypes.c_uint(0)
        ok = GetVolumeInformationW(
            ctypes.c_wchar_p(volume_root),
            vol_buf,
            ctypes.sizeof(vol_buf),
            ctypes.byref(serial),
            ctypes.byref(max_comp_len),
            ctypes.byref(flags),
            fs_buf,
            ctypes.sizeof(fs_buf),
        )
        if not ok:
            return ""
        return (fs_buf.value or "").strip()
    except Exception:
        return ""


@dataclass(frozen=True)
class _PyWin32:
    win32file: object
    win32con: object
    pywintypes: object


def _try_import_pywin32() -> Optional[_PyWin32]:
    try:
        import win32file  # type: ignore[import-not-found]
        import win32con  # type: ignore[import-not-found]
        import pywintypes  # type: ignore[import-not-found]
        return _PyWin32(win32file=win32file, win32con=win32con, pywintypes=pywintypes)
    except Exception:
        return None


class _WinHandle:
    def __init__(self, handle, closer):
        self._handle = handle
        self._closer = closer


    def __enter__(self):
        return self._handle


    def __exit__(self, exc_type, exc, tb):
        try:
            self._closer(self._handle)
        except Exception:
            pass
        return False


def _open_volume_handle(win: _PyWin32, volume_root: str) -> _WinHandle:
    """Open a volume handle (e.g. \\\\.\\C:) for USN operations."""
    vol = volume_root.rstrip("\\")
    vol_path = f"\\\\.\\{vol}"
    try:
        handle = win.win32file.CreateFile(
            vol_path,
            win.win32con.GENERIC_READ,
            win.win32con.FILE_SHARE_READ
            | win.win32con.FILE_SHARE_WRITE
            | win.win32con.FILE_SHARE_DELETE,
            None,
            win.win32con.OPEN_EXISTING,
            0,
            None,
        )
        return _WinHandle(handle, win.win32file.CloseHandle)
    except win.pywintypes.error as exc:
        # Access denied or other Win32 errors.
        if exc.winerror in (5,):
            raise PrivilegeError(str(exc))
        raise


def _open_path_handle(win: _PyWin32, path: str) -> _WinHandle:
    """Open a directory handle so we can get its FRN."""
    try:
        handle = win.win32file.CreateFile(
            path,
            0,
            win.win32con.FILE_SHARE_READ
            | win.win32con.FILE_SHARE_WRITE
            | win.win32con.FILE_SHARE_DELETE,
            None,
            win.win32con.OPEN_EXISTING,
            win.win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        return _WinHandle(handle, win.win32file.CloseHandle)
    except win.pywintypes.error as exc:
        if exc.winerror in (5,):
            raise PrivilegeError(str(exc))
        raise


FSCTL_QUERY_USN_JOURNAL = 0x000900F4
FSCTL_ENUM_USN_DATA = 0x000900B3
FILE_ATTRIBUTE_DIRECTORY = 0x00000010


def _query_usn_journal(win: _PyWin32, vol_handle) -> tuple[int, int, int]:
    """Return (journal_id, first_usn, next_usn)."""
    out = win.win32file.DeviceIoControl(vol_handle, FSCTL_QUERY_USN_JOURNAL, None, 1024)
    if not out or len(out) < 56:
        raise FastDiscoveryError("Failed to query USN journal")
    journal_id, first_usn, next_usn, *_rest = struct.unpack_from("<QQQQQQQ", out, 0)
    return int(journal_id), int(first_usn), int(next_usn)


def _get_file_reference_number(win: _PyWin32, path_handle) -> int:
    info = win.win32file.GetFileInformationByHandle(path_handle)
    # tuple: (attrs, ctime, atime, mtime, volserial, size_hi, size_lo, links, index_hi, index_lo)
    index_hi = int(info[8])
    index_lo = int(info[9])
    return (index_hi << 32) | index_lo


#endregion
#region - USN backend (directories + counts)


def _iterate_usn_records(win: _PyWin32, vol_handle, high_usn: int):
    """Yield parsed USN_RECORD_V2 fields.

    Yields tuples: (frn, parent_frn, attrs, name)

    Notes:
        - We only parse fields needed for directory-tree reconstruction and counts.
        - This is resilient to minor record parsing issues by skipping bad records.
    """
    # MFT_ENUM_DATA_V0: StartFileReferenceNumber (Q), LowUsn (Q), HighUsn (Q)
    start_frn = 0
    low_usn = 0
    while True:
        inbuf = struct.pack("<QQQ", int(start_frn), int(low_usn), int(high_usn))
        try:
            out = win.win32file.DeviceIoControl(vol_handle, FSCTL_ENUM_USN_DATA, inbuf, 1024 * 1024)
        except win.pywintypes.error:
            return
        if not out or len(out) < 8:
            return
        start_frn = struct.unpack_from("<Q", out, 0)[0]
        pos = 8
        out_len = len(out)
        while pos + 4 <= out_len:
            rec_len = 0
            try:
                rec_len = struct.unpack_from("<I", out, pos)[0]
                if rec_len <= 0 or pos + rec_len > out_len:
                    break
                rec = out[pos : pos + rec_len]
                # USN_RECORD_V2 offsets
                frn = struct.unpack_from("<Q", rec, 8)[0]
                parent_frn = struct.unpack_from("<Q", rec, 16)[0]
                attrs = struct.unpack_from("<I", rec, 52)[0]
                name_len, name_off = struct.unpack_from("<HH", rec, 56)[0:2]
                name_bytes = rec[name_off : name_off + name_len]
                name = name_bytes.decode("utf-16le", errors="replace")
                yield int(frn), int(parent_frn), int(attrs), name
            except Exception:
                # Skip malformed record
                pass
            finally:
                # Always advance at least 4 bytes to avoid infinite loops.
                pos += int(rec_len) if rec_len else 4
        if start_frn == 0:
            return


def _build_subtree_from_usn(root_path: str):
    """Return USN-derived directory subtree + file counts keyed by parent FRN."""
    win = _try_import_pywin32()
    if win is None:
        raise FastDiscoveryError("pywin32 not installed")
    vol_root = _get_volume_root(root_path)
    if not vol_root:
        raise FastDiscoveryError("Failed to determine volume root")
    with _open_path_handle(win, root_path) as root_handle:
        root_frn = _get_file_reference_number(win, root_handle)
    with _open_volume_handle(win, vol_root) as vol_handle:
        _journal_id, _first_usn, next_usn = _query_usn_journal(win, vol_handle)
        dir_children: dict[int, list[int]] = {}
        dir_parent: dict[int, int] = {}
        dir_name: dict[int, str] = {}
        file_count_by_parent: dict[int, int] = {}
        for frn, parent_frn, attrs, name in _iterate_usn_records(win, vol_handle, next_usn):
            if attrs & FILE_ATTRIBUTE_DIRECTORY:
                # Directory
                dir_parent[frn] = parent_frn
                dir_name[frn] = name
                dir_children.setdefault(parent_frn, []).append(frn)
            else:
                # File: count by its parent directory
                file_count_by_parent[parent_frn] = int(file_count_by_parent.get(parent_frn, 0)) + 1
    # Traverse subtree from root_frn
    subtree_dirs: set[int] = {root_frn}
    stack = [root_frn]
    while stack:
        p = stack.pop()
        for child in dir_children.get(p, []):
            if child not in subtree_dirs:
                subtree_dirs.add(child)
                stack.append(child)
    return root_frn, subtree_dirs, dir_parent, dir_name, file_count_by_parent


def _get_counts_via_usn(root_path: str) -> tuple[int, int]:
    root_frn, subtree_dirs, _dir_parent, _dir_name, file_count_by_parent = _build_subtree_from_usn(root_path)
    folder_count = max(0, len(subtree_dirs) - 1)  # exclude root
    file_count = 0
    for frn in subtree_dirs:
        file_count += int(file_count_by_parent.get(frn, 0) or 0)
    return int(folder_count), int(file_count)


def _enumerate_dirs_via_usn(
    root_path: str,
    batch_size: int,
    batch_callback: Optional[Callable[[list[str]], None]],
) -> list[str] | None:
    root_frn, subtree_dirs, dir_parent, dir_name, _file_count_by_parent = _build_subtree_from_usn(root_path)
    resolved: dict[int, str] = {root_frn: ""}

    def resolve_rel(frn: int) -> Optional[str]:
        if frn in resolved:
            return resolved[frn]
        parent = dir_parent.get(frn)
        if parent is None or parent not in subtree_dirs:
            return None
        parent_rel = resolve_rel(parent)
        if parent_rel is None:
            return None
        name = (dir_name.get(frn) or "").strip()
        if not name:
            return None
        rel = os.path.join(parent_rel, name) if parent_rel else name
        resolved[frn] = rel
        return rel

    rel_paths: list[str] = []
    for frn in subtree_dirs:
        if frn == root_frn:
            continue
        rel = resolve_rel(frn)
        if rel:
            rel_paths.append(rel)
    # Deterministic order helps testing and makes UI behavior stable.
    rel_paths.sort()
    if batch_callback is None:
        return [os.path.normpath(os.path.join(root_path, rel)) for rel in rel_paths]
    batch: list[str] = []
    for rel in rel_paths:
        batch.append(os.path.normpath(os.path.join(root_path, rel)))
        if len(batch) >= batch_size:
            batch_callback(batch)
            batch = []
    if batch:
        batch_callback(batch)
    return None


#endregion
#region - Fallback backend (scandir streaming)


def _get_counts_via_scandir(root_path: str) -> tuple[int, int]:
    folder_count = 0
    file_count = 0
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            folder_count += 1
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            file_count += 1
                    except OSError:
                        continue
        except OSError:
            continue
    return int(folder_count), int(file_count)


def _enumerate_paths_via_scandir(
    root_path: str,
    include_dirs: bool,
    batch_size: int,
    batch_callback: Optional[Callable[[list[str]], None]],
) -> list[str] | None:
    if batch_callback is None:
        results: list[str] = []

        def _cb(batch: list[str]) -> None:
            results.extend(batch)

        _enumerate_paths_via_scandir(root_path, include_dirs, batch_size, _cb)
        return results
    batch: list[str] = []
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        if is_dir:
                            stack.append(entry.path)
                            if include_dirs:
                                batch.append(entry.path)
                        else:
                            if not include_dirs and entry.is_file(follow_symlinks=False):
                                batch.append(entry.path)
                    except OSError:
                        continue
                    if len(batch) >= batch_size:
                        batch_callback(batch)
                        batch = []
        except OSError:
            continue
    if batch:
        batch_callback(batch)
    return None


#endregion
