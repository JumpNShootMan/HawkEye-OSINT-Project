"""
URL safety checker for HawkEye.
Queries URLhaus (malware DB) and crt.sh (Certificate Transparency).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


URLHAUS_API = "https://urlhaus-api.abuse.ch/v1/host/"
CRTSH_API = "https://crt.sh/"
USER_AGENT = "HawkEye-OSINT-Project/1.0"
URLHAUS_KEY_FILE = Path(__file__).parent / ".urlhaus_key"

URLHAUS_TIMEOUT = 60
CRTSH_TIMEOUT = 120
DEFAULT_TIMEOUT = 120

URLHAUS_RETRIES = 2
CRTSH_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5


def _to_naive_utc(dt):
    """Convert any datetime to naive UTC for safe comparison."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _registered_domain(host):
    """
    Strip subdomains down to registered domain for crt.sh queries.
    www.bbc.com -> bbc.com
    news.bbc.co.uk -> bbc.co.uk
    api.example.com -> example.com
    """
    if not host:
        return host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_part_tlds = {"co.uk", "com.au", "co.jp", "co.in", "co.za", "com.br", "co.nz"}
    last_two = ".".join(parts[-2:])
    if last_two in two_part_tlds and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _http_post_with_retries(url, timeout, headers=None, data=None, max_retries=2):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, headers=h, data=data, timeout=timeout)
            if resp.status_code == 200:
                return resp, None
            if 500 <= resp.status_code < 600:
                last_err = f"HTTP {resp.status_code}"
                if attempt < max_retries:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
            return None, last_err or f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            last_err = f"Timeout after {timeout}s"
        except requests.exceptions.ConnectionError as exc:
            last_err = f"Connection error: {exc}"
        except Exception as exc:
            last_err = f"Request failed: {exc}"
        if attempt < max_retries:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    return None, last_err


def _http_get_with_retries(url, timeout, headers=None, params=None, max_retries=2):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=h, params=params, timeout=timeout)
            if resp.status_code in (200, 404):
                return resp, None
            if 500 <= resp.status_code < 600:
                last_err = f"HTTP {resp.status_code}"
                if attempt < max_retries:
                    time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
            return None, last_err or f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            last_err = f"Timeout after {timeout}s"
        except requests.exceptions.ConnectionError as exc:
            last_err = f"Connection error: {exc}"
        except Exception as exc:
            last_err = f"Request failed: {exc}"
        if attempt < max_retries:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    return None, last_err


def _get_urlhaus_key():
    if not URLHAUS_KEY_FILE.exists():
        return None
    try:
        key = URLHAUS_KEY_FILE.read_text(encoding="utf-8").strip()
        return key if key else None
    except Exception:
        return None


def _query_urlhaus(host, timeout=URLHAUS_TIMEOUT):
    out = {
        "query_status": "error",
        "url_count": 0,
        "first_seen": None,
        "blacklisted_on": [],
        "threats": [],
        "error": None,
    }
    auth_key = _get_urlhaus_key()
    if not auth_key:
        out["query_status"] = "skipped"
        out["error"] = "No .urlhaus_key file found (get free key at https://auth.abuse.ch/)"
        return out

    resp, err = _http_post_with_retries(
        URLHAUS_API,
        timeout=timeout,
        headers={"Auth-Key": auth_key},
        data={"host": host},
        max_retries=URLHAUS_RETRIES,
    )
    if not resp:
        out["error"] = f"URLhaus request failed: {err}"
        return out

    try:
        data = resp.json()
    except Exception as exc:
        out["error"] = f"URLhaus returned non-JSON: {exc}"
        return out

    status = data.get("query_status", "error")
    out["query_status"] = status

    if status == "no_results":
        return out
    if status != "ok":
        out["error"] = f"URLhaus status: {status}"
        return out

    url_list = data.get("urls") or []
    out["url_count"] = len(url_list)
    if url_list:
        out["first_seen"] = url_list[0].get("date_added")

    blacklists = data.get("blacklists") or {}
    out["blacklisted_on"] = [k for k, v in blacklists.items() if v == "listed"]

    threats = []
    for item in url_list[:20]:
        threats.append({
            "url": item.get("url", ""),
            "threat": item.get("threat", ""),
            "status": item.get("url_status", ""),
        })
    out["threats"] = threats
    return out


