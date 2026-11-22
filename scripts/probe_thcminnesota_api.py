#!/usr/bin/env python3
"""Read-only THC Minnesota API probe. Save private raw responses as workflow artifacts only.

Never writes to the public catalog, never prints the bearer token.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://thcminnesota.com"
ENDPOINTS = (
    "/api/v1/products",
    "/api/v1/dispensaries",
    "/api/v1/brands",
    "/api/v1/pricing",
    "/api/v1/pricing/trends",
    "/api/v1/distribution",
)
OUTPUT = Path("collector/data/thcminnesota-review")


def main():
    token = os.environ.get("THCMINNESOTA_API_KEY", "").strip()
    if not token:
        raise SystemExit("THCMINNESOTA_API_KEY unavailable; no requests made")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary = {"checked_at": datetime.now(timezone.utc).isoformat(), "source": BASE, "results": []}
    failures = 0
    for endpoint in ENDPOINTS:
        params = {"limit": "10"} if endpoint != "/api/v1/pricing/trends" else {}
        url = BASE + endpoint + ("?" + urllib.parse.urlencode(params) if params else "")
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "MNtrees-API-Review/1.0",
        })
        info = {"endpoint": endpoint}
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError("Response exceeds 2 MB review safety limit")
                parsed = json.loads(raw)
                filename = endpoint.strip("/").replace("/", "_") + ".json"
                (OUTPUT / filename).write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n")
                info.update({"http_status": response.status, "file": filename,
                             "shape": type(parsed).__name__,
                             "top_level_keys": list(parsed)[:25] if isinstance(parsed, dict) else [],
                             "items": len(parsed) if isinstance(parsed, list) else None})
        except urllib.error.HTTPError as exc:
            failures += 1
            info.update({"http_status": exc.code, "error": "HTTP response error"})
        except (urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
            failures += 1
            info.update({"error": type(exc).__name__})
        summary["results"].append(info)
        print(endpoint, info.get("http_status", "error"), info.get("shape", info.get("error")))
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if failures:
        print(f"Review incomplete: {failures} of {len(ENDPOINTS)} endpoints failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
