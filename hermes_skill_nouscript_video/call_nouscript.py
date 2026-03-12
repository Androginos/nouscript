#!/usr/bin/env python3
"""
Hermes skill helper: call NouScript /api/v1/summarize and print JSON result.
Usage: python3 call_nouscript.py "<video_url>" [summary|subtitle]
Reads NOUSCRIPT_API_BASE and RAPIDAPI_KEY from environment.
"""
import json
import os
import sys
import urllib.error
import urllib.request

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: call_nouscript.py <video_url> summary|subtitle"}))
        sys.exit(1)
    url = sys.argv[1].strip()
    mode = sys.argv[2].strip().lower()
    if mode not in ("summary", "subtitle"):
        mode = "summary"
    base = os.environ.get("NOUSCRIPT_API_BASE", "").rstrip("/")
    key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not base or not key:
        print(json.dumps({"error": "NOUSCRIPT_API_BASE and RAPIDAPI_KEY must be set in environment"}))
        sys.exit(1)
    endpoint = f"{base}/api/v1/summarize"
    data = json.dumps({
        "url": url,
        "mode": mode,
        "lang": "English",
        "source_lang": "Auto",
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-rapidapi-key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            out = json.load(resp)
            print(json.dumps(out, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", body[:500])
        except Exception:
            err = body[:500] or str(e)
        print(json.dumps({"error": err, "status": e.code}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
