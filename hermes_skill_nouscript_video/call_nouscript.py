#!/usr/bin/env python3
"""
Hermes skill: Hermes does download + transcribe (via local_download_transcribe.py),
then calls NouScript API only for summary or subtitle translation.
Falls back to API for download_and_transcribe if local step fails.
Usage: python3 call_nouscript.py "<video_url>" [summary|subtitle] [lang]
Reads NOUSCRIPT_API_BASE, RAPIDAPI_KEY, GROQ_API_KEY (for local transcribe) from environment.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

LOG_PREFIX = "[nouscript-skill]"


def _log(msg: str) -> None:
    print(f"{LOG_PREFIX} {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC {msg}", file=sys.stderr, flush=True)


def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _run_local_download_transcribe(url: str, source_lang: str = "Auto") -> dict | None:
    """Run local_download_transcribe.py; return { transcript, segments, meta } or None on failure."""
    script = os.path.join(_script_dir(), "local_download_transcribe.py")
    if not os.path.isfile(script):
        _log("Local script not found, will use API for download+transcribe")
        return None
    _log("Running local download+transcribe (stderr from child will appear above)")
    try:
        proc = subprocess.run(
            [sys.executable, script, url, source_lang],
            stdout=subprocess.PIPE,
            stderr=None,  # let child stderr through so logs are visible
            text=True,
            timeout=600,
            cwd=_script_dir(),
        )
        if proc.returncode != 0:
            _log(f"Local script exited with code {proc.returncode}, falling back to API")
            return None
        out = json.loads(proc.stdout.strip())
        if out.get("error") or not out.get("segments"):
            _log("Local script returned error or no segments, falling back to API")
            return None
        _log("Local download+transcribe OK, using API only for summary/subtitle")
        return out
    except subprocess.TimeoutExpired:
        _log("Local script timed out, falling back to API")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        _log(f"Local script output parse error: {e}, falling back to API")
        return None


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
    _log(f"Start mode={mode} lang={lang} url={url[:50]}...")
    base = os.environ.get("NOUSCRIPT_API_BASE", "").rstrip("/")
    key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not base or not key:
        _log("ERROR: NOUSCRIPT_API_BASE or RAPIDAPI_KEY missing")
        print(json.dumps({"error": "NOUSCRIPT_API_BASE and RAPIDAPI_KEY must be set in environment"}))
        sys.exit(1)

    # Step 1: Hermes does download + transcribe (local script), or fall back to API
    transcript = ""
    segments = []
    meta = {}
    local_ok = _run_local_download_transcribe(url, "Auto")
    if local_ok:
        transcript = local_ok.get("transcript", "")
        segments = local_ok.get("segments", [])
        meta = local_ok.get("meta", {})
    if not local_ok:
        _log("Calling API for download_and_transcribe")
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
        segments = step1.get("segments", [])
        meta = step1.get("meta") or {}
        _log("API download_and_transcribe OK")

    if not transcript:
        _log("ERROR: No transcript available")
        print(json.dumps({"error": "No transcript available"}))
        sys.exit(1)

    if mode == "summary":
        _log("Calling API summarize_from_transcript")
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
            _log(f"ERROR: summarize_from_transcript: {step2.get('error')}")
            print(json.dumps({"error": step2.get("error", "summarize_from_transcript failed")}, ensure_ascii=False))
            sys.exit(1)
        _log("Summary OK")
        out = {"status": "ok", "summary": step2.get("summary", ""), "transcript": transcript}
        print(json.dumps(out, ensure_ascii=False))
    else:
        _log("Calling API subtitle_from_transcript")
        try:
            step2 = _post(base, key, "/api/v1/subtitle_from_transcript", {
                "segments": segments,
                "lang": lang,
            })
        except urllib.error.HTTPError as e:
            print(json.dumps(_post_err(e), ensure_ascii=False))
            sys.exit(1)
        if step2.get("error"):
            _log(f"ERROR: subtitle_from_transcript: {step2.get('error')}")
            print(json.dumps({"error": step2.get("error", "subtitle_from_transcript failed")}, ensure_ascii=False))
            sys.exit(1)
        _log("Subtitle OK")
        out = {"status": "ok", "srt": step2.get("srt", ""), "subtitle": step2.get("srt", ""), "transcript": transcript}
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
