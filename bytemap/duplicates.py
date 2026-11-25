"""Duplicate finder: group by size, then partial hash, then full SHA-256."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Iterable

from .scanner import FileInfo

CHUNK = 1024 * 1024
PARTIAL = 64 * 1024


def _hash(path: str, limit: int | None = None) -> str | None:
    h = hashlib.sha256()
    read = 0
    try:
        with open(path, "rb") as fh:
            while limit is None or read < limit:
                size = CHUNK if limit is None else min(CHUNK, limit - read)
                block = fh.read(size)
                if not block:
                    break
                h.update(block)
                read += len(block)
    except OSError:
        return None
    return h.hexdigest()


def _regroup(groups: Iterable[list[FileInfo]], key: Callable[[FileInfo], str | None]):
    for group in groups:
        buckets: dict[str, list[FileInfo]] = defaultdict(list)
        for f in group:
            k = key(f)
            if k is not None:
                buckets[k].append(f)
        yield from (b for b in buckets.values() if len(b) > 1)


def find_duplicates(files: Iterable[FileInfo], min_size: int = 1) -> list[list[FileInfo]]:
    """Return groups of identical files, sorted by wasted space (largest first)."""
    by_size: dict[int, list[FileInfo]] = defaultdict(list)
    for f in files:
        if f.size >= max(min_size, 1):
            by_size[f.size].append(f)
    groups = [g for g in by_size.values() if len(g) > 1]
    groups = list(_regroup(groups, lambda f: _hash(f.path, PARTIAL)))
    groups = list(_regroup(groups, lambda f: _hash(f.path)))
    for g in groups:
        g.sort(key=lambda f: f.path)
    return sorted(groups, key=lambda g: g[0].size * (len(g) - 1), reverse=True)


def wasted_bytes(groups: list[list[FileInfo]]) -> int:
    return sum(g[0].size * (len(g) - 1) for g in groups)
