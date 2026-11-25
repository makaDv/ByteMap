# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems.
Use GitHub's private vulnerability reporting instead:
**Security** tab of this repository, then **Report a vulnerability**.

Include the steps to reproduce and the affected version. You will get an answer as soon as possible.

## Design safeguards

- No network access: ByteMap never sends data anywhere.
- No permanent deletion: `bytemap trash` moves items to the Recycle Bin / Trash only.
- Dry run by default: `trash` needs `--apply`, then a typed `YES` (or `--yes`).
- Protected locations: filesystem roots and system folders (for example `C:\Windows`,
  `C:\Program Files`, `/etc`, `/usr`) are always refused.
- Symlinks and junctions are never followed or trashed.
- The HTML report escapes all file names and sets a Content-Security-Policy that blocks
  external requests.

## Supported versions

Only the latest release receives fixes.
