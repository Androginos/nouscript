#!/usr/bin/env python3
"""Invidious bağlantısını test et. Sunucuda: cd /opt/nouscript && python test_invidious.py"""
import os
from dotenv import load_dotenv

load_dotenv()

def _invidious_urls():
    raw = os.getenv("INVIDIOUS_URL", "http://localhost:3000")
    return [u.strip() for u in raw.split(",") if u.strip()]

TEST_VIDEO_ID = "c8LYnW2kGZg"

def main():
    urls = _invidious_urls()
    print(f"Invidious URL'ler: {urls}")
    print(f"Test video: {TEST_VIDEO_ID}")
    print("-" * 50)

    try:
        import httpx
        for base in urls:
            base = base.rstrip("/")
            url = f"{base}/api/v1/videos/{TEST_VIDEO_ID}"
            print(f"\nİstek: {url}")
            try:
                with httpx.Client(timeout=15.0) as client:
                    r = client.get(url)
                print(f"Durum: {r.status_code}")
                data = r.json()
                if "error" in data:
                    print(f"HATA: {data['error'][:150]}...")
                    continue
                if data.get("title"):
                    print(f"Başarılı! Video: {data['title'][:60]}...")
                    return 0
            except Exception as e:
                print(f"HATA: {e}")
        print("\nHiçbir instance çalışmıyor.")
        return 1
    except ImportError:
        print("HATA: pip install httpx")
        return 1

if __name__ == "__main__":
    exit(main())
