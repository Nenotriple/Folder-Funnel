#region - Imports


# Standard
from __future__ import annotations

import os
from typing import Callable, Iterable, Optional


#endregion
#region - Public API


VolumeSupport = str  # "stat_walk" | "unsupported"


class FastDiscoveryError(Exception):
    """Base exception for fast discovery failures."""


class PrivilegeError(FastDiscoveryError):
    """Raised when required privileges/permissions are missing."""


def detect_volume_support(path: str) -> VolumeSupport:
    """Return the supported discovery mode for the given path.

    This simplified implementation always prefers a safe, portable
    scandir-based traversal. It is optimized and resilient to transient
    file system changes without relying on platform-specific APIs.
    """
    root_path = (path or "").strip()
    if not root_path or not os.path.exists(root_path):
        return "unsupported"
    return "stat_walk"


def enumerate_paths_via_mft(
    root_path: str,
    include_dirs: bool = True,
    batch_size: int = 1000,
    batch_callback: Optional[Callable[[list[str]], None]] = None,
) -> list[str] | None:
    """Enumerate paths under root_path using a fast scandir traversal.

    This is a streaming-oriented API:
        - If batch_callback is provided, it is invoked with lists of *absolute* paths.
        - If batch_callback is None, this returns a list of paths (may be large).

    Safety:
        - Never raises on transient file system changes (deleted paths).
    """
    if batch_size <= 0:
        batch_size = 1000
    if detect_volume_support(root_path) == "unsupported":
        return [] if batch_callback is None else None
    return _enumerate_paths_via_scandir(
        root_path,
        include_dirs=include_dirs,
        batch_size=batch_size,
        batch_callback=batch_callback,
    )


def get_counts_via_mft(root_path: str) -> tuple[int, int]:
    """Return (folder_count, file_count) using a fast scandir walk.

    Counts match the app's existing os.walk behavior:
        - folder_count: number of subdirectories (excluding root)
        - file_count: number of files
    """
    if detect_volume_support(root_path) == "unsupported":
        return 0, 0
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
