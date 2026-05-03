
from __future__ import annotations

import re
import time
from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import quote

import requests


# Config


WAYBACK_CDX_URL = "http://web.archive.org/cdx/search/cdx"
WAYBACK_SNAPSHOT_FMT = "https://web.archive.org/web/{ts}/{url}"
ARCHIVE_TODAY_TIMEMAP = "https://archive.ph/timemap/{url}"

USER_AGENT = "HawkEye-OSINT-Project/1.0 (+archive history check)"
SNAPSHOT_SAMPLE_LIMIT = 50

# Default timeout. Wayback CDX is reliable but extremely slow on busy URLs.
# 90 seconds gives it real time to respond.
DEFAULT_TIMEOUT = 90

# Retry policy for transient errors (timeouts, connection drops, 5xx).
RETRY_COUNT = 2
RETRY_BACKOFF_SECONDS = 3



# HTTP helpers with retries

def _http_get_with_retries(
    url: str,
    timeout: int,
    headers: dict | None = None,
    params: dict | None = None,
) -> tuple[requests.Response | None, str | None]:
    """
    GET `url` with retries on connection errors, timeouts, and 5xx responses.
    Returns (Response | None, error_message | None).
    """
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)

    last_err: str | None = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            resp = requests.get(url, headers=h, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp, None
            # Retry on 5xx; treat 4xx as terminal
            if 500 <= resp.status_code < 600:
                last_err = f"HTTP {resp.status_code}"
                if attempt < RETRY_COUNT:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                return None, last_err
            return None, f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout as exc:
            last_err = f"Timeout after {timeout}s: {exc}"
        except requests.exceptions.ConnectionError as exc:
            last_err = f"Connection error: {exc}"
        except Exception as exc:
            last_err = f"Request failed: {exc}"

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
        else:
            return None, last_err

    return None, last_err


def _safe_get(url: str, timeout: int, headers: dict | None = None) -> requests.Response | None:
    """Single-shot GET that returns Response on 200 or None otherwise."""
    resp, _ = _http_get_with_retries(url, timeout, headers=headers)
    return resp


# Wayback Machine

def _parse_wayback_timestamp(ts: str) -> str:
    """Wayback timestamps look like YYYYMMDDhhmmss. Return ISO string."""
    if not ts or len(ts) < 8:
        return ts or ""
    try:
        if len(ts) >= 14:
            dt = datetime.strptime(ts[:14], "%Y%m%d%H%M%S")
        else:
            dt = datetime.strptime(ts[:8], "%Y%m%d")
        return dt.isoformat()
    except Exception:
        return ts


def _query_wayback_cdx(url: str, timeout: int) -> dict[str, Any]:
    out: dict[str, Any] = {
        "available": False,
        "snapshot_count": 0,
        "earliest": None,
        "latest": None,
        "snapshots": [],
        "error": None,
    }

    cdx_url = (
        f"{WAYBACK_CDX_URL}?url={quote(url, safe='')}"
        "&output=json&limit=10000&filter=statuscode:200&collapse=digest"
    )

    resp, err = _http_get_with_retries(cdx_url, timeout=timeout)
    if not resp:
        out["error"] = f"Wayback CDX request failed: {err}"
        return out

    try:
        data = resp.json()
    except Exception as exc:
        out["error"] = f"Wayback CDX returned non-JSON: {exc}"
        return out

    if not isinstance(data, list) or len(data) < 2:
        return out

    rows = data[1:]
    snapshots: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 3:
            continue
        ts = str(row[1])
        original = str(row[2])
        snapshots.append({
            "timestamp": ts,
            "datetime": _parse_wayback_timestamp(ts),
            "snapshot_url": WAYBACK_SNAPSHOT_FMT.format(ts=ts, url=original),
        })

    snapshots.sort(key=lambda s: s["timestamp"])
    out["snapshot_count"] = len(snapshots)
    out["available"] = len(snapshots) > 0
    if snapshots:
        out["earliest"] = snapshots[0]
        out["latest"] = snapshots[-1]

    # Down-sample if too many
    if len(snapshots) > SNAPSHOT_SAMPLE_LIMIT:
        idxs = sorted({0, len(snapshots) - 1} | {
            int(i * (len(snapshots) - 1) / (SNAPSHOT_SAMPLE_LIMIT - 1))
            for i in range(SNAPSHOT_SAMPLE_LIMIT)
        })
        out["snapshots"] = [snapshots[i] for i in idxs]
    else:
        out["snapshots"] = snapshots
    return out


# archive.today

def _query_archive_today_timemap(url: str, timeout: int) -> dict[str, Any]:
    out: dict[str, Any] = {
        "available": False,
        "snapshot_count": 0,
        "earliest": None,
        "latest": None,
        "snapshots": [],
        "error": None,
    }

    timemap_url = ARCHIVE_TODAY_TIMEMAP.format(url=url)
    resp, err = _http_get_with_retries(
        timemap_url,
        timeout=timeout,
        headers={"Accept": "application/link-format"},
    )
    if not resp:
        out["error"] = f"archive.today request failed: {err}"
        return out

    body = resp.text

    # RFC 7089 link-format
    snapshots: list[dict[str, Any]] = []
    for entry in re.split(r",\s*\n", body):
        if "memento" not in entry:
            continue
        m_url = re.search(r"<([^>]+)>", entry)
        m_dt = re.search(r'datetime="([^"]+)"', entry)
        if not m_url:
            continue
        snapshot_url = m_url.group(1)
        dt_str = m_dt.group(1) if m_dt else ""
        iso_dt = ""
        if dt_str:
            try:
                iso_dt = datetime.strptime(dt_str, "%a, %d %b %Y %H:%M:%S GMT").isoformat()
            except Exception:
                iso_dt = dt_str
        snapshots.append({
            "timestamp": iso_dt,
            "datetime": iso_dt,
            "snapshot_url": snapshot_url,
        })

    snapshots.sort(key=lambda s: s["datetime"])
    out["snapshot_count"] = len(snapshots)
    out["available"] = len(snapshots) > 0
    if snapshots:
        out["earliest"] = snapshots[0]
        out["latest"] = snapshots[-1]
    out["snapshots"] = snapshots[:SNAPSHOT_SAMPLE_LIMIT]
    return out


# Title-only stealth-edit detection

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _fetch_snapshot_title(snapshot_url: str, timeout: int) -> str:
    """Fetch a Wayback snapshot and return just its <title> text."""
    r = _safe_get(snapshot_url, timeout)
    if not r:
        return ""
    m = _TITLE_RE.search(r.text)
    if not m:
        return ""
    title = re.sub(r"<[^>]+>", "", m.group(1))
    title = re.sub(r"\s+", " ", title).strip()
    return unescape(title)


# Summary builder

def _summarize(
    wayback: dict[str, Any],
    archive_today: dict[str, Any],
    titles: dict[str, str],
) -> dict[str, Any]:
    total = (wayback.get("snapshot_count") or 0) + (archive_today.get("snapshot_count") or 0)

    candidates_earliest = [
        wayback["earliest"]["datetime"] if wayback.get("earliest") else None,
        archive_today["earliest"]["datetime"] if archive_today.get("earliest") else None,
    ]
    candidates_latest = [
        wayback["latest"]["datetime"] if wayback.get("latest") else None,
        archive_today["latest"]["datetime"] if archive_today.get("latest") else None,
    ]
    valid_earliest = [c for c in candidates_earliest if c]
    valid_latest = [c for c in candidates_latest if c]
    earliest_dt = min(valid_earliest) if valid_earliest else None
    latest_dt = max(valid_latest) if valid_latest else None

    title_first = titles.get("first") or None
    title_last = titles.get("last") or None
    title_changed = bool(title_first and title_last and title_first != title_last)

    stealth_warning = None
    if title_changed:
        stealth_warning = (
            "Article title differs between earliest and latest archived snapshots. "
            "Possible stealth edit after publication."
        )

    lifespan_days = None
    if earliest_dt and latest_dt:
        try:
            d_first = datetime.fromisoformat(earliest_dt.replace("Z", ""))
            d_last = datetime.fromisoformat(latest_dt.replace("Z", ""))
            lifespan_days = max(0, (d_last - d_first).days)
        except Exception:
            lifespan_days = None

    if total == 0:
        verdict_hint = (
            "No archived snapshots found. URL may be very new, paywalled, or already removed."
        )
    elif total < 3:
        verdict_hint = f"Only {total} snapshot(s) found across both archives. Limited history."
    else:
        first_seen = earliest_dt[:10] if earliest_dt else "unknown"
        last_seen = latest_dt[:10] if latest_dt else "unknown"
        verdict_hint = f"{total} snapshots between {first_seen} and {last_seen}."
        if title_changed:
            verdict_hint += " Title was edited after first archive."

    return {
        "total_snapshots": total,
        "first_seen": earliest_dt[:10] if earliest_dt else None,
        "last_seen": latest_dt[:10] if latest_dt else None,
        "title_first_seen": title_first,
        "title_last_seen": title_last,
        "title_changed": title_changed,
        "stealth_edit_warning": stealth_warning,
        "lifespan_days": lifespan_days,
        "verdict_hint": verdict_hint,
    }


# Public API

def fetch_archive_history(url: str, deep: bool = True, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Look up archived snapshots for `url` on Wayback Machine and archive.today.

    Args:
        url: Article URL to look up.
        deep: When True and Wayback has 2+ snapshots, also fetches the HTML of
              earliest and latest snapshots to detect title changes.
        timeout: Per-request timeout in seconds. Default 90.

    Returns dict with keys: url, wayback, archive_today, summary.
    """
    if not url:
        empty = {"available": False, "snapshot_count": 0, "earliest": None,
                 "latest": None, "snapshots": [], "error": "No URL provided"}
        return {
            "url": "",
            "wayback": dict(empty),
            "archive_today": dict(empty),
            "summary": {
                "total_snapshots": 0,
                "first_seen": None,
                "last_seen": None,
                "title_first_seen": None,
                "title_last_seen": None,
                "title_changed": False,
                "stealth_edit_warning": None,
                "lifespan_days": None,
                "verdict_hint": "No URL provided.",
            },
        }

    wayback = _query_wayback_cdx(url, timeout)
    archive_today = _query_archive_today_timemap(url, timeout)

    titles: dict[str, str] = {}
    if deep and wayback.get("snapshot_count", 0) >= 2:
        try:
            first_url = wayback["earliest"]["snapshot_url"]
            last_url = wayback["latest"]["snapshot_url"]
            titles["first"] = _fetch_snapshot_title(first_url, timeout)
            titles["last"] = _fetch_snapshot_title(last_url, timeout)
        except Exception:
            titles = {}

    summary = _summarize(wayback, archive_today, titles)

    return {
        "url": url,
        "wayback": wayback,
        "archive_today": archive_today,
        "summary": summary,
    }


def format_for_prompt(history: dict[str, Any]) -> str:
    """Return compact text block for injection into LLM prompt."""
    s = history.get("summary", {}) or {}
    wb = history.get("wayback", {}) or {}
    at = history.get("archive_today", {}) or {}

    lines = [
        f"- Total archived snapshots: {s.get('total_snapshots', 0)}",
        f"  - Wayback Machine: {wb.get('snapshot_count', 0)}",
        f"  - archive.today:   {at.get('snapshot_count', 0)}",
    ]
    if s.get("first_seen"):
        lines.append(f"- First archived: {s['first_seen']}")
    if s.get("last_seen"):
        lines.append(f"- Last archived:  {s['last_seen']}")
    if s.get("lifespan_days") is not None:
        lines.append(f"- Lifespan in archives: {s['lifespan_days']} days")
    if s.get("title_first_seen"):
        lines.append(f"- Earliest snapshot title: {s['title_first_seen'][:160]}")
    if s.get("title_last_seen"):
        lines.append(f"- Latest snapshot title:   {s['title_last_seen'][:160]}")
    if s.get("title_changed"):
        lines.append(
            "- WARNING: Title differs between earliest and latest snapshots "
            "(possible stealth edit)."
        )
    if s.get("total_snapshots", 0) == 0:
        lines.append(
            "- WARNING: No archived snapshots found. "
            "URL may be very new or already removed."
        )
    if wb.get("error"):
        lines.append(f"- Wayback error: {wb['error']}")
    if at.get("error"):
        lines.append(f"- archive.today error: {at['error']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json as _json
    import sys

    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.bbc.com/news"
    result = fetch_archive_history(test_url, deep=True, timeout=DEFAULT_TIMEOUT)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
    print("\n--- prompt block ---")
    print(format_for_prompt(result))