"""Graphical interface (Tkinter, included with Python: no extra install).

Start with:  python -m bytemap   or   python -m bytemap gui   or double-click ByteMap.pyw
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
from .treemap import squarify

SIZES = ["0", "100K", "1M", "10M", "100M", "1G"]
DISCLAIMER = (
    "ByteMap is free open source software, provided \"as is\", without warranty "
    "of any kind (MIT license).\n\n"
    "It only moves files to the Recycle Bin, never deletes them permanently, "
    "and refuses system folders. Still, check what you select and keep backups "
    "of important data.\n\n"
    "ByteMap works fully offline: no data leaves your computer and nothing is collected."
)

# Palette
BG = "#F4F5F9"
CARD = "#FFFFFF"
INK = "#1F2333"
MUTED = "#6B7185"
LINE = "#E3E5EC"
HEADER = "#1E1B4B"
HEADER_INK = "#E9E8FF"
ACCENT = "#5B5BD6"
ACCENT_DARK = "#4646B8"
DANGER = "#D64545"
DANGER_DARK = "#B83535"
STRIPE = "#F8F8FC"
SELECT = "#E4E4FB"
TILES = ["#6C6CE0", "#2FA4A9", "#E58A3A", "#D65C8A", "#4E9F5B", "#8C6AD1",
         "#C9A227", "#3D8BD9", "#C2573D", "#5F7A8C"]
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"


def _date(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _bar(pct: float, width: int = 14) -> str:
    full = max(int(round(pct / 100 * width)), 1 if pct > 0 else 0)
    return "█" * full


def open_location(path: str) -> None:
    """Show ``path`` in the system file manager (no shell involved)."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path) or path])


