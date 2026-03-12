#!/usr/bin/env python3
"""
Invidious full test: API + audio format + stream download.
On server: cd /opt/nouscript && python test_invidious.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def _invidious_urls():
    raw = os.getenv("INVIDIOUS_URL", "http://localhost:3000")
    return [u.strip() for u in raw.split(",") if u.strip()]

TEST_VIDEO_ID = "c8LYnW2kGZg"

def main():
    try:
        import httpx
    except ImportError:
        print("ERROR: pip install httpx")
        return 1

    urls = _invidious_urls()
    print(f"Invidious URL'ler: {urls}")
    print(f"Test video: {TEST_VIDEO_ID}")
    print("=" * 60)

    for base in urls:
        base = base.rstrip("/")
        print(f"\n>>> {base}")
        print("-" * 40)

        # 1. API isteği
        api_url = f"{base}/api/v1/videos/{TEST_VIDEO_ID}"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(api_url)
        except Exception as e:
            print(f"  [1] API connection error: {e}")
            continue

        print(f"  [1] API status: {r.status_code}")

        if r.status_code != 200:
            print(f"  [1] Yanıt: {r.text[:200]}...")
            continue

        try:
            data = r.json()
        except Exception as e:
            print(f"  [1] JSON parse error: {e}")
            continue

        if data.get("error"):
            print(f"  [1] API error: {data['error'][:150]}")
            continue

        title = data.get("title", "?")
        print(f"  [1] OK - Video: {title[:50]}...")

        # 2. Audio format present?
        formats = data.get("adaptiveFormats") or data.get("formatStreams") or []
        audio_formats = [
            f for f in formats
            if isinstance(f, dict) and (f.get("type") or "").startswith("audio/")
        ]
        if not audio_formats:
            print(f"  [2] ERROR: No audio format (total {len(formats)} formats)")
            continue

        def _bitrate_val(f):
            try:
                b = f.get("bitrate") or 0
                return int(b) if b else 0
            except (ValueError, TypeError):
                return 0
        best = max(audio_formats, key=_bitrate_val)
        audio_url = best.get("url")
        if not audio_url:
            print(f"  [2] HATA: Ses formatında URL yok")
            continue

        if not audio_url.startswith(("http://", "https://")):
            audio_url = base + "/" + audio_url.lstrip("/")

        print(f"  [2] OK - Audio format found (bitrate: {best.get('bitrate')})")

        # 3. Ses stream indir
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                r2 = client.get(audio_url)
        except Exception as e:
            print(f"  [3] Stream download error: {e}")
            continue

        if r2.status_code != 200:
            print(f"  [3] ERROR: Stream status {r2.status_code}")
            continue

        size = len(r2.content)
        print(f"  [3] OK - {size:,} bytes downloaded")

        print(f"\n  *** {base} FULLY WORKING ***")
        return 0

    print("\n*** No instance fully working ***")
    return 1

if __name__ == "__main__":
    sys.exit(main())
