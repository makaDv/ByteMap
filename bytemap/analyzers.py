"""Queries over a ScanResult: biggest files, old files, biggest folders."""

from __future__ import annotations

import heapq
import os
import time

from .scanner import FileInfo, ScanResult

DAY = 86400


def biggest_files(result: ScanResult, top: int = 20, min_size: int = 0) -> list[FileInfo]:
    candidates = (f for f in result.files if f.size >= min_size)
    return heapq.nlargest(top, candidates, key=lambda f: f.size)


def old_files(
    result: ScanResult,
    days: int = 365,
    min_size: int = 0,
    use_atime: bool = False,
    now: float | None = None,
) -> list[FileInfo]:
    """Files not modified (or accessed, with ``use_atime``) for ``days`` days, biggest first."""
    cutoff = (now if now is not None else time.time()) - days * DAY
    old = [
        f
        for f in result.files
        if f.size >= min_size and (f.atime if use_atime else f.mtime) < cutoff
    ]
    return sorted(old, key=lambda f: f.size, reverse=True)


def biggest_dirs(result: ScanResult, top: int = 20, depth: int = 1) -> list[tuple[str, int]]:
    """Largest directories exactly ``depth`` levels below the scan root."""
    base = result.root.rstrip(os.sep).count(os.sep)
    rows = [
        (d, s)
        for d, s in result.dir_sizes.items()
        if d.rstrip(os.sep).count(os.sep) - base == depth
    ]
    return heapq.nlargest(top, rows, key=lambda r: r[1])


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def parse_size(text: str) -> int:
    """Parse '500', '10K', '1.5M', '2G' (base 1024) into bytes."""
    text = text.strip().upper().removesuffix("B")
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    if text and text[-1] in mult:
        return int(float(text[:-1]) * mult[text[-1]])
    return int(float(text))