def _make_icon(size: int = 32) -> tk.PhotoImage:
    """Small treemap-style icon drawn in code (no image files)."""
    img = tk.PhotoImage(width=size, height=size)
    img.put(HEADER, to=(0, 0, size, size))
    s = size
    img.put(TILES[0], to=(2, 2, s // 2 + 3, s - 2))
    img.put(TILES[1], to=(s // 2 + 5, 2, s - 2, s // 2))
    img.put(TILES[2], to=(s // 2 + 5, s // 2 + 2, s - 9, s - 2))
    img.put(TILES[3], to=(s - 7, s // 2 + 2, s - 2, s - 2))
    return img


def _setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BG)
    base = (FONT, 10)
    style.configure(".", font=base, background=BG, foreground=INK, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, troughcolor=LINE, focuscolor=ACCENT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, relief="flat")
    style.configure("Header.TFrame", background=HEADER)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Header.TLabel", background=HEADER, foreground=HEADER_INK)
    style.configure("Title.TLabel", background=HEADER, foreground="#FFFFFF", font=(FONT, 17, "bold"))
    style.configure("Sub.TLabel", background=HEADER, foreground="#A9A6E8", font=(FONT, 9))
    style.configure("CardTitle.TLabel", background=CARD, foreground=MUTED, font=(FONT, 9))
    style.configure("CardValue.TLabel", background=CARD, foreground=INK, font=(FONT, 16, "bold"))
    style.configure("CardNote.TLabel", background=CARD, foreground=MUTED, font=(FONT, 8))
    style.configure("Crumb.TLabel", background=BG, foreground=INK, font=(FONT, 10, "bold"))

    style.configure("TButton", padding=(12, 6), background=CARD, relief="flat", borderwidth=1)
    style.map("TButton", background=[("active", "#ECECF6"), ("disabled", BG)],
              foreground=[("disabled", "#A0A4B4")])
    for name, color, dark in (("Accent", ACCENT, ACCENT_DARK), ("Danger", DANGER, DANGER_DARK)):
        style.configure(f"{name}.TButton", background=color, foreground="#FFFFFF",
                        bordercolor=color, font=(FONT, 10, "bold"))
        style.map(f"{name}.TButton", background=[("disabled", "#B9B9D6"), ("active", dark)],
                  bordercolor=[("active", dark)])
    style.configure("Header.TButton", background="#2E2A6B", foreground=HEADER_INK, bordercolor="#2E2A6B")
    style.map("Header.TButton", background=[("active", "#3A357F")])

    style.configure("TEntry", fieldbackground=CARD, padding=6, bordercolor=LINE)
    style.configure("Header.TEntry", fieldbackground="#FFFFFF", padding=7)
    style.configure("TCombobox", fieldbackground=CARD, padding=4)
    style.configure("TSpinbox", fieldbackground=CARD, padding=4, arrowsize=12)
    style.configure("TCheckbutton", background=BG)
    style.configure("TCheckbutton", indicatorbackground=CARD, indicatorforeground="#FFFFFF")
    style.map("TCheckbutton", background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("active", "#ECECF6")])

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", padding=(16, 7), background=BG, foreground=MUTED,
                    borderwidth=0, font=(FONT, 10))
    style.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", ACCENT)],
              font=[("selected", (FONT, 10, "bold"))])

    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                    rowheight=26, borderwidth=0, font=base)
    style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", INK)])
    style.configure("Treeview.Heading", background="#EEEFF5", foreground=MUTED, relief="flat",
                    font=(FONT, 9, "bold"), padding=(6, 5))
    style.map("Treeview.Heading", background=[("active", "#E4E5EE")])
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=LINE, borderwidth=0,
                    thickness=6)


class Table(ttk.Frame):
    """Treeview with scrollbars, sortable columns, striped rows and a path per row."""

    def __init__(self, master, columns: list[tuple[str, int, str]]):
        super().__init__(master, style="Card.TFrame")
        self.columns = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.columns, show="tree headings", selectmode="extended")
        self.tree.column("#0", width=18, stretch=False)
        for name, width, anchor in columns:
            self.tree.heading(name, text=name, anchor=anchor, command=lambda n=name: self.sort(n))
            self.tree.column(name, width=width, anchor=anchor, stretch=(name == "Path"))
        self.tree.tag_configure("odd", background=STRIPE)
        self.tree.tag_configure("group", background="#EEEEFB", font=(FONT, 10, "bold"))
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
            parent: str = "", open_: bool = False, group: bool = False) -> str:
        n = len(self.tree.get_children(parent))
        tags = ("group",) if group else (("odd",) if n % 2 else ())
        iid = self.tree.insert(parent, "end", values=values, open=open_, tags=tags)
        if path:
            self.paths[iid] = path
        self.keys[iid] = keys or {}
        return iid

    def restripe(self) -> None:
        for parent in [""] + list(self.tree.get_children("")):
            for i, iid in enumerate(self.tree.get_children(parent)):
                if "group" not in self.tree.item(iid, "tags"):
                    self.tree.item(iid, tags=("odd",) if i % 2 else ())

    def sort(self, col: str) -> None:
        desc = self._desc[col] = not self._desc.get(col, col in ("Size", "Wasted", "Share"))
        idx = self.columns.index(col)

        def key(iid):
            k = self.keys.get(iid, {})
            return k.get(col, str(self.tree.set(iid, self.columns[idx])).lower())

        for parent in {""} | set(self.tree.get_children("")):
            items = sorted(self.tree.get_children(parent), key=key, reverse=desc)
            for i, iid in enumerate(items):
                self.tree.move(iid, parent, i)
        for c in self.columns:
            arrow = (" ▼" if desc else " ▲") if c == col else ""
            self.tree.heading(c, text=c + arrow)
        self.restripe()

    def selected_paths(self) -> list[str]:
        return [self.paths[i] for i in self.tree.selection() if i in self.paths]

    def remove_paths(self, paths: set[str]) -> None:
        for iid, p in list(self.paths.items()):
            if p in paths and self.tree.exists(iid):
                self.tree.delete(iid)
                del self.paths[iid]
        self.restripe()


class StatCard(ttk.Frame):
    def __init__(self, master, title: str, color: str):
        super().__init__(master, style="Card.TFrame", padding=(14, 10))
        tk.Frame(self, background=color, width=4).pack(side="left", fill="y", padx=(0, 12))
        box = ttk.Frame(self, style="Card.TFrame")
        box.pack(side="left", fill="both", expand=True)
        ttk.Label(box, text=title.upper(), style="CardTitle.TLabel").pack(anchor="w")
        self.value = ttk.Label(box, text="—", style="CardValue.TLabel")
        self.value.pack(anchor="w")
        self.note = ttk.Label(box, text="", style="CardNote.TLabel")
        self.note.pack(anchor="w")

    def set(self, value: str, note: str = "") -> None:
        self.value.configure(text=value)
        self.note.configure(text=note)


