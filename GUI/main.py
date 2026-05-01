import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QComboBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Allow GUI/main.py to import backend_bridge.py from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_bridge import (
    _download_public_image,
    _is_http_url,
    run_analysis,
    run_exiftool_analysis,
    run_reverse_image_search,
    fetch_reddit_top_articles,
)
from ui_hawkeye import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.latest_result = None
        self.latest_exif_result = None
        self.latest_reverse_image_result = None
        self.current_reddit_articles = []
        self.setup_reddit_tab()
        self.setup_exif_tab()
        self.remove_main_tab_image_controls()

        self.ui.runButton.clicked.connect(self.run_analysis)
        self.ui.clearButton.clicked.connect(self.clear_fields)
        self.ui.exportJsonButton.clicked.connect(self.export_json)



    def remove_main_tab_image_controls(self):
        """Hide the old image picker from the main article-analysis tab."""
        for widget_name in (
            "imagePathLabel",
            "imagePathInput",
            "chooseImageButton",
            "imagePreviewLabel",
        ):
            widget = getattr(self.ui, widget_name, None)
            if widget is not None:
                widget.hide()

    def setup_reddit_tab(self):
        """Create a separate Reddit tab before Image Work.

        This tab pulls top r/worldnews posts, displays the external news links,
        and sends the selected article URL into the same run_analysis() path
        used by the main News URL tab.
        """
        self.redditTab = QWidget()
        self.redditTab.setObjectName("redditTab")
        layout = QVBoxLayout(self.redditTab)

        intro = QLabel(
            "Reddit article intake. Pulls the top 10 external article links from r/worldnews, "
            "then runs the selected article through the same analysis used by the main News URL tab."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.redditSubreddit = "worldnews"
        self.redditSourceLabel = QLabel("Source: r/worldnews")

        self.redditTimeFilterComboBox = QComboBox()
        self.redditTimeFilterComboBox.addItems(["hour", "day", "week", "month", "year", "all"])
        self.redditTimeFilterComboBox.setCurrentText("day")

        self.loadRedditButton = QPushButton("Load Top 10")
        self.runRedditAnalysisButton = QPushButton("Analyze Selected")

        controls.addWidget(self.redditSourceLabel)
        controls.addWidget(QLabel("Top:"))
        controls.addWidget(self.redditTimeFilterComboBox)
        controls.addWidget(self.loadRedditButton)
        controls.addWidget(self.runRedditAnalysisButton)
        layout.addLayout(controls)

        self.redditArticlesTableWidget = QTableWidget(0, 5)
        self.redditArticlesTableWidget.setHorizontalHeaderLabels(
            ["Title", "Source URL", "Score", "Comments", "Reddit Post"]
        )
        self.redditArticlesTableWidget.setSelectionBehavior(QTableWidget.SelectRows)
        self.redditArticlesTableWidget.setSelectionMode(QTableWidget.SingleSelection)
        self.redditArticlesTableWidget.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.redditArticlesTableWidget)

        self.redditClaimTextInput = QPlainTextEdit()
        self.redditClaimTextInput.setPlaceholderText(
            "Optional claim/caption to compare against the selected Reddit article."
        )
        self.redditClaimTextInput.setMaximumHeight(90)
        layout.addWidget(self.redditClaimTextInput)

        self.redditOutputPlainTextEdit = QPlainTextEdit()
        self.redditOutputPlainTextEdit.setReadOnly(True)
        self.redditOutputPlainTextEdit.setPlaceholderText("Reddit loading and selected article details appear here.")
        layout.addWidget(self.redditOutputPlainTextEdit)

        self.ui.mainTabs.insertTab(2, self.redditTab, "Reddit")

        self.loadRedditButton.clicked.connect(self.load_reddit_articles)
        self.runRedditAnalysisButton.clicked.connect(self.run_selected_reddit_article)
        self.redditArticlesTableWidget.cellDoubleClicked.connect(lambda row, col: self.run_selected_reddit_article())

    def load_reddit_articles(self):
        subreddit = self.redditSubreddit
        time_filter = self.redditTimeFilterComboBox.currentText()

        self.ui.statusLabel.setText("Loading Reddit articles...")
        self.redditOutputPlainTextEdit.setPlainText("Loading top Reddit articles...")
        QApplication.processEvents()

        try:
            result = fetch_reddit_top_articles(
                subreddit=subreddit,
                time_filter=time_filter,
                limit=10,
                scan_limit=50,
            )
            self.current_reddit_articles = result.get("articles", []) or []
            self.populate_reddit_table(self.current_reddit_articles)

            output_lines = [
                f"Loaded {len(self.current_reddit_articles)} external article link(s) from r/{result.get('subreddit', subreddit)}.",
                "",
            ]
            output_lines.extend(str(line) for line in result.get("logs", []))
            self.redditOutputPlainTextEdit.setPlainText("\n".join(output_lines))

            self.ui.logsPlainTextEdit.appendPlainText("Reddit top articles loaded.")
            for line in result.get("logs", []):
                self.ui.logsPlainTextEdit.appendPlainText(str(line))
            self.ui.statusLabel.setText("Reddit articles loaded")
        except Exception as exc:
            self.current_reddit_articles = []
            self.redditArticlesTableWidget.setRowCount(0)
            self.ui.statusLabel.setText("Reddit loading failed")
            self.redditOutputPlainTextEdit.setPlainText(str(exc))
            self.ui.logsPlainTextEdit.appendPlainText(f"REDDIT ERROR: {exc}")

    def populate_reddit_table(self, articles):
        self.redditArticlesTableWidget.setRowCount(0)

        for row, article in enumerate(articles):
            self.redditArticlesTableWidget.insertRow(row)
            values = [
                str(article.get("title", "")),
                str(article.get("source_url", "")),
                str(article.get("score", "")),
                str(article.get("num_comments", "")),
                str(article.get("reddit_permalink", "")),
            ]
            for col, value in enumerate(values):
                self.redditArticlesTableWidget.setItem(row, col, QTableWidgetItem(value))

        self.redditArticlesTableWidget.resizeColumnsToContents()
        if articles:
            self.redditArticlesTableWidget.selectRow(0)

    def run_selected_reddit_article(self):
        row = self.redditArticlesTableWidget.currentRow()
        if row < 0 or row >= len(self.current_reddit_articles):
            self.redditOutputPlainTextEdit.setPlainText("Select a Reddit article first.")
            return

        article = self.current_reddit_articles[row]
        article_url = str(article.get("source_url", "")).strip()
        claim_text = self.redditClaimTextInput.toPlainText().strip()

        if not article_url:
            self.redditOutputPlainTextEdit.setPlainText("Selected Reddit row does not have an external article URL.")
            return

        # Keep the main tab fields in sync so the demo visibly shows the same analysis path.
        self.ui.redditUrlInput.setText(article_url)
        self.ui.claimTextInput.setPlainText(claim_text)

        self.ui.statusLabel.setText("Analyzing selected Reddit article...")
        self.ui.runProgressBar.setValue(10)
        self.redditOutputPlainTextEdit.setPlainText(
            f"Analyzing selected Reddit article:\n{article.get('title', '')}\n\n{article_url}"
        )
        QApplication.processEvents()

        try:
            result = run_analysis(
                reddit_url=article_url,
                claim_text=claim_text,
                image_path="",
                run_notebook=True,
            )
            result.setdefault("reddit_selection", article)
            self.latest_result = result
            self.display_result(result)
            self.ui.statusLabel.setText("Reddit article analysis complete")
            self.ui.runProgressBar.setValue(100)
        except Exception as exc:
            self.ui.statusLabel.setText("Reddit article analysis failed")
            self.ui.runProgressBar.setValue(0)
            self.redditOutputPlainTextEdit.setPlainText(str(exc))
            self.ui.logsPlainTextEdit.appendPlainText(f"REDDIT ANALYSIS ERROR: {exc}")


    def setup_exif_tab(self):
        """Create the Image Work tab without needing to edit the .ui file."""
        self.exifTab = QWidget()
        self.exifTab.setObjectName("imageWorkTab")
        layout = QVBoxLayout(self.exifTab)

        intro = QLabel(
            "Image Work tools. Choose a local image for ExifTool, or paste a public image URL for automatic reverse image search."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        self.exifImagePathInput = QLineEdit()
        self.exifImagePathInput.setReadOnly(False)
        self.exifImagePathInput.setPlaceholderText("Choose a local image, or paste a public image URL for reverse search")
        self.chooseExifImageButton = QPushButton("Choose Image")
        self.runExifButton = QPushButton("Run ExifTool")
        self.runReverseImageSearchButton = QPushButton("Reverse Image Search")
        row.addWidget(self.exifImagePathInput)
        row.addWidget(self.chooseExifImageButton)
        row.addWidget(self.runExifButton)
        row.addWidget(self.runReverseImageSearchButton)
        layout.addLayout(row)

        self.exifPreviewLabel = QLabel("Image preview")
        self.exifPreviewLabel.setMinimumSize(0, 180)
        self.exifPreviewLabel.setFrameShape(QFrame.Box)
        self.exifPreviewLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.exifPreviewLabel)

        self.exifOutputPlainTextEdit = QPlainTextEdit()
        self.exifOutputPlainTextEdit.setReadOnly(True)
        self.exifOutputPlainTextEdit.setPlaceholderText("ExifTool or reverse image search output will appear here.")
        layout.addWidget(self.exifOutputPlainTextEdit)

        reddit_index = self.ui.mainTabs.indexOf(self.redditTab) if hasattr(self, "redditTab") else 1
        self.ui.mainTabs.insertTab(reddit_index + 1, self.exifTab, "Image Work")

        self.chooseExifImageButton.clicked.connect(self.choose_exif_image)
        self.exifImagePathInput.editingFinished.connect(self.update_exif_preview_from_input)
        self.runExifButton.clicked.connect(self.run_exiftool)
        self.runReverseImageSearchButton.clicked.connect(self.run_reverse_image_search)

    def _load_pixmap_into_exif_preview(self, image_path: str) -> bool:
        """Load a local image file into the Image Work preview pane."""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.exifPreviewLabel.setPixmap(QPixmap())
            self.exifPreviewLabel.setText("Could not preview image")
            return False

        scaled = pixmap.scaled(
            self.exifPreviewLabel.width(),
            self.exifPreviewLabel.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.exifPreviewLabel.setPixmap(scaled)
        return True

    def update_exif_preview_from_input(self):
        """Preview either a local image path or a public image URL.

        QPixmap can load local files, but it cannot load web URLs directly.
        For URLs, resolve/download the image first, then preview that downloaded copy.
        """
        value = self.exifImagePathInput.text().strip()
        if not value:
            self.exifPreviewLabel.setPixmap(QPixmap())
            self.exifPreviewLabel.setText("Image preview")
            return

        if _is_http_url(value):
            self.exifPreviewLabel.setText("Downloading image preview...")
            QApplication.processEvents()
            logs = []
            downloaded_path, resolved_url = _download_public_image(value, logs)
            if downloaded_path and downloaded_path.exists():
                self._load_pixmap_into_exif_preview(str(downloaded_path))
                self.ui.logsPlainTextEdit.appendPlainText(f"Image preview loaded from URL: {resolved_url}")
            else:
                self.exifPreviewLabel.setPixmap(QPixmap())
                self.exifPreviewLabel.setText("Could not preview URL image")
                for line in logs:
                    self.ui.logsPlainTextEdit.appendPlainText(str(line))
            return

        self._load_pixmap_into_exif_preview(value)

    def choose_exif_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Image for Image Work",
            "",
            "Images (*.png *.jpg *.jpeg *.jfif *.webp *.bmp *.gif *.tif *.tiff);;All Files (*)",
        )
        if not file_path:
            return

        self.exifImagePathInput.setText(file_path)
        self.update_exif_preview_from_input()

    def run_exiftool(self):
        image_path = self.exifImagePathInput.text().strip()
        self.update_exif_preview_from_input()
        self.ui.statusLabel.setText("Running ExifTool...")
        self.exifOutputPlainTextEdit.setPlainText("Running ExifTool...")
        QApplication.processEvents()

        try:
            result = run_exiftool_analysis(image_path)
            self.latest_exif_result = result

            output_parts = []
            if result.get("error"):
                output_parts.append(f"ERROR: {result.get('error')}")

            if result.get("exiftool_text"):
                output_parts.append(result.get("exiftool_text", ""))
            else:
                output_parts.append(json.dumps(result, indent=2, ensure_ascii=False))

            self.exifOutputPlainTextEdit.setPlainText("\n\n".join(output_parts))
            self.ui.rawEvidencePlainTextEdit.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
            self.ui.logsPlainTextEdit.appendPlainText("ExifTool standalone analysis completed.")
            for line in result.get("logs", []):
                self.ui.logsPlainTextEdit.appendPlainText(str(line))
            self.ui.statusLabel.setText("ExifTool complete")
        except Exception as exc:
            self.ui.statusLabel.setText("ExifTool failed")
            self.exifOutputPlainTextEdit.setPlainText(str(exc))
            self.ui.logsPlainTextEdit.appendPlainText(f"EXIFTOOL ERROR: {exc}")


    def run_reverse_image_search(self):
        image_path = self.exifImagePathInput.text().strip()
        self.update_exif_preview_from_input()
        self.ui.statusLabel.setText("Running reverse image search...")
        self.exifOutputPlainTextEdit.setPlainText("Running reverse image search...")
        QApplication.processEvents()

        try:
            query = Path(image_path).stem if image_path else "reverse image search"
            result = run_reverse_image_search(image_path_or_url=image_path, query=query)
            self.latest_reverse_image_result = result

            text_output = result.get("text_output") or json.dumps(result, indent=2, ensure_ascii=False)
            self.exifOutputPlainTextEdit.setPlainText(text_output)
            self.ui.rawEvidencePlainTextEdit.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
            self.ui.logsPlainTextEdit.appendPlainText("Reverse image search completed.")
            for line in result.get("logs", []):
                self.ui.logsPlainTextEdit.appendPlainText(str(line))
            self.ui.statusLabel.setText("Reverse image search complete")
        except Exception as exc:
            self.ui.statusLabel.setText("Reverse image search failed")
            self.exifOutputPlainTextEdit.setPlainText(str(exc))
            self.ui.logsPlainTextEdit.appendPlainText(f"REVERSE IMAGE SEARCH ERROR: {exc}")


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
        image_path = ""

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
        if hasattr(self, "redditArticlesTableWidget"):
            self.current_reddit_articles = []
            self.redditArticlesTableWidget.setRowCount(0)
            self.redditClaimTextInput.clear()
            self.redditOutputPlainTextEdit.clear()
        if hasattr(self, "exifImagePathInput"):
            self.exifImagePathInput.clear()
            self.exifPreviewLabel.setPixmap(QPixmap())
            self.exifPreviewLabel.setText("Image preview")
            self.exifOutputPlainTextEdit.clear()
        self.ui.statusLabel.setText("Ready")
        self.latest_result = None
        self.latest_exif_result = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
