"""
main.py -- HawkEye OSINT Project
==================================
PySide6 GUI entry point for the HawkEye application.

Responsibilities:
    - Initialise the Qt application and main window
    - Wire GUI buttons to analysis actions
    - Validate user inputs before running analysis
    - Display results across the Verdict, Sources, Timeline, and Logs tabs
    - Handle JSON export

Usage:
    python GUI/main.py
"""

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QTableWidgetItem,
)

# Allow GUI/main.py to import backend_bridge.py from the project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_bridge import run_analysis
from ui_hawkeye import Ui_MainWindow

# ---------------------------------------------------------------------------
# Verdict display configuration
# Maps internal verdict keys to (display label, stylesheet colour string)
# ---------------------------------------------------------------------------
VERDICT_STYLES: dict[str, tuple[str, str]] = {
    "likely_authentic":               ("Likely Authentic",              "color: #2e7d32; font-weight: bold;"),
    "likely_misleading_or_clickbait": ("Likely Misleading / Clickbait", "color: #b71c1c; font-weight: bold;"),
    "uncertain":                      ("Uncertain",                     "color: #e65100; font-weight: bold;"),
}


class MainWindow(QMainWindow):
    """Main application window for HawkEye."""

    def __init__(self) -> None:
        super().__init__()

        self.ui            = Ui_MainWindow()
        self.latest_result = None

        self.ui.setupUi(self)
        self._configure_ui()
        self._connect_signals()

    # -----------------------------------------------------------------------
    # Initialisation helpers
    # -----------------------------------------------------------------------

    def _configure_ui(self) -> None:
        """Set placeholder text and initial widget state."""
        self.ui.redditUrlInput.setPlaceholderText(
            "Paste a direct news article URL  "
            "(e.g. https://bbc.com/news/...  or  https://reuters.com/...)"
        )
        self.ui.claimTextInput.setPlaceholderText(
            "Optional: enter the claim or image caption to fact-check against the article."
        )
        self.ui.statusLabel.setText("Ready")

    def _connect_signals(self) -> None:
        """Connect all button click signals to their handler methods."""
        self.ui.runButton.clicked.connect(self._on_run_analysis)
        self.ui.clearButton.clicked.connect(self._on_clear_fields)
        self.ui.chooseImageButton.clicked.connect(self._on_choose_image)
        self.ui.exportJsonButton.clicked.connect(self._on_export_json)

    # -----------------------------------------------------------------------
    # Input validation
    # -----------------------------------------------------------------------

    def _validate_inputs(self) -> bool:
        """
        Validate user inputs before running the analysis.

        Checks:
            - At least a URL or a claim is provided.
            - Warns (but does not block) if a Reddit URL is entered directly,
              since the backend will attempt to resolve it automatically.

        Returns:
            True if inputs are acceptable to proceed, False otherwise.
        """
        url        = self.ui.redditUrlInput.text().strip()
        claim_text = self.ui.claimTextInput.toPlainText().strip()

        if not url and not claim_text:
            self._log("Please enter a news article URL or a claim before running analysis.")
            self.ui.statusLabel.setText("No input provided")
            return False

        if url and "reddit.com" in url.lower():
            self._log(
                "Note: You entered a Reddit URL. "
                "HawkEye will attempt to extract the linked article automatically. "
                "For best results, paste the direct news article URL instead."
            )

        return True

    # -----------------------------------------------------------------------
    # Button handlers
    # -----------------------------------------------------------------------

    def _on_choose_image(self) -> None:
        """Open a file dialog to select a local image and display a preview."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Image",
            "",
            "Images (*.png *.jpg *.jpeg *.jfif *.webp *.bmp);;All Files (*)",
        )
        if not file_path:
            return

        self.ui.imagePathInput.setText(file_path)
        self._log(f"Image selected: {file_path}")

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.ui.imagePreviewLabel.width(),
                self.ui.imagePreviewLabel.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.ui.imagePreviewLabel.setPixmap(scaled)
        else:
            self.ui.imagePreviewLabel.setText("Could not preview image")

    def _on_run_analysis(self) -> None:
        """Validate inputs then execute the full analysis pipeline."""
        if not self._validate_inputs():
            return

        self.ui.statusLabel.setText("Running analysis...")
        self.ui.runProgressBar.setValue(10)
        self._log("Analysis started.")
        QApplication.processEvents()

        url        = self.ui.redditUrlInput.text().strip()
        claim_text = self.ui.claimTextInput.toPlainText().strip()
        image_path = self.ui.imagePathInput.text().strip()

        try:
            result             = run_analysis(
                reddit_url   = url,
                claim_text   = claim_text,
                image_path   = image_path,
                run_notebook = True,
            )
            self.latest_result = result
            self._display_result(result)
            self.ui.statusLabel.setText("Analysis complete")
            self.ui.runProgressBar.setValue(100)

        except Exception as exc:
            self.ui.statusLabel.setText("Analysis failed")
            self.ui.runProgressBar.setValue(0)
            self._log(f"ERROR: {exc}")
            self.ui.explanationTextEdit.setPlainText(
                f"An unexpected error occurred:\n\n{exc}\n\n"
                "Check the Logs tab for details."
            )

    def _on_export_json(self) -> None:
        """Save the latest analysis result to a user-chosen JSON file."""
        if not self.latest_result:
            self._log("Nothing to export -- run an analysis first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Result as JSON",
            "hawkeye_result.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.latest_result, f, indent=2, ensure_ascii=False)
            self._log(f"Result exported to: {file_path}")
        except Exception as exc:
            self._log(f"Export failed: {exc}")

    def _on_clear_fields(self) -> None:
        """
        Reset all input and output fields to their initial state.

        Also deletes the cached Session/reverse_image_manifest.json so that
        the next analysis cannot accidentally fall back to a stale previous result.
        """
        # Clear all input widgets
        self.ui.redditUrlInput.clear()
        self.ui.claimTextInput.clear()
        self.ui.imagePathInput.clear()
        self.ui.imagePreviewLabel.setPixmap(QPixmap())
        self.ui.imagePreviewLabel.setText("Image preview")

        # Clear all output widgets
        self.ui.logsPlainTextEdit.clear()
        self.ui.rawEvidencePlainTextEdit.clear()
        self.ui.explanationTextEdit.clear()
        self.ui.verdictResultLabel.setText("No result yet")
        self.ui.verdictResultLabel.setStyleSheet("")
        self.ui.confidenceProgressBar.setValue(0)
        self.ui.runProgressBar.setValue(0)
        self.ui.sourcesTableWidget.setRowCount(0)
        self.ui.timelineTableWidget.setRowCount(0)
        self.ui.statusLabel.setText("Ready")
        self.latest_result = None

        # Delete the cached manifest so the next run cannot use stale data.
        # The manifest is re-created fresh each time a URL is successfully fetched.
        manifest_path = PROJECT_ROOT / "Session" / "reverse_image_manifest.json"
        try:
            if manifest_path.exists():
                manifest_path.unlink()
                self._log("Session cache cleared (reverse_image_manifest.json deleted).")
            else:
                self._log("Fields cleared.")
        except Exception as exc:
            self._log(f"Fields cleared. Warning: could not delete session cache: {exc}")

    # -----------------------------------------------------------------------
    # Result display
    # -----------------------------------------------------------------------

    def _display_result(self, result: dict) -> None:
        """
        Populate all output tabs with the analysis result.

        Args:
            result: Structured result dictionary returned by run_analysis().
        """
        # Verdict tab
        raw_verdict  = str(result.get("verdict", "uncertain")).lower()
        label, style = VERDICT_STYLES.get(
            raw_verdict,
            (result.get("verdict", "No result"), "font-weight: bold;"),
        )
        self.ui.verdictResultLabel.setText(label)
        self.ui.verdictResultLabel.setStyleSheet(style)
        self.ui.confidenceProgressBar.setValue(int(result.get("confidence", 0) or 0))
        self.ui.explanationTextEdit.setPlainText(str(result.get("explanation", "")))

        # Raw Evidence tab
        self.ui.rawEvidencePlainTextEdit.setPlainText(
            json.dumps(result, indent=2, ensure_ascii=False)
        )

        # Logs tab
        self._log("Backend analysis returned a result.")
        for line in result.get("logs", []):
            self._log(str(line))

        # Sources and Timeline tabs
        manifest = result.get("manifest") or []
        self._populate_sources_table(manifest)
        self._populate_timeline_table(manifest)

        # Switch to Verdict tab automatically
        self.ui.mainTabs.setCurrentWidget(self.ui.verdictTab)

    def _populate_sources_table(self, manifest: list[dict]) -> None:
        """
        Fill the Sources table with one row per manifest item.

        Columns: Domain | Text Status | Title | URL

        Args:
            manifest: List of article metadata dictionaries.
        """
        self.ui.sourcesTableWidget.setRowCount(0)

        for row, item in enumerate(manifest):
            self.ui.sourcesTableWidget.insertRow(row)

            source_url  = str(item.get("source_url", ""))
            parts       = source_url.split("/")
            domain      = parts[2] if source_url.startswith("http") and len(parts) > 2 else "unknown"
            text_status = (
                "Text extracted"
                if item.get("article_text_char_count", 0) > 200
                else "Limited text"
            )

            values = [domain, text_status, str(item.get("title", "")), source_url]
            for col, value in enumerate(values):
                self.ui.sourcesTableWidget.setItem(row, col, QTableWidgetItem(value))

        self.ui.sourcesTableWidget.resizeColumnsToContents()

    def _populate_timeline_table(self, manifest: list[dict]) -> None:
        """
        Fill the Timeline table with one row per manifest item.

        Columns: # | Title | Source URL | Status

        Args:
            manifest: List of article metadata dictionaries.
        """
        self.ui.timelineTableWidget.setRowCount(0)

        for row, item in enumerate(manifest):
            self.ui.timelineTableWidget.insertRow(row)

            values = [
                str(row + 1),
                str(item.get("title", "")),
                str(item.get("source_url", "")),
                "Fetched" if item.get("article_text_char_count", 0) > 0 else "No text",
            ]
            for col, value in enumerate(values):
                self.ui.timelineTableWidget.setItem(row, col, QTableWidgetItem(value))

        self.ui.timelineTableWidget.resizeColumnsToContents()

    # -----------------------------------------------------------------------
    # Logging helper
    # -----------------------------------------------------------------------

    def _log(self, message: str) -> None:
        """Append a timestamped message to the Logs plain-text widget."""
        self.ui.logsPlainTextEdit.appendPlainText(message)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app    = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
