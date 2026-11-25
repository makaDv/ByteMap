# Contributing

Thanks for your interest in ByteMap.

## Rules

- **License of contributions**: by opening a pull request you agree that your contribution is
  licensed under the project's [MIT License](LICENSE), and you confirm you have the right to
  submit it (your own work, or compatible open source code with its notice kept).
- **No network code**: ByteMap must stay fully offline. Pull requests that add telemetry,
  analytics, update checks, remote fonts/CDNs or any network access will not be accepted.
- **No permanent deletion**: file removal must go through the Recycle Bin / Trash only.
- **No personal data**: do not include real file paths, screenshots of your files, reports,
  e-mail addresses or other personal data in code, tests, issues or pull requests.
  Tests must use synthetic files in `tmp_path`.
- **Dependencies**: avoid new ones. Any dependency needs a license compatible with MIT.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Security issues

Do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
