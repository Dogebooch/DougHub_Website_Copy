# Configurable Web Scraper — User Manual

## Overview
This desktop application lets you save full webpages (or structured question/answer data) straight from a PyQt5 interface. The scraper runs through a simple GUI, reuses your existing logged-in browser session if you provide cookies, and stores the output in CSV, JSON, or SQLite based on `config.json`.

## Prerequisites
- Python 3.9 or later (3.11 recommended)
- Required Python packages:
  ```bash
  pip install PyQt5 requests beautifulsoup4
  ```
  Install `sqlite3` from the Python standard library if your distribution omits it.

## Files
- `config.json` — central configuration for URLs, capture mode, login/cookie details, selectors, and output preferences.
- `scraper.py` — backend scraping engine.
- `gui.py` — PyQt5 graphical interface and controller logic.
- `user_manual.md` — this guide.

## First-Time Setup
1. Verify Python and pip are installed: `python --version` and `pip --version`.
2. Install dependencies using the command above (ideally inside a virtual environment).
3. Review `config.json` and update placeholders to match your target site.

## Capture Modes
The scraper supports two modes via `capture_mode` in `config.json`:
- `raw` (recommended for your workflow) — downloads the entire HTML of each URL, records the HTTP status code, timestamp, and (optionally) a plain-text dump.
- `parsed` — extracts specific fields using CSS selectors (`question_selector`, `answer_selector`, `explanation_selector`).

Switch between modes by updating `capture_mode`. When set to `raw`, selectors are ignored and you only need working URLs and session details.

## Reusing a Logged-In Browser Session
Because you already have the question pages open in your browser:
1. In your browser's developer tools, open the **Application/Storage** tab.
2. Locate cookies for the target domain and copy the relevant name/value pairs (for example, `sessionid`).
3. Paste them into `session_cookies` in `config.json`.
4. Optionally copy the current `User-Agent` and `Referer` from the **Network** tab and paste them into `request_headers`.
5. Leave `login_required` as `false` so the scraper relies entirely on the supplied cookies/headers.

## Editing `config.json`
Key fields to customise before running:
- `start_urls`: List of fully-qualified pages to capture. Paste the URL that you currently have open in the browser.
- `capture_mode`: Use `raw` to save whole pages or `parsed` for selector-based extraction.
- `output_format`: One of `csv`, `json`, or `sqlite`.
- `output_filename`: Destination file name (e.g., `scraped_pages.json`).
- `raw_include_text`: When `true`, stores an additional plain-text version of the page alongside the HTML.
- `rate_limit_delay`: Seconds to wait between requests to respect the target site.
- `question_selector`, `answer_selector`, `explanation_selector`: Only required when `capture_mode` is `parsed`.

> Tip: Duplicate the entire `config.json` for different sites/configurations and swap the file as needed.

## Running the Application
1. Launch the GUI:
   ```bash
   python gui.py
   ```
2. Confirm the URLs displayed in the "Start URLs" field match the pages you want to save. Edit them if necessary (comma-separated) and click **Start Scraping**.
3. Monitor progress in the log panel. Status updates include applied headers/cookies, per-page fetch results, and output summaries.
4. After completion, locate the output file (CSV/JSON/SQLite) in the same directory as the scripts.

## Output Details
- **JSON** (recommended for raw captures): Each record includes `url`, `status_code`, `retrieved_at`, `raw_html`, and optionally `raw_text`.
- **CSV**: Contains the same fields; lists/dictionaries are serialised as JSON strings.
- **SQLite**: A `scraped_data` table is created with columns that match the captured fields. View with any SQLite browser.

## Handling Errors
- Network or parsing issues are reported in the log pane. Check your cookies, headers, or selector configuration.
- Configuration problems (missing file, invalid JSON, unsupported format) appear immediately when the GUI starts or when you click **Start Scraping**.
- If a page saves successfully but looks incorrect, verify you copied the latest cookies or switch to `raw_include_text` for debugging.

## Advanced Tips
- Increase `rate_limit_delay` if the site throttles repeated requests.
- Toggle `capture_mode` to `parsed` once you know the exact selectors you need for question/answer extraction.
- Extend `scraper.py` with custom processors (e.g., saving screenshots, normalising text) while keeping the GUI untouched.

## Support
If you encounter issues:
1. Confirm all dependencies are installed.
2. Validate URLs in a browser to ensure your session is still active.
3. Use the log output to pinpoint failing URLs or missing selectors.

Happy scraping!
