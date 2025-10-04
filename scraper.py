"""Scraper module for the configurable web scraping application."""
from __future__ import annotations

import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

StatusCallback = Optional[Callable[[str], None]]


class ScraperError(Exception):
    """Base exception for scraper-specific issues."""


class ConfigError(ScraperError):
    """Raised when the configuration file is missing or invalid."""


class LoginError(ScraperError):
    """Raised when login fails."""


class ScrapeError(ScraperError):
    """Raised when scraping an individual page fails."""


class Scraper:
    """Core scraping engine driven entirely by an external JSON config."""

    def __init__(self, config_file: str | Path, status_callback: StatusCallback = None) -> None:
        self.config_path = Path(config_file)
        self.status_callback = status_callback
        self.session = requests.Session()
        self.config: Dict[str, Any] = {}
        self._emit_status(f"Loading configuration from {self.config_path}...")
        self._load_config()
        self._apply_session_overrides()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Perform an optional login step if required by the configuration."""
        cookies = self.config.get("session_cookies")
        # Ensure cookies.values() is a list of known type
        if isinstance(cookies, dict) and any(bool(value) for value in list(cookies.values())):
            self._emit_status("Session cookies provided; skipping form-based login.")
            return

        if not self.config.get("login_required", False):
            self._emit_status("Login not required; skipping authentication.")
            return

        login_url = self.config.get("login_url")
        username_field = self.config.get("login_username_field")
        password_field = self.config.get("login_password_field")
        credentials = self.config.get("credentials", {})
        username = credentials.get("username")
        password = credentials.get("password")

        if not all([login_url, username_field, password_field, username, password]):
            raise LoginError(
                "Login configuration is incomplete. Please update config.json with the correct values."
            )

        payload = {
            str(username_field): str(username),
            str(password_field): str(password),
        }

        self._emit_status("Submitting login form...")
        try:
            # Explicitly cast login_url to str
            response = self.session.post(str(login_url), data=payload, timeout=15)
            response.raise_for_status()
            # TODO: Add website-specific login success verification (status code, redirected URL, or DOM check).
        except requests.RequestException as exc:
            raise LoginError(f"Login request failed: {exc}") from exc

        self._emit_status("Login completed (verification pending website-specific checks).")

    def scrape_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single page and return the extracted data dictionary."""
        delay = max(int(self.config.get("rate_limit_delay", 1)), 0)
        if delay:
            time.sleep(delay)

        self._emit_status(f"Fetching {url}...")
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            self._emit_status(f"Network error while fetching {url}: {exc}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        capture_mode = self._get_capture_mode()

        try:
            if capture_mode == "raw":
                data = self._capture_raw(url, response, soup)
            else:
                data = self._capture_parsed(url, soup)

            tables = self._extract_tables(soup)
            if tables:
                data["tables"] = tables

            images = self._extract_images(soup, url)
            if images:
                data["images"] = images

            self._emit_status(f"Successfully scraped {url}.")
            return data
        except ScrapeError as exc:
            self._emit_status(f"Parsing error for {url}: {exc}")
            return None
        except Exception as exc:  # Catch unexpected parsing edge cases.
            self._emit_status(f"Unexpected parsing error for {url}: {exc}")
            return None

    def save_data(self, data: Iterable[Dict[str, Any]]) -> Path:
        """Persist scraped data using the configured output format."""
        data_list = list(data)
        if not data_list:
            raise ScraperError("No data was scraped; nothing to save.")

        output_format = (self.config.get("output_format") or "").lower()
        output_filename = self._require_config_value("output_filename")
        output_path = (self.config_path.parent / output_filename).resolve()

        if output_format == "csv":
            self._save_to_csv(data_list, output_path)
        elif output_format == "json":
            self._save_to_json(data_list, output_path)
        elif output_format == "sqlite":
            self._save_to_sqlite(data_list, output_path)
        else:
            raise ScraperError(f"Unsupported output format: {output_format}")

        self._emit_status(f"Data saved to {output_path}")
        return output_path

    def run(self) -> List[Dict[str, Any]]:
        """Execute the full scraping workflow."""
        self._emit_status("Starting scraping workflow...")
        self.login()

        results: List[Dict[str, Any]] = []
        for url in self.config.get("start_urls", []):
            if not url:
                continue
            try:
                page_data = self.scrape_page(url)
                if page_data:
                    results.append(page_data)
            except Exception as exc:
                self._emit_status(f"Unhandled error while scraping {url}: {exc}")

        if not results:
            self._emit_status("No successful scrapes were recorded.")
            return []

        try:
            self.save_data(results)
        except ScraperError as exc:
            self._emit_status(str(exc))
            raise

        self._emit_status("Scraping workflow completed.")
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        if not self.config_path.exists():
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        try:
            raw = self.config_path.read_text(encoding="utf-8")
            self.config = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Failed to parse JSON configuration: {exc}") from exc

    def _apply_session_overrides(self) -> None:
        """Apply optional headers or cookies so existing browser sessions can be reused."""
        self.session.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
        )

        headers = self.config.get("request_headers")
        if isinstance(headers, dict) and headers:
            sanitized_headers = {str(key): str(value) for key, value in headers.items() if value is not None}
            if sanitized_headers:
                self.session.headers.update(sanitized_headers)
                self._emit_status("Applied custom request headers from configuration.")

        cookies = self.config.get("session_cookies")
        if isinstance(cookies, dict) and cookies:
            for key, value in cookies.items():
                if value is None:
                    continue
                self.session.cookies.set(str(key), str(value))
            self._emit_status("Applied session cookies from configuration.")

    def _get_capture_mode(self) -> str:
        mode = str(self.config.get("capture_mode", "parsed")).lower()
        if mode not in {"parsed", "raw"}:
            self._emit_status(f"Unknown capture_mode '{mode}', defaulting to 'parsed'.")
            return "parsed"
        return mode

    def _capture_parsed(self, url: str, soup: BeautifulSoup) -> Dict[str, Any]:
        question_selector = self._require_config_value("question_selector")
        answer_selector = self._require_config_value("answer_selector")
        explanation_selector = self._require_config_value("explanation_selector")

        question_element = soup.select_one(question_selector)
        if not question_element:
            raise ScrapeError(f"Question selector '{question_selector}' did not match any elements.")

        answer_elements = soup.select(answer_selector)
        if not answer_elements:
            raise ScrapeError(f"Answer selector '{answer_selector}' did not match any elements.")

        explanation_element = soup.select_one(explanation_selector)
        if not explanation_element:
            raise ScrapeError(f"Explanation selector '{explanation_selector}' did not match any elements.")

        answers: List[str] = [element.get_text(strip=True) for element in answer_elements]
        question_text = question_element.get_text(strip=True)
        explanation_text = explanation_element.get_text(strip=True)

        return {
            "url": url,
            "question": question_text,
            "answers": answers,
            "explanation": explanation_text,
        }

    def _capture_raw(self, url: str, response: requests.Response, soup: BeautifulSoup) -> Dict[str, Any]:
        include_text = bool(self.config.get("raw_include_text", True))
        data: Dict[str, Any] = {
            "url": url,
            "status_code": response.status_code,
            # Use timezone-aware UTC datetime
            "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "raw_html": response.text,
        }
        if include_text:
            data["raw_text"] = soup.get_text(separator="\n", strip=True)
        return data

    def _extract_tables(self, soup: BeautifulSoup) -> List[List[List[str]]]:
        tables: List[List[List[str]]] = []
        selectors = self.config.get("table_selectors") or []
        if isinstance(selectors, str):
            selectors = [selectors]

        if not isinstance(selectors, list):
            return tables

        for selector in selectors:
            if not isinstance(selector, str) or not selector:
                continue
            for table_tag in soup.select(str(selector)):
                parsed_table = self._parse_html_table(table_tag)
                if parsed_table:
                    tables.append(parsed_table)
        return tables

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        images: List[str] = []
        selectors = self.config.get("image_selectors") or []
        if isinstance(selectors, str):
            selectors = [selectors]

        if not isinstance(selectors, list):
            return images

        for selector in selectors:
            if not isinstance(selector, str) or not selector:
                continue
            for image_tag in soup.select(str(selector)):
                src = image_tag.get("src")
                if not isinstance(src, str) or not src:
                    continue
                absolute_url = urljoin(base_url, str(src))
                if absolute_url not in images:
                    images.append(absolute_url)
        return images

    def _parse_html_table(self, table: Tag) -> List[List[str]]:
        rows: List[List[str]] = []
        for row in table.find_all("tr"):
            cells = [str(cell.get_text(strip=True)) for cell in row.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        return rows

    def _require_config_value(self, key: str) -> Any:
        value = self.config.get(key)
        if value in (None, ""):
            raise ConfigError(f"Missing required configuration value: {key}")
        return value

    def _emit_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _save_to_csv(self, data: List[Dict[str, Any]], output_path: Path) -> None:
        fieldnames = self._collect_fieldnames(data)
        list_fields = {"answers", "tables", "images"}
        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                csv_row: Dict[str, Any] = {}
                for field in fieldnames:
                    value = row.get(field)
                    if field in list_fields and isinstance(value, list):
                        value = json.dumps(value, ensure_ascii=False)
                    csv_row[field] = self._coerce_for_csv(value)
                writer.writerow(csv_row)

    def _save_to_json(self, data: List[Dict[str, Any]], output_path: Path) -> None:
        with output_path.open("w", encoding="utf-8") as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=2)

    def _save_to_sqlite(self, data: List[Dict[str, Any]], output_path: Path) -> None:
        table_name = "scraped_data"
        fieldnames = self._collect_fieldnames(data)
        list_fields = {"answers", "tables", "images"}
        connection = sqlite3.connect(output_path)
        try:
            cursor = connection.cursor()
            columns_sql = ",\n".join(f'"{name}" TEXT' for name in fieldnames)
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {columns_sql}
                )
                """
            )

            placeholders = ", ".join("?" for _ in fieldnames)
            column_list = ", ".join(f'"{name}"' for name in fieldnames)
            insert_sql = f"INSERT INTO {table_name} ({column_list}) VALUES ({placeholders})"

            rows: List[List[Any]] = []
            for row in data:
                sqlite_row: List[Any] = []
                for field in fieldnames:
                    value = row.get(field)
                    if field in list_fields and isinstance(value, list):
                        value = json.dumps(value, ensure_ascii=False)
                    sqlite_row.append(self._coerce_for_sqlite(value))
                rows.append(sqlite_row)

            cursor.executemany(insert_sql, rows)
            connection.commit()
        finally:
            connection.close()

    def _collect_fieldnames(self, data: List[Dict[str, Any]]) -> List[str]:
        fieldnames: List[str] = []
        for row in data:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        for required in ("tables", "images"):
            if required not in fieldnames:
                fieldnames.append(required)
        return fieldnames

    def _coerce_for_csv(self, value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value

    def _coerce_for_sqlite(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return value


__all__ = ["Scraper", "ScraperError", "ConfigError", "LoginError", "ScrapeError"]
