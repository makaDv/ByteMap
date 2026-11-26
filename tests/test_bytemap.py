"""Tests use only synthetic files created in pytest's tmp_path."""

import os
import time

import pytest

from bytemap.analyzers import biggest_dirs, biggest_files, old_files, parse_size
from bytemap.cli import main
from bytemap.duplicates import find_duplicates, wasted_bytes
from bytemap.report import make_redactor, render
from bytemap.scanner import scan
from bytemap.trash import is_protected, move_to_trash


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "big.bin").write_bytes(b"x" * 5000)
    (tmp_path / "a" / "small.txt").write_bytes(b"hello")
    (tmp_path / "b" / "deep").mkdir(parents=True)
    (tmp_path / "b" / "deep" / "copy1.dat").write_bytes(b"same" * 300)
    (tmp_path / "b" / "copy2.dat").write_bytes(b"same" * 300)
    (tmp_path / "b" / "near.dat").write_bytes(b"same" * 299 + b"diff")
    old = tmp_path / "old.log"
    old.write_bytes(b"o" * 2000)
    past = time.time() - 400 * 86400
    os.utime(old, (past, past))
    return tmp_path


def test_scan_sizes(tree):
    r = scan(str(tree))
    assert len(r.files) == 6
    assert r.total_size == 5000 + 5 + 1200 * 3 + 2000
    assert r.dir_sizes[str(tree / "b")] == 3600


def test_biggest(tree):
    r = scan(str(tree))
    assert os.path.basename(biggest_files(r, top=1)[0].path) == "big.bin"
    dirs = biggest_dirs(r, top=2)
    assert [os.path.basename(d) for d, _ in dirs] == ["a", "b"]


def test_old(tree):
    r = scan(str(tree))
    assert [os.path.basename(f.path) for f in old_files(r, days=365)] == ["old.log"]


def test_duplicates(tree):
    groups = find_duplicates(scan(str(tree)).files)
    assert len(groups) == 1
    assert sorted(os.path.basename(f.path) for f in groups[0]) == ["copy1.dat", "copy2.dat"]
    assert wasted_bytes(groups) == 1200


def test_exclude(tree):
    r = scan(str(tree), exclude=(str(tree / "b"),))
    assert all("copy" not in f.path for f in r.files)


def test_parse_size():
    assert parse_size("10K") == 10240
    assert parse_size("1.5M") == int(1.5 * 1024**2)
    assert parse_size("200") == 200


def test_report_is_offline(tree):
    page = render(scan(str(tree)), min_size=1)
    assert "copy2.dat" in page
    for marker in ("http://", "https://", "src=", "@import", "url("):
        assert marker not in page


def test_report_escapes_html(tmp_path):
    (tmp_path / "<script>x.txt").write_bytes(b"1") if os.name != "nt" else None
    page = render(scan(str(tmp_path)), min_size=1)
    assert "<script>x" not in page


def test_redact_home():
    home = os.path.expanduser("~")
    redact = make_redactor(True)
    assert redact(os.path.join(home, "Documents", "f.txt")).startswith("~")
    assert make_redactor(False)(home) == home


def test_trash_dry_run(tree):
    target = tree / "a" / "small.txt"
    done, refused = move_to_trash([str(target)], dry_run=True)
    assert done == [str(target)] and not refused
    assert target.exists()


def test_trash_refuses_missing_and_protected(tree):
    root = os.path.abspath(os.sep)
    done, refused = move_to_trash([str(tree / "nope"), root], dry_run=True)
    assert not done and len(refused) == 2
    assert is_protected(root)
    if os.name == "nt":
        assert is_protected(r"C:\Windows\System32\drivers")
    else:
        assert is_protected("/etc/passwd")
    assert not is_protected(str(tree / "a"))


def test_cli_report(tree, tmp_path_factory):
    out = tmp_path_factory.mktemp("out") / "r.html"
    assert main(["report", str(tree), "-o", str(out), "--min-size", "1"]) == 0
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_cli_trash_dry_run_keeps_file(tree):
    target = tree / "a" / "big.bin"
    assert main(["trash", str(target)]) == 0
    assert target.exists()


def test_squarify_fills_area_without_overlap():
    from bytemap.treemap import squarify

    sizes = [500, 300, 120, 50, 20, 9, 1]
    rects = squarify(sizes, 0, 0, 400, 300)
    area = sum(w * h for _, _, w, h in rects)
    assert abs(area - 400 * 300) < 1e-6
    for (x, y, w, h), s in zip(rects, sizes):
        assert x >= -1e-9 and y >= -1e-9 and x + w <= 400 + 1e-6 and y + h <= 300 + 1e-6
        assert abs(w * h - s / sum(sizes) * 400 * 300) < 1e-6
    assert squarify([], 0, 0, 10, 10) == []
    assert squarify([0, 0], 0, 0, 10, 10) == [(0, 0, 0.0, 0.0)] * 2


def test_trash_refuses_home_and_profiles_folder():
    home = os.path.expanduser("~")
    assert is_protected(home)
    assert is_protected(os.path.dirname(home))
    assert not is_protected(os.path.join(home, "Downloads", "file.zip"))
