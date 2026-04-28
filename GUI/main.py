import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QTableWidgetItem

# Allow GUI/main.py to import backend_bridge.py from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_bridge import run_analysis
from ui_hawkeye import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.latest_result = None

        self.ui.runButton.clicked.connect(self.run_analysis)
        self.ui.clearButton.clicked.connect(self.clear_fields)
        self.ui.chooseImageButton.clicked.connect(self.choose_image)
        self.ui.exportJsonButton.clicked.connect(self.export_json)

    def choose_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Image",
            "",
            "Images (*.png *.jpg *.jpeg *.jfif *.webp *.bmp);;All Files (*)",
        )
        if not file_path:
            return

        self.ui.imagePathInput.setText(file_path)
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

    def run_analysis(self):
        self.ui.statusLabel.setText("Running analysis...")
        self.ui.runProgressBar.setValue(10)
        self.ui.logsPlainTextEdit.appendPlainText("Run Analysis clicked.")
        QApplication.processEvents()

        reddit_url = self.ui.redditUrlInput.text().strip()
        claim_text = self.ui.claimTextInput.toPlainText().strip()
        image_path = self.ui.imagePathInput.text().strip()

        try:
            # Run the active LLM prompt path from the GUI/backend bridge.
            result = run_analysis(
                reddit_url=reddit_url,
                claim_text=claim_text,
                image_path=image_path,
                run_notebook=True,
            )
            self.latest_result = result
            self.display_result(result)
            self.ui.statusLabel.setText("Analysis complete")
            self.ui.runProgressBar.setValue(100)
        except Exception as exc:
            self.ui.statusLabel.setText("Analysis failed")
            self.ui.runProgressBar.setValue(0)
            self.ui.logsPlainTextEdit.appendPlainText(f"ERROR: {exc}")
            self.ui.explanationTextEdit.setPlainText(str(exc))

    def display_result(self, result):
        self.ui.verdictResultLabel.setText(str(result.get("verdict", "No result")))
        self.ui.confidenceProgressBar.setValue(int(result.get("confidence", 0) or 0))
        self.ui.explanationTextEdit.setPlainText(str(result.get("explanation", "")))
        self.ui.rawEvidencePlainTextEdit.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))

        self.ui.logsPlainTextEdit.appendPlainText("Backend bridge returned a result.")
        for line in result.get("logs", []):
            self.ui.logsPlainTextEdit.appendPlainText(str(line))

        manifest = result.get("manifest", []) or []
        self.populate_sources_table(manifest)
        self.populate_timeline_table(manifest)

        self.ui.mainTabs.setCurrentWidget(self.ui.verdictTab)

    def populate_sources_table(self, manifest):
        self.ui.sourcesTableWidget.setRowCount(0)
        for row, item in enumerate(manifest):
            self.ui.sourcesTableWidget.insertRow(row)
            source_url = str(item.get("source_url", ""))
            domain = source_url.split("/")[2] if source_url.startswith("http") and len(source_url.split("/")) > 2 else ""
            values = [
                domain,
                "",
                "",
                "loaded",
                str(item.get("title", "")),
                source_url,
            ]
            for col, value in enumerate(values):
                self.ui.sourcesTableWidget.setItem(row, col, QTableWidgetItem(value))
        self.ui.sourcesTableWidget.resizeColumnsToContents()

    def populate_timeline_table(self, manifest):
        self.ui.timelineTableWidget.setRowCount(0)
        for row, item in enumerate(manifest):
            self.ui.timelineTableWidget.insertRow(row)
            values = [
                "",
                str(item.get("title", "")),
                str(item.get("source_url", "")),
                "manifest loaded",
            ]
            for col, value in enumerate(values):
                self.ui.timelineTableWidget.setItem(row, col, QTableWidgetItem(value))
        self.ui.timelineTableWidget.resizeColumnsToContents()

    def export_json(self):
        if not self.latest_result:
            self.ui.logsPlainTextEdit.appendPlainText("No result to export yet.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            "hawkeye_result.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.latest_result, f, indent=2, ensure_ascii=False)
        self.ui.logsPlainTextEdit.appendPlainText(f"Exported JSON to {file_path}")

    def clear_fields(self):
        self.ui.redditUrlInput.clear()
        self.ui.claimTextInput.clear()
        self.ui.imagePathInput.clear()
        self.ui.imagePreviewLabel.setPixmap(QPixmap())
        self.ui.imagePreviewLabel.setText("Image preview")
        self.ui.logsPlainTextEdit.clear()
        self.ui.rawEvidencePlainTextEdit.clear()
        self.ui.explanationTextEdit.clear()
        self.ui.verdictResultLabel.setText("No result yet")
        self.ui.confidenceProgressBar.setValue(0)
        self.ui.runProgressBar.setValue(0)
        self.ui.sourcesTableWidget.setRowCount(0)
        self.ui.timelineTableWidget.setRowCount(0)
        self.ui.statusLabel.setText("Ready")
        self.latest_result = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
