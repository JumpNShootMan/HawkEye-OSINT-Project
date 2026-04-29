"""
backend_bridge.py -- HawkEye OSINT Project
===========================================
Backend bridge between the PySide6 GUI and the analysis pipeline.

Responsibilities:
    - Resolve and validate the input URL (supports Reddit post -> linked article extraction)
    - Fetch article metadata and body text from direct news article URLs
    - Read local image EXIF/metadata via ExifTool (bundled or system-installed)
    - Build a structured, strict LLM prompt
    - Call a locally running Ollama instance (API first, CLI fallback)
    - Parse and validate the LLM JSON response
    - Persist results to Session/ and hawkeye_result.json

Supported Ollama models (recommended, in order of quality):
    - llama3.1:8b   -- default, good balance of speed and accuracy
    - mistral
    - llama3.1:70b  -- best quality, requires high VRAM

Important limits:
    - Image analysis is EXIF/metadata only. No visual content analysis is performed.
    - Reverse-image search is handled separately by reverse_image_search.py.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).resolve().parent
SESSION_DIR   = PROJECT_ROOT / "Session"
MANIFEST_JSON = SESSION_DIR / "reverse_image_manifest.json"
MANIFEST_CSV  = SESSION_DIR / "reverse_image_manifest.csv"
POC_NOTEBOOK  = PROJECT_ROOT / "POC.ipynb"
RESULT_JSON   = PROJECT_ROOT / "hawkeye_result.json"

# ---------------------------------------------------------------------------
# Ollama configuration
# Change OLLAMA_MODEL to switch models. Recommended: llama3.1:8b or mistral.
# ---------------------------------------------------------------------------

OLLAMA_MODEL   = "llama3.1:8b"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

# Domains that are not news articles -- excluded from article-quality scoring
NON_ARTICLE_DOMAINS = {
    "reddit.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "pinterest.com", "youtube.com", "tiktok.com", "linkedin.com", "tumblr.com",
}


# ===========================================================================
# Section 1: URL utilities
# ===========================================================================

def _resolve_url(url: str) -> str:
    """
    Resolve the best fetchable article URL from the given input.

    If the URL is a Reddit post, attempt to extract the linked external
    article URL from the Reddit JSON API. If extraction fails or the
    linked URL is also on Reddit, return the original URL unchanged.

    Args:
        url: Raw URL string entered by the user.

    Returns:
        A direct news article URL, or the original URL if resolution fails.
    """
    if not url:
        return url

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    # Not a Reddit URL -- return as-is
    if "reddit.com" not in domain:
        return url

    try:
        # Reddit's JSON API appends .json to any post URL
        json_url = url.rstrip("/") + ".json"
        headers  = {"User-Agent": "Mozilla/5.0 HawkEye-OSINT/1.0"}
        response = requests.get(json_url, headers=headers, timeout=15)
        response.raise_for_status()

        data       = response.json()
        post_data  = data[0]["data"]["children"][0]["data"]
        linked_url = post_data.get("url", "")

        # Only use the linked URL if it points to an external site
        if linked_url and "reddit.com" not in linked_url:
            return linked_url

    except Exception:
        # Resolution failed -- fall back to the original Reddit URL
        pass

    return url


def _is_reddit_url(url: str) -> bool:
    """Return True if the URL points to reddit.com."""
    return "reddit.com" in urlparse(url).netloc.lower()


# ===========================================================================
# Section 2: HTML parsing helpers
# ===========================================================================

def _clean_html_text(value: str) -> str:
    """Collapse whitespace and unescape HTML entities in a string."""
    value = re.sub(r"\s+", " ", value or "").strip()
    return unescape(value)


def _extract_attr(tag: str, attr: str) -> str:
    """Extract a single attribute value from an HTML tag string."""
    m = re.search(rf'{attr}\s*=\s*["\']([^"\']+)["\']', tag, flags=re.I)
    return _clean_html_text(m.group(1)) if m else ""


def _extract_meta(html: str, *, property_name: str = "", name: str = "") -> str:
    """
    Extract the content of a <meta> tag matching either a property or name attribute.

    Args:
        html:          Raw HTML string.
        property_name: Value of the property attribute to match (e.g. "og:title").
        name:          Value of the name attribute to match (e.g. "description").

    Returns:
        The content attribute value, or an empty string if not found.
    """
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.I):
        prop = _extract_attr(tag, "property").lower()
        nm   = _extract_attr(tag, "name").lower()
        if property_name and prop == property_name.lower():
            return _extract_attr(tag, "content")
        if name and nm == name.lower():
            return _extract_attr(tag, "content")
    return ""


def _extract_title(html: str) -> str:
    """
    Extract the article title from HTML.

    Preference order: og:title -> twitter:title -> <title> element.
    """
    og_title = _extract_meta(html, property_name="og:title")
    if og_title:
        return og_title

    twitter_title = _extract_meta(html, name="twitter:title")
    if twitter_title:
        return twitter_title

    m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return _clean_html_text(re.sub(r"<[^>]+>", "", m.group(1))) if m else "Untitled article"


def _extract_article_text(html: str, max_chars: int = 7000) -> str:
    """
    Extract readable article body text from raw HTML without external dependencies.

    Strategy:
        1. Strip script, style, and noscript blocks.
        2. Prefer text inside <article> tags if present.
        3. Collect <p> paragraphs of at least 35 characters.
        4. Fall back to stripping all tags from the full body if no paragraphs found.

    Args:
        html:      Raw HTML string.
        max_chars: Maximum number of characters to return.

    Returns:
        Plain text article body, truncated to max_chars.
    """
    # Remove non-content blocks
    cleaned = re.sub(r"<script\b.*?</script>",    " ", html,    flags=re.I | re.S)
    cleaned = re.sub(r"<style\b.*?</style>",       " ", cleaned, flags=re.I | re.S)
    cleaned = re.sub(r"<noscript\b.*?</noscript>", " ", cleaned, flags=re.I | re.S)

    # Prefer content inside <article> if available
    article_match = re.search(r"<article\b[^>]*>(.*?)</article>", cleaned, flags=re.I | re.S)
    search_area   = article_match.group(1) if article_match else cleaned

    # Collect substantial paragraphs
    paragraphs     = re.findall(r"<p\b[^>]*>(.*?)</p>", search_area, flags=re.I | re.S)
    paragraph_text = []
    for p in paragraphs:
        text = _clean_html_text(re.sub(r"<[^>]+>", " ", p))
        if len(text) >= 35:
            paragraph_text.append(text)

    article_text = "\n".join(paragraph_text)

    # Final fallback: strip all tags
    if not article_text:
        body         = re.sub(r"<[^>]+>", " ", cleaned)
        article_text = _clean_html_text(body)

    return article_text[:max_chars]


# ===========================================================================
# Section 3: Article fetching
# ===========================================================================

def _read_json(path: Path) -> Any:
    """Read and return the parsed contents of a JSON file."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_article_metadata(article_url: str) -> dict[str, Any]:
    """
    Fetch and parse metadata and body text from a news article URL.

    Extracts: title, description, og:image, canonical URL, domain, article text.

    Args:
        article_url: Direct URL to a news article page.

    Returns:
        Dictionary of article metadata fields.

    Raises:
        requests.HTTPError: If the HTTP request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 HawkEye-OSINT-Project/1.0",
        "Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    response = requests.get(article_url, headers=headers, timeout=25)
    response.raise_for_status()
    html = response.text

    title       = _extract_title(html)
    description = (
        _extract_meta(html, property_name="og:description")
        or _extract_meta(html, name="description")
        or _extract_meta(html, name="twitter:description")
    )
    image_url = (
        _extract_meta(html, property_name="og:image")
        or _extract_meta(html, name="twitter:image")
        or _extract_meta(html, property_name="twitter:image")
    )
    canonical_url = _extract_meta(html, property_name="og:url") or article_url
    domain        = urlparse(canonical_url).netloc or urlparse(article_url).netloc
    article_text  = _extract_article_text(html)

    return {
        "title":                   title,
        "source_url":              canonical_url,
        "article_url_input":       article_url,
        "source_domain":           domain,
        "image_url":               image_url,
        "description":             description,
        "article_text":            article_text,
        "article_text_char_count": len(article_text),
        "collection_method":       "direct_news_article_url",
    }


def _write_manifest(items: list[dict[str, Any]]) -> None:
    """Persist the article manifest list to Session/reverse_image_manifest.json."""
    SESSION_DIR.mkdir(exist_ok=True)
    with MANIFEST_JSON.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


# ===========================================================================
# Section 4: Image metadata (EXIF)
# ===========================================================================

def _image_size_from_header(path: Path) -> tuple[int | None, int | None]:
    """
    Read image dimensions from the binary header without requiring Pillow.

    Supports PNG (IHDR chunk) and JPEG (SOF markers).

    Returns:
        (width, height) in pixels, or (None, None) if parsing fails.
    """
    try:
        data = path.read_bytes()[:65536]

        # PNG: signature is 8 bytes; IHDR width/height at bytes 16-24
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")

        # JPEG: scan for SOF (Start of Frame) markers
        if data.startswith(b"\xff\xd8"):
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                i += 2
                if marker in (0xD8, 0xD9):
                    continue
                if i + 2 > len(data):
                    break
                length = int.from_bytes(data[i:i + 2], "big")
                if length < 2:
                    break
                # SOF markers that encode frame dimensions
                sof_markers = {
                    0xC0, 0xC1, 0xC2, 0xC3,
                    0xC5, 0xC6, 0xC7,
                    0xC9, 0xCA, 0xCB,
                    0xCD, 0xCE, 0xCF,
                }
                if marker in sof_markers:
                    if i + 7 <= len(data):
                        height = int.from_bytes(data[i + 3:i + 5], "big")
                        width  = int.from_bytes(data[i + 5:i + 7], "big")
                        return width, height
                    break
                i += length

    except Exception:
        pass

    return None, None


def _find_exiftool() -> list[str] | None:
    """
    Locate the ExifTool executable.

    Search order:
        1. System PATH (e.g. apt-installed exiftool)
        2. Bundled Windows package at exiftool_files/perl.exe + exiftool.pl

    Returns:
        A list forming the command prefix, e.g. ["exiftool"] or
        ["/path/perl.exe", "/path/exiftool.pl"], or None if not found.
    """
    exe = shutil.which("exiftool")
    if exe:
        return [exe]

    bundled_perl     = PROJECT_ROOT / "exiftool_files" / "perl.exe"
    bundled_exiftool = PROJECT_ROOT / "exiftool_files" / "exiftool.pl"
    if bundled_perl.exists() and bundled_exiftool.exists():
        return [str(bundled_perl), str(bundled_exiftool)]

    return None


def _read_image_metadata(image_path: str) -> dict[str, Any]:
    """
    Read file-level and EXIF metadata for a local image file.

    Collects: file name, extension, MIME type, size, SHA-256, dimensions,
    and selected EXIF fields (camera make/model, dates, GPS, copyright).

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        Dictionary of metadata fields. Always includes "provided" and "exists" keys.
    """
    path     = Path(image_path).expanduser()
    metadata: dict[str, Any] = {
        "provided": bool(image_path),
        "path":     image_path,
        "exists":   path.exists(),
    }

    if not image_path:
        return metadata
    if not path.exists():
        metadata["error"] = "Selected image path does not exist."
        return metadata
    if not path.is_file():
        metadata["error"] = "Selected image path is not a file."
        return metadata

    # Basic file metadata
    try:
        stat = path.stat()
        metadata.update({
            "file_name":           path.name,
            "extension":           path.suffix.lower(),
            "mime_guess":          mimetypes.guess_type(str(path))[0] or "unknown",
            "size_bytes":          stat.st_size,
            "modified_time_epoch": int(stat.st_mtime),
        })
        with path.open("rb") as f:
            metadata["sha256"] = hashlib.sha256(f.read()).hexdigest()

        width, height      = _image_size_from_header(path)
        metadata["width"]  = width
        metadata["height"] = height

    except Exception as exc:
        metadata["basic_metadata_error"] = str(exc)

    # EXIF metadata via ExifTool
    exif_cmd = _find_exiftool()
    if exif_cmd:
        try:
            completed = subprocess.run(
                [*exif_cmd, "-json", str(path)],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                parsed = json.loads(completed.stdout)
                if isinstance(parsed, list) and parsed:
                    raw       = parsed[0]
                    keep_keys = [
                        "FileType", "MIMEType", "ImageWidth", "ImageHeight",
                        "Make", "Model", "Software",
                        "CreateDate", "ModifyDate", "DateTimeOriginal",
                        "GPSLatitude", "GPSLongitude", "GPSPosition",
                        "Artist", "Copyright",
                    ]
                    metadata["exif_summary"] = {k: raw[k] for k in keep_keys if k in raw}
                else:
                    metadata["exif_summary"] = {}
            else:
                metadata["exif_error"] = completed.stderr.strip() or "ExifTool returned no output."

        except Exception as exc:
            metadata["exif_error"] = str(exc)
    else:
        metadata["exif_error"] = "ExifTool not found. Basic file metadata only."

    return metadata


# ===========================================================================
# Section 5: JSON utilities
# ===========================================================================

def _extract_json_from_output(raw_output: str) -> dict[str, Any] | None:
    """
    Parse a JSON object from the LLM's raw text output.

    Attempts direct JSON parsing first; if that fails, scans the string for
    the first '{' and tries to decode from that position forward.

    Args:
        raw_output: Raw string returned by the LLM.

    Returns:
        Parsed dictionary, or None if no valid JSON object was found.
    """
    if not raw_output:
        return None

    # Attempt 1: direct parse (model returned clean JSON)
    try:
        parsed = json.loads(raw_output)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Attempt 2: find the first '{' and decode from there
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw_output):
        if ch != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw_output[i:])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            continue

    return None


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    """
    Coerce a value to an integer clamped within [low, high].

    Returns default if the value cannot be converted to an integer.
    """
    try:
        number = int(value)
    except Exception:
        return default
    return max(low, min(high, number))


# ===========================================================================
# Section 6: LLM prompt builder
# ===========================================================================

def _build_gui_llm_prompt(
    item: dict[str, Any],
    claim_text: str = "",
    image_metadata: dict[str, Any] | None = None,
) -> str:
    """
    Build a strict, structured prompt for the Ollama LLM.

    The prompt enforces JSON-only output and provides explicit field
    definitions to reduce hallucination and non-committal verdicts.

    Args:
        item:           Article metadata dictionary from _fetch_article_metadata().
        claim_text:     Optional claim or image caption entered by the user.
        image_metadata: Optional image metadata dictionary from _read_image_metadata().

    Returns:
        A formatted prompt string ready to be sent to the LLM.
    """
    # Limit article text to 3000 characters to stay within model context windows
    article_text = (item.get("article_text") or "")[:3000]

    claim_section = (
        f"CLAIM TO VERIFY: {claim_text.strip()}"
        if claim_text.strip()
        else "CLAIM TO VERIFY: No claim provided. Evaluate the article on its own merits."
    )

    # Summarise image metadata for the prompt
    img_meta = image_metadata or {}
    if img_meta.get("exists"):
        exif        = img_meta.get("exif_summary", {})
        img_section = (
            "IMAGE METADATA:\n"
            f"  File      : {img_meta.get('file_name', 'unknown')}\n"
            f"  Size      : {img_meta.get('size_bytes', 'unknown')} bytes\n"
            f"  Dimensions: {img_meta.get('width')}x{img_meta.get('height')} px\n"
            f"  Camera    : {exif.get('Make', 'unknown')} {exif.get('Model', '')}\n"
            f"  Date taken: {exif.get('DateTimeOriginal', exif.get('CreateDate', 'unknown'))}\n"
            f"  GPS       : {exif.get('GPSPosition', 'none')}\n"
            f"  Software  : {exif.get('Software', 'unknown')}"
        )
    else:
        img_section = "IMAGE METADATA: No local image provided or image could not be read."

    return f"""You are a forensic fact-checking analyst for the HawkEye OSINT tool.
