#!/usr/bin/env python3
"""
Hermes skill: all steps via NouScript API (download, transcribe, summary/subtitle).
Usage: python3 call_nouscript.py "<video_url>" [summary|subtitle] [lang]
Reads NOUSCRIPT_API_BASE and RAPIDAPI_KEY from environment.
"""
import json
import os
import sys
import urllib.error
import urllib.request


def _post(base: str, key: str, path: str, body: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-rapidapi-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _post_err(e: urllib.error.HTTPError) -> dict:
    body = e.read().decode("utf-8", errors="replace")
    try:
        err = json.loads(body).get("error", body[:500])
    except Exception:
        err = body[:500] or str(e)
    return {"error": err, "status": e.code}


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: call_nouscript.py <video_url> summary|subtitle [lang]"}))
        sys.exit(1)
    url = sys.argv[1].strip()
    mode = sys.argv[2].strip().lower()
    if mode not in ("summary", "subtitle"):
        mode = "summary"
    lang = sys.argv[3].strip() if len(sys.argv) > 3 else "English"
    base = os.environ.get("NOUSCRIPT_API_BASE", "").rstrip("/")
    key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not base or not key:
        print(json.dumps({"error": "NOUSCRIPT_API_BASE and RAPIDAPI_KEY must be set in environment"}))
        sys.exit(1)

    if mode == "summary":
        # Step 1: API download + transcribe
        try:
            step1 = _post(base, key, "/api/v1/download_and_transcribe", {
                "url": url,
                "source_lang": "Auto",
            })
        except urllib.error.HTTPError as e:
            print(json.dumps(_post_err(e), ensure_ascii=False))
            sys.exit(1)
        if step1.get("error"):
            print(json.dumps({"error": step1.get("error", "download_and_transcribe failed")}, ensure_ascii=False))
            sys.exit(1)
        transcript = step1.get("transcript", "")
        meta = step1.get("meta") or {}
        # Step 2: API summary from transcript
        try:
            step2 = _post(base, key, "/api/v1/summarize_from_transcript", {
                "transcript": transcript,
                "lang": lang,
                "meta": meta,
            })
        except urllib.error.HTTPError as e:
            print(json.dumps(_post_err(e), ensure_ascii=False))
            sys.exit(1)
        if step2.get("error"):
            print(json.dumps({"error": step2.get("error", "summarize_from_transcript failed")}, ensure_ascii=False))
            sys.exit(1)
        out = {"status": "ok", "summary": step2.get("summary", ""), "transcript": transcript}
        print(json.dumps(out, ensure_ascii=False))
    else:
        # Subtitle: single API call (full pipeline on API)
        try:
            out = _post(base, key, "/api/v1/summarize", {
                "url": url,
                "mode": "subtitle",
                "lang": lang,
                "source_lang": "Auto",
            })
            print(json.dumps(out, ensure_ascii=False))
        except urllib.error.HTTPError as e:
            print(json.dumps(_post_err(e), ensure_ascii=False))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)


if __name__ == "__main__":
    main()
