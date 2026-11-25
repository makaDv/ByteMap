# ByteMap

Find out what fills your disk. ByteMap lists the biggest folders and files, old files you
forgot, and duplicate files. It writes an interactive HTML treemap report.

**Fully offline.** No telemetry, no network access, no data leaves your computer.
See [PRIVACY.md](PRIVACY.md).

## Install

Needs Python 3.10 or newer.

```sh
git clone https://github.com/makaDv/ByteMap.git
cd ByteMap
pip install .
```

## Use

```sh
bytemap scan D:\                       # biggest folders
bytemap big ~/Downloads --top 30       # biggest files
bytemap old . --days 730 --min-size 50M  # not modified for 2 years
bytemap dupes ~/Pictures               # duplicate files (default: 1 MB or larger)
bytemap report C:\Users --redact-home  # HTML report: bytemap-report.html
```

Without installing: `python -m bytemap <command> ...`.

Common options: `--top N`, `--min-size 10M`, `--exclude DIR` (repeatable).

### Free up space

`bytemap trash` moves files to the Recycle Bin / Trash. It **never deletes permanently**.

```sh
bytemap trash old-video.mp4 setup.exe            # dry run: shows what would happen
bytemap trash old-video.mp4 setup.exe --apply    # asks you to type YES, then moves
bytemap trash --from-file list.txt --apply       # one path per line
```

ByteMap refuses filesystem roots, system folders (`C:\Windows`, `C:\Program Files`, `/usr`,
`/etc` and similar), symlinks and junctions.

## How it works

- Walks folders with `os.scandir`. It does not follow symlinks or junctions, so it never loops
  or counts a file twice.
- Duplicates: groups by size, then compares a SHA-256 of the first 64 KB, then a full SHA-256.
- The report is one HTML file with inline CSS/JS. It loads nothing from the internet.

## Privacy note about reports

A report contains file paths from your computer, which can include your name or document
titles. Keep it private, or create it with `--redact-home`. Report files are in `.gitignore`.

## Disclaimer

Use at your own risk. ByteMap is provided "as is", without warranty of any kind (see
[LICENSE](LICENSE)). Check what you move to the Recycle Bin and keep backups of important data.

## Third-party software

- [Send2Trash](https://github.com/arsenetar/send2trash), BSD-3-Clause license: moves files to
  the Recycle Bin / Trash.

## License

[MIT](LICENSE)
