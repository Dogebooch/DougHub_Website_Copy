"""PyQt5 GUI for the configurable web scraping application."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List

from PyQt5 import QtCore, QtWidgets

from scraper import ConfigError, LoginError, Scraper, ScraperError


class ScraperGUI(QtWidgets.QWidget):
    """Main application window combining the view and controller roles."""

    log_signal = QtCore.pyqtSignal(str)
    scraping_complete = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Configurable Web Scraper")
        self.resize(800, 600)

        self.config_path = Path(__file__).resolve().parent / "config.json"
        self._scraper_thread: threading.Thread | None = None

        self.log_signal.connect(self._append_log)
        self.scraping_complete.connect(self._on_scraping_complete)

        self._init_ui()
        self._load_config_into_ui()

    # ------------------------------------------------------------------
    # UI setup and configuration helpers
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        url_label = QtWidgets.QLabel("Start URLs (comma separated):")
        layout.addWidget(url_label)

        self.url_input = QtWidgets.QLineEdit()
        layout.addWidget(self.url_input)

        self.log_output = QtWidgets.QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output, stretch=1)

        button_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Start Scraping")
        self.start_button.clicked.connect(self.start_scraping)

        self.config_button = QtWidgets.QPushButton("Edit Config")
        self.config_button.clicked.connect(self.open_config_file)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.config_button)
        layout.addLayout(button_layout)

    def _load_config(self) -> Dict[str, Any]:
        try:
            raw = self.config_path.read_text(encoding="utf-8")
            return json.loads(raw)
        except FileNotFoundError:
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in configuration file: {exc}") from exc

    def _load_config_into_ui(self) -> None:
        try:
            config = self._load_config()
        except ConfigError as exc:
            self.log_signal.emit(str(exc))
            return

        start_urls = config.get("start_urls", []) or []
        joined_urls = ", ".join(start_urls)
        self.url_input.setText(joined_urls)

    def _persist_urls(self, urls: List[str]) -> None:
        config = self._load_config()
        config["start_urls"] = urls
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def start_scraping(self) -> None:
        self.log_output.clear()
        self.start_button.setEnabled(False)

        raw_urls = self.url_input.text().split(",")
        urls = [url.strip() for url in raw_urls if url.strip()]

        try:
            self._persist_urls(urls)
        except ConfigError as exc:
            self.log_signal.emit(str(exc))
            self.start_button.setEnabled(True)
            return
        except Exception as exc:  # Catch filesystem issues such as permissions.
            self.log_signal.emit(f"Failed to update configuration: {exc}")
            self.start_button.setEnabled(True)
            return

        if not urls:
            self.log_signal.emit("No URLs provided. Please enter at least one URL to scrape.")
            self.start_button.setEnabled(True)
            return

        self.log_signal.emit("Starting scraper in a background thread...")
        self._scraper_thread = threading.Thread(target=self.run_scraper_thread, daemon=True, name="ScraperThread")
        self._scraper_thread.start()

    def open_config_file(self) -> None:
        try:
            if sys.platform.startswith("win") and hasattr(os, "startfile"):
                os.startfile(self.config_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.config_path)])
            else:
                subprocess.Popen(["xdg-open", str(self.config_path)])
        except Exception as exc:
            self.log_signal.emit(f"Unable to open config file: {exc}")

    def run_scraper_thread(self) -> None:
        try:
            scraper = Scraper(self.config_path, status_callback=self.log_signal.emit)
            results = scraper.run()
            if results:
                summary = self._summarize_output(scraper)
                self.log_signal.emit(summary)
            else:
                self.log_signal.emit("Scraper finished without collecting any data. Check your selectors and URLs.")
        except (ConfigError, LoginError, ScraperError) as exc:
            self.log_signal.emit(f"Scraper error: {exc}")
        except Exception as exc:
            self.log_signal.emit(f"Unexpected error: {exc}")
        finally:
            self.scraping_complete.emit()

    # ------------------------------------------------------------------
    # Thread-safe UI helpers
    # ------------------------------------------------------------------
    @QtCore.pyqtSlot(str)
    def _append_log(self, message: str) -> None:
        self.log_output.append(message)

    @QtCore.pyqtSlot()
    def _on_scraping_complete(self) -> None:
        self.start_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Output summarisation
    # ------------------------------------------------------------------
    def _summarize_output(self, scraper: Scraper) -> str:
        config = scraper.config
        output_format = (config.get("output_format") or "").lower()
        output_filename = config.get("output_filename")
        if not output_filename:
            return "Scraping complete. Output filename missing from config; unable to display summary."

        output_path = (self.config_path.parent / output_filename).resolve()
        if not output_path.exists():
            return f"Scraping complete, but output file was not found at {output_path}."

        try:
            if output_format == "csv":
                preview = self._preview_text_file(output_path)
                return f"Scraping complete. Preview of {output_path.name}:\n{preview}"
            if output_format == "json":
                preview = self._preview_json(output_path)
                return f"Scraping complete. Preview of {output_path.name}:\n{preview}"
            if output_format == "sqlite":
                count = self._count_sqlite_rows(output_path)
                return f"Scraping complete. Stored {count} rows in {output_path.name}."
        except Exception as exc:
            return f"Scraping complete, but failed to read output file: {exc}"

        return f"Scraping complete. Output file saved to {output_path}."

    def _preview_text_file(self, path: Path, max_lines: int = 10) -> str:
        lines = path.read_text(encoding="utf-8").splitlines()
        preview_lines = lines[:max_lines]
        if len(lines) > max_lines:
            preview_lines.append("...")
        return "\n".join(preview_lines) if preview_lines else "(file is empty)"

    def _preview_json(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        pretty = json.dumps(data, ensure_ascii=False, indent=2)
        return pretty if len(pretty) <= 2000 else pretty[:2000] + "\n..."

    def _count_sqlite_rows(self, path: Path) -> int:
        connection = sqlite3.connect(path)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM scraped_data")
            (count,) = cursor.fetchone() or (0,)
            return int(count)
        finally:
            connection.close()


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = ScraperGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
