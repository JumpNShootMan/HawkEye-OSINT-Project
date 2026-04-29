# 🦅 HawkEye – OSINT Media Integrity Analyzer

HawkEye is a desktop GUI tool for analyzing news articles and images for potential misinformation, clickbait, or misleading content. It fetches article metadata, reads local image EXIF data, and sends a structured prompt to a local LLM (via [Ollama](https://ollama.com)) to produce a verdict.

---

## Project Structure

```
HawkEye/
├── GUI/
│   └── main.py               # PySide6 application entry point
├── backend_bridge.py         # Core analysis logic (fetch, EXIF, LLM)
├── ui_hawkeye.py             # Auto-generated Qt UI bindings
├── hawkeye.ui                # Qt Designer UI layout file
├── POC.ipynb                 # Jupyter notebook proof-of-concept
├── hawkeye_result.json       # Last saved analysis result (auto-generated)
├── Session/                  # Auto-created at runtime
│   └── reverse_image_manifest.json
├── exiftool_files/           # Optional bundled ExifTool (Windows)
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

### 1. Clone or download the project

```bash
git clone https://github.com/JumpNShootMan/HawkEye-OSINT-Project.git
cd HawkEye
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
4. **Run Analysis** – Click *Run Analysis*. The backend fetches the article, builds an LLM prompt, calls Ollama, and displays:
   - **Verdict**: `likely_authentic` | `uncertain` | `likely_misleading_or_clickbait`
   - **Confidence** score (0–100%)
   - **Explanation** with per-field reasoning
   - **Sources** and **Timeline** tables
5. **Export JSON** – Save the full result to a `.json` file for later review.

---

## Configuration

All configuration is at the top of `backend_bridge.py`:

```python
OLLAMA_MODEL   = "llama3"                      # LLM model name
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"  # Ollama API endpoint
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: PySide6` | Run `pip install -r requirements.txt` inside your venv |
| `Ollama API call failed` | Make sure `ollama serve` is running and the model is pulled |
| `Could not fetch article URL` | Check internet connectivity; some sites block scrapers |
| EXIF metadata missing | Install ExifTool (see step 5) or place files in `exiftool_files/` |
| `Analysis failed` with no detail | Check the Logs tab in the GUI for the full error message |

---

## Dependencies

- [PySide6](https://doc.qt.io/qtforpython/) – Qt6 GUI bindings for Python
- [requests](https://requests.readthedocs.io/) – HTTP article fetching
- [Ollama](https://ollama.com/) – Local LLM inference (external, not a pip package)
- [ExifTool](https://exiftool.org/) by Phil Harvey – Image metadata extraction (optional, bundled for Windows)

---

## License

See `LICENSE` for details. Bundled ExifTool and Strawberry Perl components are governed by their respective licenses in `Licenses_Strawberry_Perl.zip` and `windows_exiftool.txt`.