Your task is to evaluate whether the article below is authentic or potentially misleading.

STRICT RULES:
1. Return ONLY a valid JSON object. No explanation, no markdown, no extra text.
2. Base your verdict ONLY on the evidence provided below.
3. Do NOT invent facts. If evidence is insufficient, state that in the reason field.
4. verdict MUST be exactly one of: "likely_authentic", "uncertain", "likely_misleading_or_clickbait"
5. confidence MUST be a decisive integer (avoid 45-55 unless genuinely borderline).
6. reason MUST cite specific evidence from the article text (max 80 words).
7. If a claim is provided, explicitly state whether it is SUPPORTED, CONTRADICTED, or UNVERIFIABLE.

ARTICLE TITLE: {item.get('title', 'N/A')}
ARTICLE SOURCE: {item.get('source_domain', 'N/A')} ({item.get('source_url', 'N/A')})
ARTICLE DESCRIPTION: {item.get('description', 'N/A')}
ARTICLE TEXT:
{article_text}

{claim_section}

{img_section}

Return ONLY this JSON structure:
{{
  "verdict": "likely_authentic" | "uncertain" | "likely_misleading_or_clickbait",
  "confidence": <integer 0-100>,
  "integrity_risk_score": <integer 0-100, higher = more suspicious>,
  "reason": "<specific evidence from article, max 80 words>",
  "claim_caption_assessment": "<SUPPORTED | CONTRADICTED | UNVERIFIABLE -- with one sentence of reasoning>",
  "image_metadata_assessment": "<findings from image metadata, or 'No image provided'>",
  "caution_flags": ["<flag1>", "<flag2>"],
  "supporting_signals": ["<signal1>", "<signal2>"]
}}""".strip()


# ===========================================================================
# Section 7: Ollama API and CLI callers
# ===========================================================================

def _run_ollama_api(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 240) -> str:
    """
    Send the prompt to Ollama via its REST API and return the raw response text.

    The "format": "json" parameter instructs Ollama to enforce JSON output mode,
    which significantly reduces non-JSON responses from the model.

    Args:
        prompt:  The formatted LLM prompt string.
        model:   Ollama model name (default: OLLAMA_MODEL).
        timeout: Request timeout in seconds.

    Returns:
        Raw response string from the model.

    Raises:
        requests.HTTPError: If Ollama returns a non-2xx status.
    """
    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "format": "json",        # Enforce JSON output mode
        "options": {
            "temperature": 0.1,  # Low temperature = more deterministic, less hallucination
            "top_p":       0.9,
            "num_predict": 512,  # Sufficient tokens for the structured JSON response
        },
    }
    response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return str(data.get("response", ""))


def _run_ollama_cli(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 240) -> str:
    """
    Send the prompt to Ollama via the command-line interface as a fallback.

    Used when the REST API is unreachable (e.g. Ollama not started with `ollama serve`).

    Args:
        prompt:  The formatted LLM prompt string.
        model:   Ollama model name.
        timeout: Subprocess timeout in seconds.

    Returns:
        Raw response string from the model.

    Raises:
        RuntimeError: If `ollama` is not in PATH or the CLI returns an error.
    """
    cmd = shutil.which("ollama")
    if not cmd:
        raise RuntimeError(
            "Ollama was not found in PATH. "
            "Install Ollama from https://ollama.com and run `ollama serve`."
        )

    completed = subprocess.run(
        [cmd, "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Ollama CLI returned a non-zero exit code.")

    return completed.stdout


# ===========================================================================
# Section 8: LLM result handlers
# ===========================================================================

def _fallback_without_llm(
    item: dict[str, Any],
    claim_text: str,
    image_metadata: dict[str, Any],
    prompt: str,
    error: str,
) -> dict[str, Any]:
    """
    Build a structured fallback result when the LLM could not be reached.

    Verdict is forced to "uncertain" with 0% confidence so the GUI clearly
    communicates that no real analysis was performed.

    Args:
        item:           Article metadata dictionary.
        claim_text:     User-supplied claim or caption.
        image_metadata: Image metadata dictionary.
        prompt:         The prompt that was attempted.
        error:          Error message from the failed LLM call.

    Returns:
        A result dictionary compatible with the GUI display methods.
    """
    flags = [f"LLM unavailable -- ensure Ollama is running and '{OLLAMA_MODEL}' is pulled"]

    if claim_text.strip():
        flags.append("Claim/caption captured but not evaluated (LLM unavailable)")
    if image_metadata.get("provided"):
        if image_metadata.get("exists"):
            flags.append("Image metadata captured but not evaluated (LLM unavailable)")
        else:
            flags.append("Selected image path could not be read")

    return {
        "integrity_risk_score":      50,
        "verdict":                   "uncertain",
        "confidence":                0,
        "reason": (
            f"LLM analysis could not run. "
            f"Ensure Ollama is running (`ollama serve`) and the model '{OLLAMA_MODEL}' "
            f"is available (`ollama pull {OLLAMA_MODEL}`). Error: {error}"
        ),
        "claim_caption_assessment":  (
            "Captured but not evaluated -- LLM unavailable."
            if claim_text.strip()
            else "No claim/caption provided."
        ),
        "image_metadata_assessment": (
            "Basic metadata captured but not LLM-evaluated."
            if image_metadata.get("exists")
            else "No readable local image metadata."
        ),
        "caution_flags":             flags[:5],
        "supporting_signals":        [],
        "prompt_used":               prompt,
        "raw_llm_output":            "",
        "llm_error":                 error,
    }


def _run_llm_analysis(
    item: dict[str, Any],
    claim_text: str,
    image_metadata: dict[str, Any],
    logs: list[str],
) -> dict[str, Any]:
    """
    Build the LLM prompt, call Ollama, and return a validated result dictionary.

    Execution flow:
        1. Build prompt from article data, claim, and image metadata.
        2. Attempt Ollama REST API call.
        3. Fall back to Ollama CLI if the API call fails.
        4. Fall back to _fallback_without_llm() if both fail.
        5. Parse and validate the JSON response.

    Args:
        item:           Article metadata dictionary.
        claim_text:     User-supplied claim or caption.
        image_metadata: Image metadata dictionary.
        logs:           Mutable list to append progress log lines to.

    Returns:
        Validated result dictionary with all expected keys populated.
    """
    prompt = _build_gui_llm_prompt(item, claim_text, image_metadata)

    # Print the full prompt to the terminal for debugging purposes
    separator = "=" * 60
    print(f"\n{separator}", flush=True)
    print(f"HAWKEYE -- PROMPT SENT TO LLM (model: {OLLAMA_MODEL})", flush=True)
    print(separator, flush=True)
    print(prompt, flush=True)
    print(f"{separator}\n", flush=True)

    logs.append(f"Built LLM prompt (model: {OLLAMA_MODEL}).")

    # Attempt REST API call, then CLI fallback
    raw_output: str = ""
    try:
        raw_output = _run_ollama_api(prompt)
        logs.append("Ollama REST API call succeeded.")
    except Exception as api_exc:
        logs.append(f"Ollama REST API failed: {api_exc}")
        try:
            raw_output = _run_ollama_cli(prompt)
            logs.append("Ollama CLI fallback succeeded.")
        except Exception as cli_exc:
            logs.append(f"Ollama CLI fallback failed: {cli_exc}")
            return _fallback_without_llm(item, claim_text, image_metadata, prompt, str(cli_exc))

    # Parse LLM JSON response
    parsed = _extract_json_from_output(raw_output)
    if parsed is None:
        logs.append("LLM returned a response, but it could not be parsed as valid JSON.")
        return {
            "integrity_risk_score":      50,
            "verdict":                   "uncertain",
            "confidence":                25,
            "reason": (
                "The LLM response was received but could not be parsed as valid JSON. "
                "Try switching to a different model or review the raw output in the Raw Evidence tab."
            ),
            "claim_caption_assessment":  "Parse error -- could not evaluate.",
            "image_metadata_assessment": "Parse error -- could not evaluate.",
            "caution_flags":             ["JSON parse error -- raw output preserved in Raw Evidence tab"],
            "supporting_signals":        [],
            "prompt_used":               prompt,
            "raw_llm_output":            raw_output,
        }

    # Validate and normalise all response fields
    parsed["integrity_risk_score"] = _clamp_int(parsed.get("integrity_risk_score"), 0, 100, 50)
    parsed["confidence"]           = _clamp_int(parsed.get("confidence"),           0, 100, 50)

    verdict = str(parsed.get("verdict", "uncertain")).strip().lower()
    valid_verdicts = {"likely_authentic", "uncertain", "likely_misleading_or_clickbait"}
    if verdict not in valid_verdicts:
        verdict = "uncertain"
    parsed["verdict"] = verdict

    parsed.setdefault("reason",                    "LLM analysis completed.")
    parsed.setdefault("claim_caption_assessment",  "No claim/caption assessment returned.")
    parsed.setdefault("image_metadata_assessment", "No image metadata assessment returned.")

    if not isinstance(parsed.get("caution_flags"),      list):
        parsed["caution_flags"]      = []
    if not isinstance(parsed.get("supporting_signals"), list):
        parsed["supporting_signals"] = []

    parsed["prompt_used"]    = prompt
    parsed["raw_llm_output"] = raw_output

    logs.append(f"LLM verdict: {verdict} | Confidence: {parsed['confidence']}%")
    return parsed


# ===========================================================================
# Section 9: Main public entry point
# ===========================================================================

def run_analysis(
    reddit_url: str    = "",
    claim_text: str    = "",
    image_path: str    = "",
    run_notebook: bool = True,
) -> dict[str, Any]:
    """
    Execute the full HawkEye analysis pipeline and return a structured result.

    This is the single entry point called by the GUI (main.py).

    Parameter names are kept for GUI compatibility:
        - reddit_url   -- treated as any article URL; Reddit posts are resolved
                          to their linked external article automatically.
        - run_notebook -- enables the LLM prompt path; does not execute POC.ipynb.

    Pipeline:
        1. Resolve Reddit post URLs to linked article URLs.
        2. Fetch article metadata and body text.
        3. Fall back to cached manifest if fetch fails.
        4. Read local image EXIF metadata if an image was provided.
        5. Run LLM analysis via Ollama.
        6. Persist result to hawkeye_result.json.
        7. Return result dictionary for GUI display.

    Args:
        reddit_url:   Article URL (or Reddit post URL) entered by the user.
        claim_text:   Optional claim or caption to fact-check.
        image_path:   Optional path to a local image file.
        run_notebook: If True, run the LLM analysis step.

    Returns:
        Structured result dictionary compatible with all GUI display methods.
    """
    raw_input_url = (reddit_url or "").strip()
    claim_text    = (claim_text or "").strip()
    image_path    = (image_path or "").strip()
    logs: list[str]                = []
    manifest: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Step 1: Resolve URL -- extract linked article from Reddit posts
    # ------------------------------------------------------------------
    article_url = _resolve_url(raw_input_url)
    if article_url != raw_input_url:
        logs.append(f"Reddit URL resolved to linked article: {article_url}")
    elif _is_reddit_url(article_url):
        logs.append(
            "Warning: Could not extract an external article from this Reddit post. "
            "Results may be limited. Consider pasting the direct news article URL instead."
        )

    # ------------------------------------------------------------------
    # Step 2: Fetch article metadata and body text
    # ------------------------------------------------------------------
    fetch_succeeded = False
    if article_url:
        logs.append(f"Fetching article: {article_url}")
        try:
            item            = _fetch_article_metadata(article_url)
            manifest        = [item]
            fetch_succeeded = True
            _write_manifest(manifest)
            char_count = item.get("article_text_char_count", 0)
            logs.append(
                f"Article fetched. "
                f"Title: '{item.get('title', 'N/A')}' | "
                f"Text extracted: {char_count} characters."
            )
            if char_count < 200:
                logs.append(
                    "Warning: Very little article text was extracted. "
                    "The site may block scrapers or require JavaScript rendering. "
                    "LLM analysis quality may be reduced."
                )
        except Exception as exc:
            logs.append(f"Could not fetch article: {exc}")
            logs.append(
                "Fetch failed. Will NOT fall back to cached data to avoid "
                "analysing a stale article from a previous session. "
                "Please check the URL and try again."
            )

    # ------------------------------------------------------------------
    # Step 3: Load cached manifest ONLY when no URL was provided at all.
    #         If a URL was given but the fetch failed, do NOT use stale cache.
    # ------------------------------------------------------------------
    if not manifest and not article_url and MANIFEST_JSON.exists():
        # No URL entered by the user -- loading cache is intentional
        try:
            raw      = _read_json(MANIFEST_JSON)
            manifest = raw if isinstance(raw, list) else [raw]
            logs.append(
                f"No URL provided. Loaded {len(manifest)} cached item(s) "
                f"from Session/reverse_image_manifest.json."
            )
        except Exception as exc:
            logs.append(f"Could not read cached manifest: {exc}")
    elif not manifest and article_url and not fetch_succeeded:
        # URL was given but fetch failed -- refuse to use stale cache
        logs.append(
            "Analysis aborted: article could not be fetched and cached data "
            "will not be used to avoid misleading results. "
            "Fix the URL or check your internet connection and try again."
        )
    elif not manifest and not article_url:
        logs.append("No article URL provided and no cached manifest found in Session/.")

    # ------------------------------------------------------------------
    # Step 4: Read local image metadata
    # ------------------------------------------------------------------
    first          = manifest[0] if manifest else {}
    image_metadata = _read_image_metadata(image_path)

    if image_metadata.get("provided"):
        if image_metadata.get("exists"):
            logs.append(
                f"Image metadata read: {image_metadata.get('file_name')} "
                f"({image_metadata.get('width')}x{image_metadata.get('height')} px, "
                f"{image_metadata.get('size_bytes', 0):,} bytes)"
            )
        else:
            logs.append("Warning: Selected image path could not be read.")

    # ------------------------------------------------------------------
    # Step 5: LLM analysis
    # ------------------------------------------------------------------
    if manifest and run_notebook:
        llm_eval   = _run_llm_analysis(first, claim_text, image_metadata, logs)
        verdict    = str(llm_eval.get("verdict", "uncertain"))
        confidence = _clamp_int(llm_eval.get("confidence"), 0, 100, 0)
        explanation = (
            f"Title      : {first.get('title', 'N/A')}\n"
            f"Source     : {first.get('source_url', 'N/A')}\n"
            f"Model      : {OLLAMA_MODEL}\n\n"
            f"Verdict    : {verdict}\n"
            f"Confidence : {confidence}%\n"
            f"Risk score : {llm_eval.get('integrity_risk_score', 'N/A')}/100\n\n"
            f"Reason:\n{llm_eval.get('reason', 'N/A')}\n\n"
            f"Claim assessment:\n{llm_eval.get('claim_caption_assessment', 'N/A')}\n\n"
            f"Image metadata:\n{llm_eval.get('image_metadata_assessment', 'N/A')}"
        )

    elif manifest:
        # LLM step disabled
        llm_eval   = {}
        verdict    = "Article loaded (LLM disabled)"
        confidence = 0
        explanation = (
            f"Title  : {first.get('title', 'N/A')}\n"
            f"Source : {first.get('source_url', 'N/A')}\n\n"
            "LLM analysis was disabled. Set run_notebook=True to enable it."
        )

    else:
        # No article data available (fetch failed or no URL given)
        llm_eval   = {}
        verdict    = "No data"
        confidence = 0

        if article_url and not fetch_succeeded:
            explanation = (
                "The article could not be fetched and cached data was not used.\n\n"
                "Common causes:\n"
                "  - 403 Forbidden: the site blocks automated requests\n"
                "  - Reddit URL: the linked article site blocked the request\n"
                "  - Network error: check your internet connection\n\n"
                "Suggestions:\n"
                "  - Open the article in your browser and copy the final URL\n"
                "  - Try a different source covering the same story\n"
                "  - Check the Logs tab for the exact error"
            )
        else:
            explanation = (
                "No article data could be loaded.\n\n"
                "Tips:\n"
                "  - Paste a direct news article URL (e.g. https://bbc.com/news/...)\n"
                "  - Avoid Reddit URLs where possible -- use the linked article instead\n"
                "  - Check your internet connection"
            )

    # ------------------------------------------------------------------
    # Step 6: Assemble and persist result
    # ------------------------------------------------------------------
    result = {
        "inputs": {
            "raw_url_input":         raw_input_url,
            "resolved_article_url":  article_url,
            "claim_text_or_caption": claim_text,
            "image_path":            image_path,
            "ollama_model":          OLLAMA_MODEL,
            "run_llm_prompt_path":   run_notebook,
        },
        "verdict":        verdict,
        "confidence":     confidence,
        "explanation":    explanation,
        "llm_evaluation": llm_eval,
        "image_metadata": image_metadata,
        "manifest":       manifest,
        "logs":           logs,
        "files_checked": {
            "manifest_json": str(MANIFEST_JSON),
            "manifest_csv":  str(MANIFEST_CSV),
            "notebook":      str(POC_NOTEBOOK),
        },
    }

    try:
        with RESULT_JSON.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logs.append(f"Result saved to {RESULT_JSON}.")
    except Exception as exc:
        logs.append(f"Could not save result JSON: {exc}")

    return result
