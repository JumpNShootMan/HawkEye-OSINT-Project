
# 🦅 HawkEye – OSINT Media Integrity Analyzer

HawkEye is a desktop GUI tool for analyzing news articles and images for potential misinformation, clickbait, or misleading content. It fetches article metadata, performs reverse image searches across Google, Yandex, and Bing, reads local image EXIF data, and sends a structured prompt to a local LLM (via [Ollama](https://ollama.com)) to produce a verdict.

---

## Project Structure

```
HawkEye/
├── GUI/
│   └── main.py                      # PySide6 application entry point
├── backend_bridge.py                # Core analysis logic (fetch, EXIF, LLM)
├── reverse_image_search.py          # Multi-engine reverse image search module
├── ui_hawkeye.py                    # Auto-generated Qt UI bindings
├── hawkeye.ui                       # Qt Designer UI layout file
├── POC.ipynb                        # Jupyter notebook proof-of-concept
├── hawkeye_result.json              # Last saved analysis result (auto-generated)
├── Session/                         # Auto-created at runtime
│   ├── reverse_image_manifest.json  # Fetched article metadata
│   ├── reverse_image_manifest.csv   # CSV export of manifest
│   ├── reverse_image_urls.txt       # Image URLs collected during search
│   └── reverse_image_files.txt      # Local image file paths collected
├── exiftool_files/                  # Optional bundled ExifTool (Windows)
│   ├── perl.exe
│   ├── exiftool.pl
│   └── *.dll
└── requirements.txt
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | 3.11 or 3.12 recommended |
| Ollama | Latest | Must be running locally |
| ExifTool | Optional | Bundled Windows version included |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/JumpNShootMan/HawkEye-OSINT-Project.git
cd HawkEye-OSINT-Project
```

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install and start Ollama

Download Ollama from [https://ollama.com/download](https://ollama.com/download), then pull the required model:

```bash
ollama pull llama3
ollama serve          # starts the API on http://127.0.0.1:11434
```

> HawkEye defaults to `llama3`. You can change `OLLAMA_MODEL` at the top of `backend_bridge.py` to use a different model (e.g. `mistral`, `phi3`).

### 5. (Windows only) Set up bundled ExifTool

The `exiftool_files/` folder contains a portable Perl + ExifTool bundle for Windows. No extra installation is needed — the bridge detects it automatically. On macOS/Linux, install ExifTool via your package manager:

```bash
# macOS
brew install exiftool

# Ubuntu / Debian
sudo apt install libimage-exiftool-perl
```

---

## Running the Application

```bash
# From the project root
python GUI/main.py
```

---

## How to Use

1. **Article URL** – Paste a direct news article URL into the *Article / Reddit URL* field. HawkEye fetches the title, description, and article text automatically.
2. **Claim / Caption** – Optionally type a claim or image caption you want to fact-check against the article.
3. **Image** – Click *Choose Image* to select a local image file. HawkEye reads its EXIF/metadata without uploading it anywhere.
4. **Run Analysis** – Click *Run Analysis*. The backend:
   - Fetches article metadata and full text
   - Runs a reverse image search across Google, Yandex, and Bing
   - Computes perceptual similarity scores between matched images
   - Reads local image EXIF metadata
   - Builds and sends a structured prompt to Ollama
   - Displays results across four tabs:
     - **Verdict**: `likely_authentic` | `uncertain` | `likely_misleading_or_clickbait`
     - **Confidence** score (0–100%)
     - **Sources** table with matched domains
     - **Timeline** of evidence items
5. **Export JSON** – Save the full result to a `.json` file for later review.

---

## Reverse Image Search

`reverse_image_search.py` queries three engines in order — Yandex → Google → Bing — and merges the results:

- **Deduplication** – identical links are removed across engines
- **Similarity scoring** – a perceptual hash (average hash) is computed for each candidate image and compared against the query image. Requires `Pillow`; falls back gracefully if unavailable.
- **Domain filtering** – social media and wallpaper sites (Twitter, Pinterest, Reddit, etc.) are excluded from article-quality counts
- **Fallback** – if no structured hits are found, the manifest source URL is used as a fallback result

The `Session/` folder is created automatically and stores the manifest JSON, CSV, and collected URL/file lists between runs.

---

## Configuration

All runtime configuration lives at the top of `backend_bridge.py`:

```python
OLLAMA_MODEL   = "llama3"                               # LLM model name
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"  # Ollama API endpoint
```

Reverse image search settings can be tuned in `reverse_image_search.py`:

```python
self.retry_count          = 3    # HTTP retry attempts per engine
self.similarity_threshold = 60   # Minimum % similarity to count a match
self.request_timeout      = 20   # Seconds before a request times out
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: PySide6` | Run `pip install -r requirements.txt` inside your venv |
| `ModuleNotFoundError: bs4` | Run `pip install beautifulsoup4` |
| `Ollama API call failed` | Make sure `ollama serve` is running and the model is pulled |
| Similarity scores all `None` | Install Pillow: `pip install Pillow` |
| `Could not fetch article URL` | Check internet connectivity; some sites block scrapers |
| EXIF metadata missing | Install ExifTool (see step 5) or place files in `exiftool_files/` |
| `Analysis failed` with no detail | Check the Logs tab in the GUI for the full error message |

---

## Dependencies

- [PySide6](https://doc.qt.io/qtforpython/) – Qt6 GUI bindings for Python
- [requests](https://requests.readthedocs.io/) – HTTP fetching for articles and image searches
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) – HTML parsing for reverse image search results
- [lxml](https://lxml.de/) – Fast HTML/XML parser backend for BeautifulSoup
- [Pillow](https://python-pillow.org/) – Perceptual image hashing for similarity scoring
- [Ollama](https://ollama.com/) – Local LLM inference (external, not a pip package)
- [ExifTool](https://exiftool.org/) by Phil Harvey – Image metadata extraction (optional, bundled for Windows)

---

## License

See `LICENSE` for details. Bundled ExifTool and Strawberry Perl components are governed by their respective licenses in `Licenses_Strawberry_Perl.zip` and `windows_exiftool.txt`.
