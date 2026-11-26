"""Move files to the OS recycle bin. Never deletes permanently."""

from __future__ import annotations

import os
import sys

# Locations ByteMap refuses to touch, regardless of user input.
_WINDOWS_PROTECTED = (
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
)
_POSIX_PROTECTED = (
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/sbin",
    "/sys", "/usr", "/var", "/System", "/Library", "/Applications",
)


def _protected_roots() -> list[str]:
    if sys.platform == "win32":
        roots = list(_WINDOWS_PROTECTED)
        for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
            if os.environ.get(var):
                roots.append(os.environ[var])
        return roots
    return list(_POSIX_PROTECTED)


def is_protected(path: str) -> bool:
    """True for system locations, filesystem roots and the user-profile folders themselves."""
    full = os.path.normcase(os.path.abspath(path))
    if os.path.dirname(full) == full:  # drive or filesystem root
        return True
    # The home folder and the folder that holds all profiles (C:\Users, /home) are refused
    # as a whole; files and subfolders inside them are allowed.
    home = os.path.normcase(os.path.abspath(os.path.expanduser("~")))
    if full in (home, os.path.dirname(home)):
        return True
    for root in _protected_roots():
        r = os.path.normcase(os.path.abspath(root))
        if full == r or full.startswith(r.rstrip(os.sep) + os.sep):
            return True
    return False


def move_to_trash(paths: list[str], dry_run: bool = True) -> tuple[list[str], list[str]]:
    """Send ``paths`` to the recycle bin.

    Returns ``(done, refused)``. With ``dry_run`` nothing is moved and ``done``
    lists what would be moved.
    """
    done: list[str] = []
    refused: list[str] = []
    for p in paths:
        if is_protected(p) or not os.path.lexists(p) or os.path.islink(p):
            refused.append(p)
            continue
        if not dry_run:
            from send2trash import send2trash  # imported lazily: optional at analysis time

            try:
                send2trash(p)
            except OSError:
                refused.append(p)
                continue
        done.append(p)
    return done, refused