def _query_crtsh(host, timeout=CRTSH_TIMEOUT):
    """
    Query crt.sh. Tries multiple query strategies because crt.sh is finicky.
    """
    out = {
        "available": False,
        "total_certs": 0,
        "first_cert_date": None,
        "approx_domain_age_days": None,
        "unique_subdomains": 0,
        "recent_cert_count_30d": 0,
        "subdomains_sample": [],
        "error": None,
    }

    domain_to_query = _registered_domain(host)
    queries_to_try = [
        domain_to_query,
        f"%.{domain_to_query}",
        host,
    ]

    data = None
    last_err = None
    for q in queries_to_try:
        params = {"q": q, "output": "json"}
        resp, err = _http_get_with_retries(
            CRTSH_API,
            timeout=timeout,
            params=params,
            max_retries=CRTSH_RETRIES,
        )
        if not resp:
            last_err = err
            continue

        if resp.status_code == 404:
            last_err = "HTTP 404 (no results for this query)"
            continue

        if not resp.text or not resp.text.strip():
            last_err = "Empty response"
            continue

        try:
            parsed = resp.json()
            if isinstance(parsed, list) and len(parsed) > 0:
                data = parsed
                break
            else:
                last_err = "No certificates returned"
        except Exception as exc:
            last_err = f"Non-JSON response: {exc}"
            continue

    if data is None:
        out["error"] = f"crt.sh returned no results: {last_err}"
        return out

    out["available"] = True
    out["total_certs"] = len(data)

    dates = []
    for cert in data:
        not_before = cert.get("not_before")
        if not_before:
            try:
                dt_str = not_before.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                dates.append(_to_naive_utc(dt))
            except Exception:
                pass

    if dates:
        earliest = min(dates)
        out["first_cert_date"] = earliest.isoformat()
        now = datetime.utcnow()
        out["approx_domain_age_days"] = max(0, (now - earliest).days)
        thirty_days_ago = now - timedelta(days=30)
        out["recent_cert_count_30d"] = sum(1 for d in dates if d >= thirty_days_ago)

    subdomains = set()
    for cert in data:
        name_value = cert.get("name_value", "")
        for name in name_value.splitlines():
            name = name.strip().lower()
            if name and "." in name:
                subdomains.add(name)
    out["unique_subdomains"] = len(subdomains)
    out["subdomains_sample"] = sorted(subdomains)[:20]
    return out


