# Privacy

**Short version: ByteMap collects no data. Everything stays on your computer.**

- ByteMap runs only on your machine. It opens no network connections and has no telemetry,
  analytics, crash reporting or update checks.
- The author receives no data from ByteMap or its users. The author therefore does not process
  personal data of users in the sense of the EU General Data Protection Regulation (GDPR,
  Regulation (EU) 2016/679).
- ByteMap reads file names, sizes and dates. It reads file contents only to compare possible
  duplicates (SHA-256 hashes, computed in memory and never stored or sent).
- ByteMap stores no settings, history or logs. The only files it writes are the HTML reports you
  explicitly export, in the location you choose.
- The HTML report you create holds file and folder paths from your computer. These paths may
  include personal information, such as your user name or document titles. The report is a
  local file under your control: think before you share it. Use `--redact-home` to replace your
  home folder path with `~`.
- The report loads no external resources (no CDN, no web fonts, no trackers). Its
  Content-Security-Policy blocks all network requests.
- If you scan folders that hold other people's personal data (for example, in a company), you
  are responsible for doing so lawfully under the rules that apply to you.

Questions: open an issue on the GitHub repository. Do not post personal data in issues.
