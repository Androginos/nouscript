#!/usr/bin/env python3
"""
NouScript backend test: /api/v1/summarize çağrısı.
.env'deki NOUSCRIPT_API_BASE ve RAPIDAPI_KEY kullanılır (veya komut satırı).
Kullanım: python test_web_backend.py [video_url]
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Proje kökünde .env yükle (opsiyonel)
root = Path(__file__).resolve().parent
env_path = root / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

def main():
    base = os.environ.get("NOUSCRIPT_API_BASE", "https://nouscript.com").rstrip("/")
    key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not key:
        print("Hata: RAPIDAPI_KEY .env'de tanımlı değil.")
        sys.exit(1)
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    endpoint = f"{base}/api/v1/summarize"
    payload = {"url": url, "mode": "summary", "lang": "English", "source_lang": "Auto"}
    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json", "x-rapidapi-key": key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.load(resp)
            summary = (out.get("summary") or "")[:500]
            print("OK status:", resp.status)
            print("Summary (ilk 500 karakter):", summary or "(yok)")
            if out.get("error"):
                print("Error alanı:", out.get("error"))
    except urllib.error.HTTPError as e:
        print("HTTP Hata:", e.code, e.reason)
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
            print("Cevap:", body)
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print("Hata:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
