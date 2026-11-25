"""Filesystem walker. Iterative (no recursion limit), never follows links."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    mtime: float
    atime: float


@dataclass
class ScanResult:
    root: str
    files: list[FileInfo] = field(default_factory=list)
    dir_sizes: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return self.dir_sizes.get(self.root, 0)


def _is_link(entry: os.DirEntry) -> bool:
    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)  # Python 3.12+
    return bool(is_junction and is_junction())


def scan(root: str, exclude: tuple[str, ...] = ()) -> ScanResult:
    """Walk ``root`` and collect file metadata and cumulative directory sizes.

    Symlinks and Windows junctions are skipped to avoid loops and double counting.
    Unreadable entries are recorded in ``errors`` and skipped.
    """
    root = os.path.abspath(root)
    result = ScanResult(root=root)
    excluded = {os.path.normcase(os.path.abspath(e)) for e in exclude}
    own_sizes: dict[str, int] = {}
    parents: dict[str, str] = {}
    stack = [root]

    while stack:
        current = stack.pop()
        own_sizes.setdefault(current, 0)
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError as exc:
            result.errors.append(f"{current}: {exc.strerror or exc}")
            continue
        for entry in entries:
            try:
                if _is_link(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if os.path.normcase(entry.path) in excluded:
                        continue
                    parents[entry.path] = current
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    st = entry.stat(follow_symlinks=False)
                    result.files.append(
                        FileInfo(entry.path, st.st_size, st.st_mtime, st.st_atime)
                    )
                    own_sizes[current] += st.st_size
            except OSError as exc:
                result.errors.append(f"{entry.path}: {exc.strerror or exc}")

    # Roll up sizes: deepest directories first.
    totals = dict(own_sizes)
    for d in sorted(own_sizes, key=lambda p: p.count(os.sep), reverse=True):
        parent = parents.get(d)
        if parent is not None:
            totals[parent] = totals.get(parent, 0) + totals[d]
    result.dir_sizes = totals
    return result
