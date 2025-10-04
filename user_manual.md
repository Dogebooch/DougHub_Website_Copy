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
- `raw` (recommended for saving everything) — downloads the entire HTML of each URL, records the HTTP status code, timestamp, and (optionally) a plain-text dump.
- `parsed` — extracts specific fields using CSS selectors (`question_selector`, `answer_selector`, `explanation_selector`).

Switch between modes by updating `capture_mode`. When set to `raw`, selectors are ignored and you only need working URLs and session details. Parsed mode benefits from the new table/image extraction described below.

## How to Use Session Cookies (Recommended for Login)
Follow these steps to reuse your existing browser session so the scraper can access protected pages without automating the login form:
1. **Log in normally**: Open the target website in your preferred browser, sign in, and navigate to a page you want to scrape.
2. **Open Developer Tools**: Press `F12` (or right-click and choose "Inspect").
3. **Locate the storage panel**:
   - Chrome/Edge: go to the **Application** tab.
   - Firefox: go to the **Storage** tab.
4. **Find cookies for the site**: In the left sidebar, expand **Cookies** and select the site domain (e.g., `https://example.com`).
5. **Identify the session cookie**: Look for entries named something like `sessionid`, `auth_token`, `csrftoken`, or similar high-value entries. Confirm the value is populated (not blank or expired).
6. **Copy name and value**: Double-click the cookie's **Name** and **Value** fields to copy them exactly.
7. **Paste into `config.json`**: Open `config.json` and add each cookie under the `session_cookies` object. For example:
   ```json
   "session_cookies": {
     "sessionid": "abc123def456",
     "csrftoken": "XYZ789"
   }
   ```
8. **(Optional) Capture headers**: While Developer Tools is open, switch to the **Network** tab, reload the page, select a request, and copy the browser's `User-Agent` and `Referer` headers. Paste them into the `request_headers` section to mimic the browser even more closely.
9. **Leave `login_required` as `false`**: With valid cookies in place, the scraper will skip its own form-based login and reuse your browser session automatically.

If the site logs you out later, repeat these steps to refresh the cookie values.

## Editing `config.json`
Key fields to customise before running:
- `start_urls`: List of fully-qualified pages to capture. Paste the URLs you want to save.
- `capture_mode`: Use `raw` to save whole pages or `parsed` for selector-based extraction.
- `table_selectors` / `image_selectors`: Lists of CSS selectors for table and image extraction (used in parsed mode and appended to raw captures for convenience).
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
2. Click **Start Scraping**. The GUI reads all settings from `config.json`, launches the scraper in the background, and streams log messages in the text area.
3. Monitor progress in the log panel. Status updates include applied headers/cookies, per-page fetch results, and output summaries.
4. After completion, locate the output file (CSV/JSON/SQLite) in the same directory as the scripts.

## Output Details
- **JSON** (recommended for raw captures): Each record includes `url`, `status_code`, `retrieved_at`, `raw_html`, optional `raw_text`, plus any captured `tables` and `images`.
- **CSV**: Contains the same fields; lists such as `answers`, `tables`, and `images` are stored as JSON strings.
- **SQLite**: A `scraped_data` table is created with columns that match the captured fields (including `tables` and `images`). View with any SQLite browser.

## Handling Errors
- Network or parsing issues are reported in the log pane. Check your cookies, headers, selectors, or rate limiting if a request fails.
- Configuration problems (missing file, invalid JSON, unsupported format) appear immediately when the GUI starts or when you click **Start Scraping**.
- If a page saves successfully but looks incorrect, verify you copied the latest cookies or adjust selectors for parsed mode.

## Advanced Tips
- Increase `rate_limit_delay` if the site throttles repeated requests.
- Toggle `capture_mode` to `parsed` once you know the exact selectors you need for question/answer extraction alongside tables and images.
- Extend `scraper.py` with custom processors (e.g., saving screenshots, normalising text) while keeping the GUI untouched.

## Support
If you encounter issues:
1. Confirm all dependencies are installed.
2. Validate URLs in a browser to ensure your session is still active.
3. Use the log output to pinpoint failing URLs, missing cookies, or absent elements.

Happy scraping!