class App(tk.Tk):
    def __init__(self, start: str | None = None):
        super().__init__()
        self.title(f"ByteMap {__version__}")
        self.geometry("1180x780")
        self.minsize(860, 560)
        _setup_style(self)
        try:
            self._icon = _make_icon()
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        self.result: ScanResult | None = None
        self.children_map: dict[str, list[str]] = {}
        self.own_files: dict[str, int] = {}
        self.current_dir: str | None = None
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self._tiles: dict[int, str] = {}

        self.folder = tk.StringVar(value=start or os.path.expanduser("~"))
        self.min_size = tk.StringVar(value="1M")
        self.days = tk.IntVar(value=365)
        self.redact = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Choose a folder and press Scan.")

        self._build()
        self.after(100, self._poll)

    # ---------- layout ----------
    def _build(self) -> None:
        header = ttk.Frame(self, style="Header.TFrame", padding=(18, 12))
        header.pack(fill="x")
        brand = ttk.Frame(header, style="Header.TFrame")
        brand.pack(side="left", padx=(0, 24))
        ttk.Label(brand, text="ByteMap", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="See what fills your disk · 100% offline", style="Sub.TLabel").pack(anchor="w")
        self.scan_btn = ttk.Button(header, text="Scan", style="Accent.TButton", command=self.start_scan)
        self.scan_btn.pack(side="right", padx=(6, 0))
        ttk.Button(header, text="Browse…", style="Header.TButton", command=self.browse).pack(side="right", padx=6)
        entry = ttk.Entry(header, textvariable=self.folder, style="Header.TEntry", font=(FONT, 10))
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.start_scan())

        cards = ttk.Frame(self, padding=(14, 12, 14, 0))
        cards.pack(fill="x")
        self.c_total = StatCard(cards, "Total size", TILES[0])
        self.c_files = StatCard(cards, "Files", TILES[1])
        self.c_old = StatCard(cards, "Old files", TILES[2])
        self.c_dupes = StatCard(cards, "Duplicates", TILES[3])
        for i, c in enumerate((self.c_total, self.c_files, self.c_old, self.c_dupes)):
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            cards.columnconfigure(i, weight=1)
        self.c_dupes.set("—", "open the Duplicates tab")

        opts = ttk.Frame(self, padding=(14, 10, 14, 0))
        opts.pack(fill="x")
        ttk.Label(opts, text="Min file size", style="Muted.TLabel").pack(side="left")
        ttk.Combobox(opts, textvariable=self.min_size, values=SIZES, width=6).pack(side="left", padx=(6, 18))
        ttk.Label(opts, text="Old after", style="Muted.TLabel").pack(side="left")
        ttk.Spinbox(opts, from_=30, to=7300, increment=30, textvariable=self.days, width=6).pack(side="left", padx=6)
        ttk.Label(opts, text="days", style="Muted.TLabel").pack(side="left", padx=(0, 12))
        ttk.Button(opts, text="Apply filters", command=self.refresh).pack(side="left")
        ttk.Button(opts, text="About & disclaimer", command=self.about).pack(side="right")

        self.tabs = ttk.Notebook(self)

        # Folders tab: treemap + table
        f = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        nav = ttk.Frame(f, style="Card.TFrame")
        nav.pack(fill="x", pady=(0, 8))
        ttk.Button(nav, text="← Up", command=self.go_up).pack(side="left")
        self.crumb = ttk.Label(nav, text="", style="Crumb.TLabel", background=CARD)
        self.crumb.pack(side="left", padx=10)
        split = ttk.PanedWindow(f, orient="vertical")
        split.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(split, height=220, background=CARD, highlightthickness=0, cursor="hand2")
        self.canvas.bind("<Configure>", lambda e: self.draw_treemap())
        self.canvas.bind("<Motion>", self._tile_hover)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("hover"))
        self.canvas.bind("<Button-1>", self._tile_click)
        split.add(self.canvas, weight=2)
        self.t_dirs = Table(split, [("Size", 90, "e"), ("Share", 170, "w"), ("Subfolders", 90, "e"), ("Path", 560, "w")])
        split.add(self.t_dirs, weight=3)
        self.t_dirs.tree.bind("<Double-1>", self.drill_down)
        self.tabs.add(f, text="  Folders  ")

        self.t_big = Table(self.tabs, [("Size", 90, "e"), ("Modified", 100, "center"), ("Path", 760, "w")])
        self.tabs.add(self.t_big, text="  Big files  ")
        self.t_old = Table(self.tabs, [("Size", 90, "e"), ("Modified", 100, "center"), ("Path", 760, "w")])
        self.tabs.add(self.t_old, text="  Old files  ")

        d = ttk.Frame(self.tabs, style="Card.TFrame", padding=10)
        bar = ttk.Frame(d, style="Card.TFrame")
        bar.pack(fill="x", pady=(0, 8))
        self.dupe_btn = ttk.Button(bar, text="Find duplicates", style="Accent.TButton", command=self.start_dupes)
        self.dupe_btn.pack(side="left")
        ttk.Label(bar, text="Compares file contents (SHA-256). Keep at least one copy of each file.",
                  style="CardNote.TLabel").pack(side="left", padx=10)
        self.t_dupes = Table(d, [("Wasted", 100, "e"), ("Size", 110, "e"), ("Path", 740, "w")])
        self.t_dupes.pack(fill="both", expand=True)
        self.tabs.add(d, text="  Duplicates  ")

        for t in (self.t_dirs, self.t_big, self.t_old, self.t_dupes):
            t.tree.bind("<Delete>", lambda e: self.trash_selected())

        bottom = tk.Frame(self, background=CARD, highlightthickness=1, highlightbackground=LINE)
        bottom.pack(side="bottom", fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=160, value=0)
        self.progress.pack(side="right", padx=12, pady=8)
        tk.Label(bottom, textvariable=self.status, background=CARD, foreground=MUTED,
                 font=(FONT, 9)).pack(side="left", padx=14, pady=6)

        actions = ttk.Frame(self, padding=(14, 0, 14, 8))
        actions.pack(side="bottom", fill="x")
        ttk.Button(actions, text="Show in folder", command=self.show_selected).pack(side="left")
        ttk.Button(actions, text="Copy path", command=self.copy_selected).pack(side="left", padx=6)
        ttk.Button(actions, text="Move to Recycle Bin", style="Danger.TButton",
                   command=self.trash_selected).pack(side="left")
        ttk.Button(actions, text="Export HTML report…", command=self.export_report).pack(side="right")
        ttk.Checkbutton(actions, text="Hide my home folder in report", variable=self.redact).pack(side="right", padx=10)

        self.tabs.pack(fill="both", expand=True, padx=14, pady=10)

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
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
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

    # ---------- treemap ----------
    def _tile_items(self) -> list[tuple[str, int, str | None]]:
        """(label, size, folder path or None) for the current folder."""
        if not self.result or not self.current_dir:
            return []
        subs = sorted(self.children_map.get(self.current_dir, []),
                      key=lambda p: self.result.dir_sizes[p], reverse=True)
        items = [(os.path.basename(s), self.result.dir_sizes[s], s) for s in subs if self.result.dir_sizes[s] > 0]
        own = self.own_files.get(self.current_dir, 0)
        if own:
            items.append(("(files here)", own, None))
        return sorted(items, key=lambda t: t[1], reverse=True)

    def draw_treemap(self) -> None:
        c = self.canvas
        c.delete("all")
        self._tiles.clear()
        w, h = c.winfo_width(), c.winfo_height()
        items = self._tile_items()
        if not items:
            msg = "Choose a folder and press Scan" if not self.result else "This folder is empty"
            c.create_text(w / 2, h / 2, text=msg, fill=MUTED, font=(FONT, 12))
            return
        total = sum(s for _, s, _ in items)
        for i, ((label, size, path), (x, y, rw, rh)) in enumerate(
                zip(items, squarify([s for _, s, _ in items], 0, 0, w, h))):
            if rw < 1 or rh < 1:
                continue
            color = TILES[i % len(TILES)] if path else "#9AA0B4"
            rid = c.create_rectangle(x + 1, y + 1, x + rw - 1, y + rh - 1, fill=color, outline=CARD, width=2)
            self._tiles[rid] = path or ""
            c.itemconfigure(rid, tags=("tile", f"t{rid}"))
            if rw > 60 and rh > 22:
                chars = max(int(rw / 7.5), 3)
                name = label if len(label) <= chars else label[: chars - 1] + "…"
                c.create_text(x + 8, y + 6, anchor="nw", text=name, fill="#FFFFFF",
                              font=(FONT, 10, "bold"), tags=(f"t{rid}",))
                if rh > 42:
                    c.create_text(x + 8, y + 24, anchor="nw", fill="#F1F1FF", font=(FONT, 9),
                                  text=f"{human(size)} · {size * 100 / total:.0f}%", tags=(f"t{rid}",))

    def _tile_at(self, event) -> int | None:
        for item in reversed(self.canvas.find_overlapping(event.x, event.y, event.x, event.y)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("t") and tag[1:].isdigit() and int(tag[1:]) in self._tiles:
                    return int(tag[1:])
        return None

    def _tile_hover(self, event) -> None:
        self.canvas.delete("hover")
        rid = self._tile_at(event)
        if rid is None:
            return
        x1, y1, x2, y2 = self.canvas.coords(rid)
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#FFFFFF", width=3, tags=("hover",))
        path = self._tiles[rid]
        if path and self.result:
            self.status.set(f"{path}  —  {human(self.result.dir_sizes[path])}  (click to open)")

    def _tile_click(self, event) -> None:
        rid = self._tile_at(event)
        if rid is not None and self._tiles[rid]:
            self.show_dir(self._tiles[rid])

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
        self._set_busy(True, f"Scanning {path} …")
        self.t_dupes.clear()
        self.c_dupes.set("—", "open the Duplicates tab")
        self._t0 = time.perf_counter()
        self._run("scan", scan, path)

    def _scan_done(self, result: ScanResult) -> None:
        self.result = result
        self.children_map = defaultdict(list)
        for d in result.dir_sizes:
            parent = os.path.dirname(d)
            if d != result.root and parent in result.dir_sizes:
                self.children_map[parent].append(d)
        self.own_files = defaultdict(int)
        for f in result.files:
            self.own_files[os.path.dirname(f.path)] += f.size
        self.current_dir = result.root
        self.refresh()
        elapsed = time.perf_counter() - self._t0
        self.c_total.set(human(result.total_size), f"scanned in {elapsed:.1f}s")
        self.c_files.set(f"{len(result.files):,}", f"{len(result.errors)} unreadable")
        self.status.set(f"Done. {human(result.total_size)} in {len(result.files):,} files.")

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
        old_total = sum(f.size for f in old)
        self.c_old.set(human(old_total), f"{len(old):,} files over {days} days")

    def show_dir(self, path: str) -> None:
        assert self.result
        self.current_dir = path
        total = self.result.dir_sizes.get(path, 0) or 1
        self.crumb.configure(text=f"{path}   ·   {human(self.result.dir_sizes.get(path, 0))}")
        self.t_dirs.clear()
        subs = sorted(self.children_map.get(path, []), key=lambda p: self.result.dir_sizes[p], reverse=True)
        for s in subs:
            size = self.result.dir_sizes[s]
            pct = size * 100 / total
            n = len(self.children_map.get(s, []))
            self.t_dirs.add([human(size), f"{_bar(pct)}  {pct:4.1f}%", str(n), s], s,
                            {"Size": size, "Share": size, "Subfolders": n})
        self.draw_treemap()

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
        self._set_busy(True, "Comparing files …")
        self._run("dupes", find_duplicates, list(self.result.files), min_size)

    def _dupes_done(self, groups) -> None:
        self.t_dupes.clear()
        for g in groups:
            wasted = g[0].size * (len(g) - 1)
            parent = self.t_dupes.add([human(wasted), f"{len(g)} × {human(g[0].size)}", os.path.basename(g[0].path)],
                                      keys={"Wasted": wasted, "Size": g[0].size}, open_=True, group=True)
            for f in g:
                self.t_dupes.add(["", human(f.size), f.path], f.path, {"Size": f.size}, parent=parent)
        total = wasted_bytes(groups)
        self.c_dupes.set(human(total), f"{len(groups):,} groups of identical files")
        self.status.set(f"{len(groups):,} duplicate groups, {human(total)} wasted. "
                        "Select the copies to remove (keep at least one).")

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
        preview = "\n".join(paths[:10]) + (f"\n… and {len(paths) - 10} more" if len(paths) > 10 else "")
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
