"""Command line interface."""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import __version__
from .analyzers import biggest_dirs, biggest_files, human, old_files, parse_size
from .duplicates import find_duplicates, wasted_bytes
from .scanner import scan


def _scan(args):
    print(f"Scanning {args.path} ...", file=sys.stderr)
    t = time.perf_counter()
    result = scan(args.path, exclude=tuple(args.exclude or ()))
    print(
        f"{human(result.total_size)} in {len(result.files):,} files"
        f" ({time.perf_counter() - t:.1f}s, {len(result.errors)} unreadable)",
        file=sys.stderr,
    )
    return result


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def cmd_scan(args) -> int:
    result = _scan(args)
    for d, s in biggest_dirs(result, top=args.top, depth=args.depth):
        print(f"{human(s):>10}  {d}")
    return 0


def cmd_big(args) -> int:
    result = _scan(args)
    for f in biggest_files(result, top=args.top, min_size=args.min_size):
        print(f"{human(f.size):>10}  {_date(f.mtime)}  {f.path}")
    return 0


def cmd_old(args) -> int:
    result = _scan(args)
    files = old_files(result, days=args.days, min_size=args.min_size, use_atime=args.atime)
    for f in files[: args.top]:
        ts = f.atime if args.atime else f.mtime
        print(f"{human(f.size):>10}  {_date(ts)}  {f.path}")
    print(f"Total: {human(sum(f.size for f in files))} in {len(files):,} files", file=sys.stderr)
    return 0


def cmd_dupes(args) -> int:
    result = _scan(args)
    groups = find_duplicates(result.files, min_size=args.min_size)
    for g in groups[: args.top]:
        print(f"# {len(g)} x {human(g[0].size)} (wasted {human(g[0].size * (len(g) - 1))})")
        for f in g:
            print(f"  {f.path}")
    print(f"Wasted: {human(wasted_bytes(groups))} in {len(groups):,} groups", file=sys.stderr)
    return 0


def cmd_report(args) -> int:
    from .report import render

    result = _scan(args)
    page = render(
        result,
        top=args.top,
        old_days=args.days,
        min_size=args.min_size,
        dupes=not args.no_dupes,
        redact_home=args.redact_home,
    )
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Report written to {os.path.abspath(args.output)}", file=sys.stderr)
    return 0


def cmd_trash(args) -> int:
    from .trash import move_to_trash

    paths = list(args.paths)
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as fh:
            paths += [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    if not paths:
        print("No paths given.", file=sys.stderr)
        return 2

    dry = not args.apply
    if not dry and not args.yes:
        print(f"About to move {len(paths)} item(s) to the Recycle Bin:")
        for p in paths:
            print(f"  {p}")
        if input("Type YES to continue: ").strip() != "YES":
            print("Cancelled.")
            return 1

    done, refused = move_to_trash(paths, dry_run=dry)
    verb = "Would move" if dry else "Moved"
    for p in done:
        print(f"{verb}: {p}")
    for p in refused:
        print(f"Refused (missing, link or protected location): {p}", file=sys.stderr)
    if dry:
        print("Dry run: nothing was moved. Add --apply to move to the Recycle Bin.", file=sys.stderr)
    return 0 if not refused else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bytemap",
        description="Find big, old and duplicate files. Runs fully offline.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def scan_cmd(name, help_, func, min_size="0"):
        s = sub.add_parser(name, help=help_)
        s.add_argument("path", nargs="?", default=".", help="folder to scan (default: current)")
        s.add_argument("--top", type=int, default=20, help="rows to show (default: 20)")
        s.add_argument("--min-size", type=parse_size, default=parse_size(min_size),
                       help=f"ignore smaller files, e.g. 10M (default: {min_size})")
        s.add_argument("--exclude", action="append", metavar="DIR", help="skip a folder (repeatable)")
        s.set_defaults(func=func)
        return s

    s = scan_cmd("scan", "show biggest folders", cmd_scan)
    s.add_argument("--depth", type=int, default=1, help="folder depth below path (default: 1)")
    scan_cmd("big", "show biggest files", cmd_big)
    s = scan_cmd("old", "show files not modified for N days", cmd_old)
    s.add_argument("--days", type=int, default=365, help="age in days (default: 365)")
    s.add_argument("--atime", action="store_true", help="use last access time instead of modified")
    scan_cmd("dupes", "show duplicate files", cmd_dupes, min_size="1M")
    s = scan_cmd("report", "write a self-contained HTML report", cmd_report, min_size="1M")
    s.add_argument("-o", "--output", default="bytemap-report.html", help="output file")
    s.add_argument("--days", type=int, default=365, help="age for the old-files table")
    s.add_argument("--no-dupes", action="store_true", help="skip duplicate detection (faster)")
    s.add_argument("--redact-home", action="store_true",
                   help="replace your home folder path with ~ in the report")
    s.set_defaults(top=50)

    t = sub.add_parser("trash", help="move files to the Recycle Bin (dry run by default)")
    t.add_argument("paths", nargs="*", help="files or folders to move")
    t.add_argument("--from-file", help="text file with one path per line")
    t.add_argument("--apply", action="store_true", help="really move (otherwise dry run)")
    t.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    t.set_defaults(func=cmd_trash)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
