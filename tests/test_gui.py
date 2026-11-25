"""GUI smoke tests on synthetic files. Skipped when no display is available."""

import os

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from bytemap import gui

    try:
        a = gui.App(str(tmp_path))
    except tk.TclError:
        pytest.skip("no display")
    a.withdraw()
    # Never show real dialogs during tests.
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a, **k: True)
    for name in ("showinfo", "showwarning", "showerror"):
        monkeypatch.setattr(gui.messagebox, name, lambda *a, **k: None)
    yield a
    a.destroy()


@pytest.fixture
def files(tmp_path):
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "sub" / "deep" / "one.bin").write_bytes(b"z" * 4096)
    (tmp_path / "sub" / "two.bin").write_bytes(b"z" * 4096)
    (tmp_path / "unique.bin").write_bytes(b"u" * 9000)
    return tmp_path


def test_scan_fills_tables(app, files):
    from bytemap.scanner import scan

    app.min_size.set("0")
    app._t0 = 0
    app._scan_done(scan(str(files)))
    assert len(app.t_big.tree.get_children()) == 3
    assert [os.path.basename(p) for p in app.t_dirs.paths.values()] == ["sub"]
    app.t_dirs.tree.selection_set(app.t_dirs.tree.get_children()[0])
    app.drill_down()
    assert app.current_dir == str(files / "sub")
    app.go_up()
    assert app.current_dir == str(files)


def test_dupes_and_guard_against_trashing_all_copies(app, files):
    from bytemap.duplicates import find_duplicates
    from bytemap.scanner import scan

    app._t0 = 0
    app._scan_done(scan(str(files)))
    app._dupes_done(find_duplicates(app.result.files))
    tree = app.t_dupes.tree
    group = tree.get_children("")[0]
    kids = tree.get_children(group)
    assert len(kids) == 2

    app.tabs.select(3)
    tree.selection_set(kids)  # every copy selected: must refuse
    app.trash_selected()
    assert all(os.path.exists(app.t_dupes.paths[k]) for k in kids)


def test_trash_moves_selected_file(app, files, monkeypatch):
    from bytemap import gui
    from bytemap.scanner import scan

    moved = []
    monkeypatch.setattr(gui, "move_to_trash", lambda paths, dry_run: (moved.extend(paths) or (paths, [])))
    app.min_size.set("0")
    app._t0 = 0
    app._scan_done(scan(str(files)))
    app.tabs.select(1)
    first = app.t_big.tree.get_children()[0]
    app.t_big.tree.selection_set(first)
    app.trash_selected()
    assert moved == [str(files / "unique.bin")]
    assert not app.t_big.tree.exists(first)


def test_busy_toggle(app):
    app._set_busy(True, "working")
    assert app.busy and str(app.scan_btn["state"]) == "disabled"
    app._set_busy(False)
    assert not app.busy and str(app.scan_btn["state"]) == "normal"


def test_no_args_opens_gui(monkeypatch):
    from bytemap import cli, gui

    called = []
    monkeypatch.setattr(gui, "main", lambda path=None: called.append(path) or 0)
    assert cli.main([]) == 0
    assert called == [None]