def _assess_risk(urlhaus, crtsh, host):
    reasons = []
    risk_level = "unknown"
    uh_status = urlhaus.get("query_status", "error")
    uh_count = urlhaus.get("url_count", 0)
    crtsh_available = crtsh.get("available", False)
    domain_age = crtsh.get("approx_domain_age_days")
    recent_certs = crtsh.get("recent_cert_count_30d", 0)

    # URLhaus signals
    if uh_status == "ok" and uh_count > 0:
        risk_level = "malicious"
        reasons.append(f"URLhaus reports {uh_count} malicious URL(s)")
        blacklists = urlhaus.get("blacklisted_on", [])
        if blacklists:
            reasons.append(f"Blacklisted on: {', '.join(blacklists[:5])}")
    elif uh_status == "no_results":
        reasons.append("URLhaus: no malware URLs on record")
    elif uh_status == "skipped":
        reasons.append("URLhaus skipped (no auth key)")
    elif uh_status == "error":
        reasons.append(f"URLhaus error: {urlhaus.get('error', 'unknown')}")

    # Established domain = trusted (older than 2 years)
    is_established = domain_age is not None and domain_age > 730

    # crt.sh signals
    if crtsh_available:
        if domain_age is not None:
            if domain_age < 30:
                if risk_level != "malicious":
                    risk_level = "suspicious"
                reasons.append(f"Domain age ~{domain_age} days (very young - red flag)")
            elif domain_age < 180:
                reasons.append(f"Domain age ~{domain_age} days (relatively new)")
            else:
                years = round(domain_age / 365, 1)
                reasons.append(f"Domain age ~{domain_age} days (~{years} years - established)")

        # Cert churn only matters for young domains. Big sites issue lots of certs.
        if recent_certs > 50 and not is_established:
            if risk_level != "malicious":
                risk_level = "suspicious"
            reasons.append(f"{recent_certs} SSL certs in last 30 days (high churn for young domain)")
        elif recent_certs > 0:
            reasons.append(f"{recent_certs} SSL cert(s) issued in last 30 days")

        reasons.append(f"{crtsh.get('total_certs', 0)} total SSL certificates in CT logs")
    else:
        reasons.append(f"crt.sh error: {crtsh.get('error', 'unknown')}")

    # Final verdict
    if risk_level == "malicious":
        verdict_hint = f"Host '{host}' flagged in URLhaus malware DB. High risk."
    elif risk_level == "suspicious":
        verdict_hint = f"Host '{host}' shows caution signals."
    elif uh_status == "no_results" and is_established:
        risk_level = "clean"
        verdict_hint = f"Host '{host}' looks clean (no malware, established domain)."
    elif uh_status == "no_results" and crtsh_available:
        risk_level = "clean"
        verdict_hint = f"Host '{host}' looks clean (no malware records)."
    else:
        verdict_hint = f"Host '{host}' status unclear."

    return {
        "risk_level": risk_level,
        "reasons": reasons,
        "verdict_hint": verdict_hint,
    }


def check_url_safety(url, timeout=None):
    if not url:
        return {
            "host": "",
            "urlhaus": {"query_status": "error", "error": "No URL provided"},
            "crtsh": {"available": False, "error": "No URL provided"},
            "summary": {"risk_level": "unknown", "reasons": ["No URL provided"], "verdict_hint": "No URL provided"},
        }

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host:
        return {
            "host": "",
            "urlhaus": {"query_status": "error", "error": "Could not parse hostname"},
            "crtsh": {"available": False, "error": "Could not parse hostname"},
            "summary": {"risk_level": "unknown", "reasons": ["Could not parse hostname"], "verdict_hint": "Invalid URL"},
        }

    print(f"[url_safety] Querying URLhaus for {host} (up to 60s)...")
    urlhaus = _query_urlhaus(host, timeout=URLHAUS_TIMEOUT)
    print(f"[url_safety] URLhaus done: {urlhaus.get('query_status')}")

    domain_for_ct = _registered_domain(host)
    print(f"[url_safety] Querying crt.sh for {domain_for_ct} (this can take 30-120s)...")
    crtsh = _query_crtsh(host, timeout=CRTSH_TIMEOUT)
    if crtsh.get("available"):
        print(f"[url_safety] crt.sh done: {crtsh.get('total_certs')} certs found")
    else:
        print(f"[url_safety] crt.sh failed: {crtsh.get('error')}")

    summary = _assess_risk(urlhaus, crtsh, host)

    return {
        "host": host,
        "urlhaus": urlhaus,
        "crtsh": crtsh,
        "summary": summary,
    }


def format_for_prompt(safety):
    summary = safety.get("summary", {}) or {}
    host = safety.get("host", "unknown")
    risk = summary.get("risk_level", "unknown")

    lines = [f"- Host: {host}", f"- Risk level: {risk}"]
    for reason in summary.get("reasons", []):
        lines.append(f"  - {reason}")
    if summary.get("verdict_hint"):
        lines.append(f"- Verdict: {summary['verdict_hint']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.bbc.com/news"
    result = check_url_safety(test_url)
    print(json.dumps(result, indent=2))