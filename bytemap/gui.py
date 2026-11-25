"""Graphical interface (Tkinter, included with Python: no extra install).

Start with:  python -m bytemap gui   or   python -m bytemap.gui
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .analyzers import biggest_files, human, old_files, parse_size
from .duplicates import find_duplicates, wasted_bytes
from .scanner import ScanResult, scan
from .trash import move_to_trash

SIZES = ["0", "100K", "1M", "10M", "100M", "1G"]
DISCLAIMER = (
    "ByteMap is provided \"as is\", without warranty of any kind (MIT license).\n\n"
    "It only moves files to the Recycle Bin, never deletes them permanently, "
    "and refuses system folders. Still, check what you select and keep backups "
    "of important data.\n\n"
    "ByteMap works fully offline: no data leaves your computer."
)


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def open_location(path: str) -> None:
    """Show ``path`` in the system file manager (no shell involved)."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path) or path])


class Table(ttk.Frame):
    """Treeview with scrollbars, sortable columns and a path per row."""

    def __init__(self, master, columns: list[tuple[str, int, str]]):
        super().__init__(master)
        self.columns = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.columns, show="tree headings", selectmode="extended")
        self.tree.column("#0", width=0, stretch=False)
        for name, width, anchor in columns:
            self.tree.heading(name, text=name, command=lambda n=name: self.sort(n))
            self.tree.column(name, width=width, anchor=anchor, stretch=(name == "Path"))
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.paths: dict[str, str] = {}
        self.keys: dict[str, dict[str, object]] = {}
        self._desc: dict[str, bool] = {}

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.paths.clear()
        self.keys.clear()

    def add(self, values: list[str], path: str | None = None, keys: dict | None = None,
            parent: str = "", open_: bool = False) -> str:
        iid = self.tree.insert(parent, "end", values=values, open=open_)
        if path:
            self.paths[iid] = path
        self.keys[iid] = keys or {}
        return iid

    def sort(self, col: str) -> None:
        desc = self._desc[col] = not self._desc.get(col, col in ("Size", "Wasted"))
        idx = self.columns.index(col)

        def key(iid):
            k = self.keys.get(iid, {})
            return k.get(col, str(self.tree.set(iid, self.columns[idx])).lower())

        for parent in {""} | set(self.tree.get_children("")):
            items = sorted(self.tree.get_children(parent), key=key, reverse=desc)
            for i, iid in enumerate(items):
                self.tree.move(iid, parent, i)

    def selected_paths(self) -> list[str]:
        return [self.paths[i] for i in self.tree.selection() if i in self.paths]

    def remove_paths(self, paths: set[str]) -> None:
        for iid, p in list(self.paths.items()):
            if p in paths and self.tree.exists(iid):
                self.tree.delete(iid)
                del self.paths[iid]


