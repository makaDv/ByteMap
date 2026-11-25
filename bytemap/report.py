"""Self-contained HTML report.

The page embeds all CSS, JS and data inline. It loads nothing from the network
(no CDN, no web fonts, no analytics), so opening it never contacts third parties.
"""

from __future__ import annotations

import html
import json
import os
import time
from collections import defaultdict

from . import __version__
from .analyzers import biggest_dirs, biggest_files, human, old_files
from .duplicates import find_duplicates, wasted_bytes
from .scanner import ScanResult


def make_redactor(enabled: bool):
    """Return a function that replaces the user's home folder with '~'."""
    home = os.path.expanduser("~")
    if not enabled or not home or home == "~":
        return lambda p: p
    norm_home = os.path.normcase(home)

    def redact(path: str) -> str:
        if os.path.normcase(path).startswith(norm_home):
            return "~" + path[len(home):]
        return path

    return redact


def build_tree(result: ScanResult, max_depth: int = 4, max_children: int = 40, redact=lambda p: p):
    """Nested {name, size, children} tree of directories for the treemap."""
    children: dict[str, list[str]] = defaultdict(list)
    for d in result.dir_sizes:
        parent = os.path.dirname(d)
        if d != result.root and parent in result.dir_sizes:
            children[parent].append(d)
    files_by_dir: dict[str, int] = defaultdict(int)
    for f in result.files:
        files_by_dir[os.path.dirname(f.path)] += f.size

    def node(path: str, depth: int) -> dict:
        name = redact(path) if path == result.root else os.path.basename(path)
        n = {"name": name, "size": result.dir_sizes.get(path, 0)}
        if depth >= max_depth:
            return n
        subs = sorted(children[path], key=lambda p: result.dir_sizes[p], reverse=True)
        kids = [node(s, depth + 1) for s in subs[:max_children] if result.dir_sizes[s] > 0]
        rest = sum(result.dir_sizes[s] for s in subs[max_children:])
        own = files_by_dir.get(path, 0)
        if own:
            kids.append({"name": "(files)", "size": own, "leaf": True})
        if rest:
            kids.append({"name": "(other folders)", "size": rest, "leaf": True})
        if kids:
            n["children"] = kids
        return n

    return node(result.root, 0)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "<p class='empty'>Nothing found.</p>"
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(
    result: ScanResult,
    top: int = 50,
    old_days: int = 365,
    min_size: int = 1024 * 1024,
    dupes: bool = True,
    redact_home: bool = False,
) -> str:
    redact = make_redactor(redact_home)
    date = lambda t: time.strftime("%Y-%m-%d", time.localtime(t))  # noqa: E731

    big = biggest_files(result, top=top)
    old = old_files(result, days=old_days, min_size=min_size)[:top]
    dirs = biggest_dirs(result, top=top)
    groups = find_duplicates(result.files, min_size=min_size) if dupes else []

    big_rows = [[human(f.size), date(f.mtime), redact(f.path)] for f in big]
    old_rows = [[human(f.size), date(f.mtime), redact(f.path)] for f in old]
    dir_rows = [[human(s), redact(d)] for d, s in dirs]
    dupe_rows = []
    for g in groups[:top]:
        wasted = human(g[0].size * (len(g) - 1))
        for i, f in enumerate(g):
            dupe_rows.append([wasted if i == 0 else "", human(f.size), redact(f.path)])

    tree = json.dumps(build_tree(result, redact=redact)).replace("<", "\\u003c")
    title = html.escape(redact(result.root))
    summary = (
        f"{human(result.total_size)} in {len(result.files):,} files"
        f" &middot; {len(result.errors)} unreadable"
        + (f" &middot; {human(wasted_bytes(groups))} in duplicates" if dupes else "")
    )

    return _TEMPLATE.format(
        title=title,
        summary=summary,
        generated=time.strftime("%Y-%m-%d %H:%M"),
        version=__version__,
        tree=tree,
        big=_table(["Size", "Modified", "Path"], big_rows),
        old=_table(["Size", "Modified", "Path"], old_rows),
        old_days=old_days,
        min_size=human(min_size),
        dirs=_table(["Size", "Folder"], dir_rows),
        dupes=_table(["Wasted", "Size", "Path"], dupe_rows) if dupes else "<p class='empty'>Skipped.</p>",
    )


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>ByteMap - {title}</title>
<style>
:root {{ --bg:#f7f7f5; --fg:#1d1d1b; --muted:#6b6b66; --line:#ddddd8; --card:#fff; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#161615; --fg:#ececea; --muted:#9a9a95; --line:#33332f; --card:#1f1f1d; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--bg); color:var(--fg); }}
main {{ max-width:1200px; margin:0 auto; padding:24px; }}
h1 {{ font-size:20px; margin:0 0 4px; word-break:break-all; }}
h2 {{ font-size:16px; margin:32px 0 8px; }}
.muted, .empty {{ color:var(--muted); }}
#crumbs {{ margin:16px 0 8px; font-size:13px; }}
#crumbs a {{ color:inherit; cursor:pointer; text-decoration:underline; }}
#map {{ position:relative; width:100%; height:480px; background:var(--card); border:1px solid var(--line); border-radius:6px; overflow:hidden; }}
.cell {{ position:absolute; border:1px solid var(--bg); overflow:hidden; padding:3px 5px; font-size:12px; color:#111; cursor:pointer; }}
.cell.leaf {{ cursor:default; opacity:.75; }}
.cell span {{ display:block; white-space:nowrap; text-overflow:ellipsis; overflow:hidden; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); border-radius:6px; }}
th, td {{ text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
td:last-child {{ word-break:break-all; font-family:ui-monospace,Consolas,monospace; font-size:12px; }}
th {{ font-weight:600; color:var(--muted); }}
td:first-child, th:first-child {{ white-space:nowrap; font-variant-numeric:tabular-nums; }}
footer {{ margin:40px 0 0; font-size:12px; color:var(--muted); }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<div class="muted">{summary}</div>

<div id="crumbs"></div>
<div id="map" role="img" aria-label="Treemap of folder sizes"></div>

<h2>Biggest folders</h2>
{dirs}
<h2>Biggest files</h2>
{big}
<h2>Old files (not modified for {old_days} days, at least {min_size})</h2>
{old}
<h2>Duplicate files (at least {min_size})</h2>
{dupes}

<footer>Generated locally by ByteMap {version} on {generated}. This file contains file paths from your computer: do not share it if they are private.</footer>
</main>
<script>
const ROOT = {tree};
const map = document.getElementById("map"), crumbs = document.getElementById("crumbs");
const fmt = b => {{ const u=["B","KB","MB","GB","TB"]; let i=0; while(b>=1024&&i<4){{b/=1024;i++;}} return (i?b.toFixed(1):b)+" "+u[i]; }};
const color = (i, n) => `hsl(${{(i*137.5)%360}} 55% ${{n?72:82}}%)`;

function squarify(items, x, y, w, h, out) {{
  if (!items.length) return;
  const total = items.reduce((s, it) => s + it.area, 0);
  if (items.length === 1 || total <= 0) {{ items.forEach(it => out.push({{...it, x, y, w, h}})); return; }}
  const short = Math.min(w, h);
  let row = [], best = Infinity, i = 0;
  const worst = r => {{ const s = r.reduce((a, b) => a + b.area, 0); const mx = Math.max(...r.map(e => e.area)), mn = Math.min(...r.map(e => e.area)); return Math.max(short*short*mx/(s*s), (s*s)/(short*short*mn)); }};
  while (i < items.length) {{ const r = row.concat(items[i]); const wr = worst(r); if (wr > best) break; row = r; best = wr; i++; }}
  const s = row.reduce((a, b) => a + b.area, 0), thick = s / short;
  let off = 0;
  row.forEach(it => {{ const len = it.area / thick;
    out.push(w >= h ? {{...it, x, y: y+off, w: thick, h: len}} : {{...it, x: x+off, y, w: len, h: thick}}); off += len; }});
  const rest = items.slice(i);
  if (w >= h) squarify(rest, x+thick, y, w-thick, h, out); else squarify(rest, x, y+thick, w, h-thick, out);
}}

let current = [ROOT];
function draw(path) {{
  current = path;
  const node = path[path.length-1];
  crumbs.innerHTML = "";
  path.forEach((p, i) => {{
    if (i) crumbs.append(" / ");
    const a = document.createElement(i < path.length-1 ? "a" : "strong");
    a.textContent = p.name + " (" + fmt(p.size) + ")";
    if (i < path.length-1) a.onclick = () => draw(path.slice(0, i+1));
    crumbs.append(a);
  }});
  map.innerHTML = "";
  const W = map.clientWidth, H = map.clientHeight, kids = (node.children||[]).filter(c => c.size > 0);
  const area = W * H, tot = kids.reduce((s, c) => s + c.size, 0) || 1;
  const out = []; squarify(kids.map((c, i) => ({{c, i, area: c.size/tot*area}})), 0, 0, W, H, out);
  out.forEach(r => {{
    const d = document.createElement("div");
    d.className = "cell" + (r.c.children ? "" : " leaf");
    Object.assign(d.style, {{left:r.x+"px", top:r.y+"px", width:r.w+"px", height:r.h+"px", background:color(r.i, r.c.children)}});
    d.title = r.c.name + " - " + fmt(r.c.size);
    if (r.w > 50 && r.h > 18) {{ const t = document.createElement("span"); t.textContent = r.c.name; d.append(t);
      if (r.h > 34) {{ const s = document.createElement("span"); s.textContent = fmt(r.c.size); d.append(s); }} }}
    if (r.c.children) d.onclick = () => draw(path.concat(r.c));
    map.append(d);
  }});
}}
draw(current);
window.addEventListener("resize", () => draw(current));
</script>
</body>
</html>
"""