class App(tk.Tk):
    def __init__(self, start: str | None = None):
        super().__init__()
        self.title(f"ByteMap {__version__}")
        self.geometry("1100x680")
        self.minsize(760, 420)
        self.result: ScanResult | None = None
        self.children_map: dict[str, list[str]] = {}
        self.current_dir: str | None = None
        self.events: queue.Queue = queue.Queue()
        self.busy = False

        self.folder = tk.StringVar(value=start or os.path.expanduser("~"))
        self.min_size = tk.StringVar(value="1M")
        self.days = tk.IntVar(value=365)
        self.redact = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Choose a folder and press Scan.")

        self._build()
        self.after(100, self._poll)

    # ---------- layout ----------
    def _build(self) -> None:
        pad = {"padx": 4, "pady": 4}
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Folder:").pack(side="left", **pad)
        entry = ttk.Entry(top, textvariable=self.folder)
        entry.pack(side="left", fill="x", expand=True, **pad)
        entry.bind("<Return>", lambda e: self.start_scan())
        ttk.Button(top, text="Browse...", command=self.browse).pack(side="left", **pad)
        self.scan_btn = ttk.Button(top, text="Scan", command=self.start_scan)
        self.scan_btn.pack(side="left", **pad)

        opts = ttk.Frame(self, padding=(6, 0))
        opts.pack(fill="x")
        ttk.Label(opts, text="Min file size:").pack(side="left", **pad)
        size = ttk.Combobox(opts, textvariable=self.min_size, values=SIZES, width=7)
        size.pack(side="left", **pad)
        ttk.Label(opts, text="Old = not modified for").pack(side="left", **pad)
        ttk.Spinbox(opts, from_=30, to=7300, increment=30, textvariable=self.days, width=6).pack(side="left")
        ttk.Label(opts, text="days").pack(side="left", **pad)
        ttk.Button(opts, text="Apply filters", command=self.refresh).pack(side="left", **pad)
        ttk.Button(opts, text="About / Disclaimer", command=self.about).pack(side="right", **pad)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=6, pady=6)

        # Folders tab with drill-down
        f = ttk.Frame(self.tabs)
        nav = ttk.Frame(f)
        nav.pack(fill="x")
        ttk.Button(nav, text="Up", command=self.go_up).pack(side="left", padx=2, pady=2)
        self.crumb = ttk.Label(nav, text="")
        self.crumb.pack(side="left", padx=6)
        self.t_dirs = Table(f, [("Size", 90, "e"), ("Share", 60, "e"), ("Subfolders", 80, "e"), ("Path", 600, "w")])
        self.t_dirs.pack(fill="both", expand=True)
        self.t_dirs.tree.bind("<Double-1>", self.drill_down)
        self.tabs.add(f, text="Folders")

        self.t_big = Table(self.tabs, [("Size", 90, "e"), ("Modified", 90, "center"), ("Path", 700, "w")])
        self.tabs.add(self.t_big, text="Big files")
        self.t_old = Table(self.tabs, [("Size", 90, "e"), ("Modified", 90, "center"), ("Path", 700, "w")])
        self.tabs.add(self.t_old, text="Old files")

        d = ttk.Frame(self.tabs)
        bar = ttk.Frame(d)
        bar.pack(fill="x")
        self.dupe_btn = ttk.Button(bar, text="Find duplicates", command=self.start_dupes)
        self.dupe_btn.pack(side="left", padx=2, pady=2)
        ttk.Label(bar, text="Compares file contents (SHA-256). Can take a while on big folders.").pack(side="left", padx=6)
        self.t_dupes = Table(d, [("Wasted", 90, "e"), ("Size", 90, "e"), ("Path", 700, "w")])
        self.t_dupes.pack(fill="both", expand=True)
        self.tabs.add(d, text="Duplicates")

        for t in (self.t_dirs, self.t_big, self.t_old, self.t_dupes):
            t.tree.bind("<Delete>", lambda e: self.trash_selected())

        actions = ttk.Frame(self, padding=6)
        actions.pack(fill="x")
        ttk.Button(actions, text="Show in folder", command=self.show_selected).pack(side="left", **pad)
        ttk.Button(actions, text="Copy path", command=self.copy_selected).pack(side="left", **pad)
        ttk.Button(actions, text="Move to Recycle Bin", command=self.trash_selected).pack(side="left", **pad)
        ttk.Button(actions, text="Export HTML report...", command=self.export_report).pack(side="right", **pad)
        ttk.Checkbutton(actions, text="Hide my home folder in report", variable=self.redact).pack(side="right", **pad)

        bottom = ttk.Frame(self, padding=(6, 0, 6, 6))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=140)
        self.progress.pack(side="right")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")

    # ---------- helpers ----------
    def current_table(self) -> Table:
        tab = self.tabs.index(self.tabs.select())
        return [self.t_dirs, self.t_big, self.t_old, self.t_dupes][tab]

    def _min_size(self) -> int:
        try:
            return parse_size(self.min_size.get() or "0")
        except ValueError:
            messagebox.showerror("ByteMap", "Invalid size. Examples: 0, 500K, 10M, 1G")
            raise

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.dupe_btn.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress["value"] = 0
        if text:
            self.status.set(text)

    def _run(self, kind: str, func, *args) -> None:
        def worker():
            try:
                self.events.put((kind, func(*args), None))
            except Exception as exc:  # report any failure to the UI thread
                self.events.put((kind, None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self) -> None:
        try:
            while True:
                kind, value, error = self.events.get_nowait()
                self._set_busy(False)
                if error:
                    messagebox.showerror("ByteMap", f"{type(error).__name__}: {error}")
                    self.status.set("Error.")
                elif kind == "scan":
                    self._scan_done(value)
                elif kind == "dupes":
                    self._dupes_done(value)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ---------- actions ----------
    def browse(self) -> None:
        d = filedialog.askdirectory(initialdir=self.folder.get() or None, title="Folder to scan")
        if d:
            self.folder.set(os.path.normpath(d))

    def start_scan(self) -> None:
        path = self.folder.get().strip()
        if self.busy:
            return
        if not os.path.isdir(path):
            messagebox.showerror("ByteMap", "Folder not found.")
            return
        self._set_busy(True, f"Scanning {path} ...")
        self.t_dupes.clear()
        self._t0 = time.perf_counter()
        self._run("scan", scan, path)

    def _scan_done(self, result: ScanResult) -> None:
        self.result = result
        self.children_map = defaultdict(list)
        for d in result.dir_sizes:
            parent = os.path.dirname(d)
            if d != result.root and parent in result.dir_sizes:
                self.children_map[parent].append(d)
        self.current_dir = result.root
        self.refresh()
        self.status.set(
            f"{human(result.total_size)} in {len(result.files):,} files, "
            f"{time.perf_counter() - self._t0:.1f}s, {len(result.errors)} unreadable."
        )

    def refresh(self) -> None:
        if not self.result:
            return
        try:
            min_size = self._min_size()
            days = int(self.days.get())
        except (ValueError, tk.TclError):
            return
        self.show_dir(self.current_dir or self.result.root)
        self.t_big.clear()
        for f in biggest_files(self.result, top=500, min_size=min_size):
            self.t_big.add([human(f.size), _date(f.mtime), f.path], f.path, {"Size": f.size})
        self.t_old.clear()
        old = old_files(self.result, days=days, min_size=min_size)
        for f in old[:2000]:
            self.t_old.add([human(f.size), _date(f.mtime), f.path], f.path, {"Size": f.size})
        self.tabs.tab(2, text=f"Old files ({human(sum(f.size for f in old))})")

    def show_dir(self, path: str) -> None:
        assert self.result
        self.current_dir = path
        total = self.result.dir_sizes.get(path, 0) or 1
        self.crumb.configure(text=f"{path}   ({human(self.result.dir_sizes.get(path, 0))})")
        self.t_dirs.clear()
        subs = sorted(self.children_map.get(path, []), key=lambda p: self.result.dir_sizes[p], reverse=True)
        for s in subs:
            size = self.result.dir_sizes[s]
            n = len(self.children_map.get(s, []))
            self.t_dirs.add([human(size), f"{size * 100 / total:.1f}%", str(n), s], s,
                            {"Size": size, "Share": size, "Subfolders": n})

    def drill_down(self, _event=None) -> None:
        paths = self.t_dirs.selected_paths()
        if paths and self.children_map.get(paths[0]):
            self.show_dir(paths[0])

    def go_up(self) -> None:
        if self.result and self.current_dir and self.current_dir != self.result.root:
            self.show_dir(os.path.dirname(self.current_dir))

    def start_dupes(self) -> None:
        if self.busy:
            return
        if not self.result:
            messagebox.showinfo("ByteMap", "Scan a folder first.")
            return
        try:
            min_size = max(self._min_size(), 1)
        except ValueError:
            return
        self._set_busy(True, "Comparing files ...")
        self._run("dupes", find_duplicates, list(self.result.files), min_size)

    def _dupes_done(self, groups) -> None:
        self.t_dupes.clear()
        for g in groups:
            wasted = g[0].size * (len(g) - 1)
            parent = self.t_dupes.add([human(wasted), f"{len(g)} x {human(g[0].size)}", os.path.basename(g[0].path)],
                                      keys={"Wasted": wasted, "Size": g[0].size}, open_=True)
            for f in g:
                self.t_dupes.add(["", human(f.size), f.path], f.path, {"Size": f.size}, parent=parent)
        self.status.set(f"{len(groups):,} duplicate groups, {human(wasted_bytes(groups))} wasted. "
                        "Select the copies to remove (keep at least one!).")

    def show_selected(self) -> None:
        paths = self.current_table().selected_paths()
        if paths:
            open_location(paths[0])

    def copy_selected(self) -> None:
        paths = self.current_table().selected_paths()
        if paths:
            self.clipboard_clear()
            self.clipboard_append("\n".join(paths))
            self.status.set(f"Copied {len(paths)} path(s).")

    def trash_selected(self) -> None:
        table = self.current_table()
        paths = table.selected_paths()
        if not paths:
            messagebox.showinfo("ByteMap", "Select one or more rows first.")
            return
        if table is self.t_dupes:
            for parent in table.tree.get_children(""):
                kids = [table.paths[k] for k in table.tree.get_children(parent) if k in table.paths]
                if kids and all(k in paths for k in kids):
                    messagebox.showwarning("ByteMap", "You selected every copy of a file. Keep at least one.")
                    return
        preview = "\n".join(paths[:10]) + (f"\n... and {len(paths) - 10} more" if len(paths) > 10 else "")
        if not messagebox.askyesno(
            "Move to Recycle Bin",
            f"Move {len(paths)} item(s) to the Recycle Bin?\n\n{preview}\n\n"
            "You can restore them from the Recycle Bin.",
            icon="warning", default="no",
        ):
            return
        done, refused = move_to_trash(paths, dry_run=False)
        for t in (self.t_dirs, self.t_big, self.t_old, self.t_dupes):
            t.remove_paths(set(done))
        msg = f"Moved {len(done)} item(s) to the Recycle Bin."
        if refused:
            msg += f" Refused {len(refused)} (missing, link or protected)."
            messagebox.showwarning("ByteMap", msg + "\n\n" + "\n".join(refused[:10]))
        self.status.set(msg + " Rescan to update totals.")

    def export_report(self) -> None:
        if not self.result:
            messagebox.showinfo("ByteMap", "Scan a folder first.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".html", initialfile="bytemap-report.html",
                                           filetypes=[("HTML", "*.html")])
        if not out:
            return
        from .report import render

        try:
            page = render(self.result, old_days=int(self.days.get()), min_size=self._min_size(),
                          dupes=False, redact_home=self.redact.get())
        except (ValueError, tk.TclError):
            return
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(page)
        self.status.set(f"Report saved: {out}  (contains file paths: keep it private)")

    def about(self) -> None:
        messagebox.showinfo(f"ByteMap {__version__}", DISCLAIMER)


def main(start: str | None = None) -> int:
    App(start).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
