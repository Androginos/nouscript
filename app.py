import asyncio
import gc
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
from contextlib import asynccontextmanager

import time
import urllib.request
import urllib.parse

import struct
import tempfile

import httpx
import numpy as np
from dotenv import load_dotenv

load_dotenv()

import whisper
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

RATE_LIMIT_MAX = 10
RATE_LIMIT_MAX_UNVERIFIED = 5
RATE_LIMIT_MAX_RAPIDAPI = 100  # per RapidAPI key
RATE_LIMIT_WINDOW = 86400  # 24 hours (1 day)
rate_limit_store: dict[str, list[float]] = {}  # ip/key -> [timestamps]

CHUNK_DURATION = 300
SAMPLE_RATE = 16000
WHISPER_MODEL_SIZE = "small"

LANG_CODE_MAP = {
    "Auto": None,
    "English": "en", "Turkish": "tr", "Spanish": "es", "French": "fr",
    "German": "de", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja",
    "Korean": "ko", "Chinese": "zh", "Arabic": "ar", "Hindi": "hi",
    "Italian": "it", "Dutch": "nl",
}
TRANSLATION_BATCH_SIZE = 20

NOUS_REASONING_PREAMBLE = (
    "You are a deep thinking AI, you may use extremely long "
    "chains of thought to deeply consider the problem and "
    "deliberate with yourself via systematic reasoning processes "
    "to help come to a correct solution prior to answering. "
    "You should enclose your thoughts and internal monologue "
    "inside <think> </think> tags, and then provide your "
    "solution or response to the problem."
)

whisper_model = None
CONCURRENT_WORKERS = 5   # fewer concurrent jobs = less Groq 429, faster when Groq is used
processing_queue: asyncio.Queue = asyncio.Queue(maxsize=20)  # 10 in progress + up to 20 waiting

FFMPEG: str = ""
FFPROBE: str = ""


def _build_search_path() -> str:
    default_path = "/usr/local/bin:/usr/bin:/bin" if sys.platform != "win32" else ""
    paths: set[str] = set(os.environ.get("PATH", default_path).split(os.pathsep))
    if sys.platform == "win32":
        paths.add(os.path.join(os.path.dirname(sys.executable), "Scripts"))
        paths.add(os.path.join(sys.prefix, "Scripts"))
        paths.add(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"))
        try:
            import winreg
            for root, sub in [
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                (winreg.HKEY_CURRENT_USER, r"Environment"),
            ]:
                with winreg.OpenKey(root, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "Path")
                    paths.update(val.split(os.pathsep))
        except Exception:
            pass
    return os.pathsep.join(p for p in paths if p)


def _find_binary(name: str) -> str:
    result = shutil.which(name, path=_build_search_path())
    if result:
        return result
    raise FileNotFoundError(f"'{name}' not found. Please install it and add to PATH.")


def _resolve_tools():
    global FFMPEG, FFPROBE
    FFMPEG = _find_binary("ffmpeg")
    FFPROBE = _find_binary("ffprobe")
    print(f"[OK] ffmpeg  : {FFMPEG}")
    print(f"[OK] ffprobe : {FFPROBE}")
    hosts = _rapidapi_hosts()
    if os.getenv("RAPIDAPI_KEY") and hosts:
        names = [h.split(".")[0] for h in hosts[:3]]
        print(f"[OK] RapidAPI : {len(hosts)} host ({', '.join(names)}{'...' if len(hosts) > 3 else ''})")
    else:
        print("[WARN] RapidAPI : RAPIDAPI_KEY and RAPIDAPI_HOSTS required")



def strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def verify_turnstile(token: str) -> bool | None:
    """Returns True (passed), False (failed), None (skipped/unavailable)."""
    secret = os.getenv("TURNSTILE_SECRET_KEY", "")
    if not secret or not token:
        return None
    data = urllib.parse.urlencode({
        "secret": secret,
        "response": token,
    }).encode()
    try:
        req = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            return result.get("success", False)
    except Exception:
        return False


def _get_remaining(ip: str, limit: int = RATE_LIMIT_MAX) -> int:
    now = time.time()
    timestamps = rate_limit_store.get(ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    rate_limit_store[ip] = timestamps
    return max(0, limit - len(timestamps))


def _consume_request(ip: str, limit: int = RATE_LIMIT_MAX) -> bool:
    now = time.time()
    timestamps = rate_limit_store.get(ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= limit:
        rate_limit_store[ip] = timestamps
        return False
    timestamps.append(now)
    rate_limit_store[ip] = timestamps
    return True


def _is_rapidapi_request(request: Request) -> bool:
    """Whether request is RapidAPI (x-rapidapi-key header + optional proxy secret)."""
    key = request.headers.get("x-rapidapi-key", "").strip()
    if not key:
        return False
    secret = os.getenv("RAPIDAPI_PROXY_SECRET", "").strip()
    if secret:
        return request.headers.get("x-rapidapi-proxy-secret", "") == secret
    return True


def _get_rate_limit_key(request: Request) -> tuple[str, int]:
    """Returns (rate_limit_key, limit). Uses API key for RapidAPI, IP otherwise."""
    if _is_rapidapi_request(request):
        key = request.headers.get("x-rapidapi-key", "").strip()
        return f"rapidapi:{key}", RATE_LIMIT_MAX_RAPIDAPI
    return request.client.host, RATE_LIMIT_MAX


def _nous_client() -> OpenAI:
    return OpenAI(
        base_url="https://inference-api.nousresearch.com/v1",
        api_key=os.getenv("NOUS_API_KEY", ""),
    )


# -- Audio (in-memory) -------------------------------------------------------

def _invidious_urls() -> list[str]:
    """INVIDIOUS_URL'den URL listesi döner. Virgülle ayrılmış birden fazla olabilir."""
    raw = os.getenv("INVIDIOUS_URL", "http://localhost:3000")
    return [u.strip() for u in raw.split(",") if u.strip()]


INVIDIOUS_BASE = os.getenv("INVIDIOUS_URL", "http://localhost:3000")  # ilk URL (geriye uyumluluk)


def _get_cookies_path() -> str | None:
    """cookies.txt veya COOKIES_FILE yolunu döndür."""
    p = os.getenv("COOKIES_FILE", "").strip()
    if p and os.path.isfile(p):
        return p
    for base in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        p = os.path.join(base, "cookies.txt")
        if os.path.isfile(p):
            return p
    return None


def _download_audio_via_ytdlp_subprocess(
    url: str, cookies_path: str | None, platform: str
) -> tuple[io.BytesIO, float, dict] | None:
    """Download audio via yt-dlp CLI (fallback when Python API fails)."""
    import shutil as _shutil
    ytdlp_cmd = _shutil.which("yt-dlp") or _shutil.which("yt_dlp")
    if not ytdlp_cmd:
        ytdlp_cmd = sys.executable
        ytdlp_args = ["-m", "yt_dlp"]
    else:
        ytdlp_args = []
    out_dir = tempfile.mkdtemp()
    out_tpl = os.path.join(out_dir, "audio.%(ext)s")
    cmd = [ytdlp_cmd] + ytdlp_args + [
        "-x", "-f", "worst",
        "-o", out_tpl,
        "--no-playlist", "--quiet", "--no-warnings",
        "--audio-format", "opus", "--audio-quality", "0",
    ]
    if cookies_path:
        cmd.extend(["--cookies", cookies_path])
    if platform == "youtube":
        cmd.extend(["--extractor-args", "youtube:player_client=mweb,android,web"])
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            print(f"[yt-dlp subprocess] exit={proc.returncode} stderr: {proc.stderr[:400]}")
            return None
        files = [f for f in os.listdir(out_dir) if f.endswith((".opus", ".m4a", ".webm", ".mp3", ".ogg"))]
        if not files:
            return None
        path = os.path.join(out_dir, files[0])
        with open(path, "rb") as f:
            data = f.read()
        duration = _get_duration_from_buffer(io.BytesIO(data)) if data else 0
        if duration <= 0 and len(data) > 1000:
            duration = max(60.0, len(data) / 3000.0)
        # opus değilse ffmpeg ile çevir
        if not path.endswith(".opus") and not path.endswith(".ogg"):
            proc2 = subprocess.run(
                [FFMPEG, "-i", path, "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
                 "-f", "ogg", "-loglevel", "error", "pipe:1"],
                capture_output=True, timeout=120,
            )
            if proc2.returncode == 0:
                data = proc2.stdout
        buffer = io.BytesIO(data)
        meta = {"title": "", "description": "", "channel": "", "categories": "", "tags": "", "platform": platform}
        print("[yt-dlp subprocess] başarılı")
        return buffer, duration, meta
    except Exception as e:
        print(f"[yt-dlp subprocess] error: {e}")
        return None
    finally:
        try:
            for f in os.listdir(out_dir):
                os.unlink(os.path.join(out_dir, f))
            os.rmdir(out_dir)
        except OSError:
            pass


def _rapidapi_hosts() -> list[str]:
    """RAPIDAPI_HOSTS (virgülle ayrılmış) veya RAPIDAPI_YOUTUBE_HOST listesini döndür."""
    hosts_str = os.getenv("RAPIDAPI_HOSTS", "").strip()
    if hosts_str:
        return [h.strip() for h in hosts_str.split(",") if h.strip()]
    host = os.getenv("RAPIDAPI_YOUTUBE_HOST", "").strip()
    return [host] if host else []


def _download_audio_via_rapidapi_ytapi(
    url: str, host: str, api_key: str
) -> tuple[io.BytesIO, float, dict] | None:
    """yt-api.p.rapidapi.com: GET /dl?id=VIDEO_ID - stream URL döner."""
    video_id = _extract_youtube_video_id(url)
    if not video_id:
        print("[RapidAPI yt-api] No video_id from URL")
        return None
    api_url = f"https://{host.rstrip('/')}/dl?id={video_id}"
    print(f"[RapidAPI yt-api] Requesting {host}/dl?id={video_id[:8]}...")
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host}
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(api_url, headers=headers)
            if r.status_code != 200:
                print(f"[RapidAPI yt-api] {r.status_code} {r.text[:150]}")
                return None
            api_data = r.json()
    except Exception as e:
        print(f"[RapidAPI yt-api] {e}")
        return None

    # stream URL çıkar: yt-api kök seviyede formats/adaptiveFormats döner
    download_url = None
    streaming = api_data.get("streamingData") or {}
    formats = (
        api_data.get("adaptiveFormats")
        or api_data.get("formats")
        or streaming.get("adaptiveFormats")
        or streaming.get("formats")
        or []
    )
    for f in formats:
        if isinstance(f, dict):
            mime = (f.get("mimeType") or "").lower()
            if "audio" in mime:
                u = f.get("url")
                if u and str(u).startswith(("http://", "https://")):
                    download_url = u
                    break
    if not download_url and formats:
        f0 = formats[0] if isinstance(formats[0], dict) else {}
        download_url = f0.get("url")
    if not download_url:
        download_url = api_data.get("url") or api_data.get("streamingUrl")
    if not download_url or not str(download_url).startswith(("http://", "https://")):
        print(f"[RapidAPI yt-api] No stream URL. Keys: {list(api_data.keys())}")
        return None

    print(f"[RapidAPI yt-api] Downloading from googlevideo... ({len(download_url)} chars)")
    download_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.youtube.com/",
        "Origin": "https://www.youtube.com",
        "Range": "bytes=0-",
    }
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            with client.stream("GET", download_url, headers=download_headers) as stream:
                if stream.status_code not in (200, 206):
                    print(f"[RapidAPI yt-api] Download {stream.status_code}")
                    return None
                audio_buffer = io.BytesIO()
                for chunk in stream.iter_bytes(chunk_size=8192):
                    audio_buffer.write(chunk)
    except Exception as e:
        print(f"[RapidAPI yt-api] Download error: {type(e).__name__} {e}")
        return None

    audio_buffer.seek(0)
    raw_data = audio_buffer.read()
    audio_buffer.seek(0)
    print(f"[RapidAPI yt-api] Downloaded {len(raw_data)} bytes")
    if len(raw_data) < 1000:
        head = raw_data[:200].decode(errors="replace")
        print(f"[RapidAPI yt-api] Data too small. First 100 chars: {repr(head[:100])}")
        return None
    if raw_data[:4] == b"<htm" or raw_data[:5] == b"<!DOC":
        print("[RapidAPI yt-api] Got HTML instead of audio (403/blocked?)")
        return None

    proc = subprocess.run(
        [
            FFMPEG, "-i", "pipe:0",
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        input=raw_data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        print(f"[RapidAPI yt-api] FFmpeg: {proc.stderr.decode(errors='ignore')[:150]}")
        return None

    buffer = io.BytesIO(proc.stdout)
    vid = api_data.get("videoDetails") or {}
    duration = float(vid.get("lengthSeconds") or api_data.get("lengthSeconds") or 0)
    if duration <= 0:
        duration = _get_duration_from_buffer(buffer)
        buffer.seek(0)
    if duration <= 0 and len(proc.stdout) > 1000:
        duration = max(60.0, len(proc.stdout) / 3000.0)

    title = str(vid.get("title") or api_data.get("title") or "")
    author = str(vid.get("author") or api_data.get("author") or "")
    meta = {
        "title": title,
        "description": str(api_data.get("description", ""))[:500],
        "channel": author,
        "categories": "",
        "tags": "",
        "platform": "youtube",
    }
    print(f"[RapidAPI yt-api] OK ({host}): {url[:50]}...")
    return buffer, duration, meta


def _download_audio_via_rapidapi_ytmp3(
    url: str, host: str, api_key: str
) -> tuple[io.BytesIO, float, dict] | None:
    """
    youtube-mp3-audio-video-downloader: GET /get_m4a_download_link/{videoId}
    Kendi CDN'inden döner - googlevideo 403 yok. M4A 20-30 sn'de hazır.
    """
    video_id = _extract_youtube_video_id(url)
    if not video_id:
        return None
    api_url = f"https://{host.rstrip('/')}/get_m4a_download_link/{video_id}"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host}
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(api_url, headers=headers)
            if r.status_code != 200:
                print(f"[RapidAPI yt-mp3] API {r.status_code} {r.text[:100]}")
                return None
            api_data = r.json()
    except Exception as e:
        print(f"[RapidAPI yt-mp3] {e}")
        return None

    download_url = api_data.get("file")
    if not download_url or not str(download_url).startswith(("http://", "https://")):
        print(f"[RapidAPI yt-mp3] No file URL. Keys: {list(api_data.keys())}")
        return None

    # API: dosya 20-30 sn'de hazır olabilir; ilk denemeden önce kısa bekle
    time.sleep(5)
    # CDN indirme: timeout 150s, timeout/network hatasında tekrar dene
    print(f"[RapidAPI yt-mp3] Downloading... (API CDN)")
    headers_dl = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    raw_data = None
    for attempt in range(7):
        try:
            with httpx.Client(timeout=150.0, follow_redirects=True) as client:
                r = client.get(download_url, headers=headers_dl)
                if r.status_code == 200:
                    raw_data = r.content
                    break
                if r.status_code == 404 and attempt < 6:
                    time.sleep(5)
                    continue
                print(f"[RapidAPI yt-mp3] Download {r.status_code} (attempt {attempt + 1})")
                return None
        except Exception as e:
            print(f"[RapidAPI yt-mp3] Download error (attempt {attempt + 1}/7): {e}", file=sys.stderr, flush=True)
            if attempt < 4:
                time.sleep(5)
                continue
            return None

    if not raw_data or len(raw_data) < 1000:
        print(f"[RapidAPI yt-mp3] Invalid data ({len(raw_data) if raw_data else 0} bytes)")
        return None

    proc = subprocess.run(
        [
            FFMPEG, "-i", "pipe:0",
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        input=raw_data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        print(f"[RapidAPI yt-mp3] FFmpeg: {proc.stderr.decode(errors='ignore')[:100]}")
        return None

    buffer = io.BytesIO(proc.stdout)
    duration = _get_duration_from_buffer(buffer)
    buffer.seek(0)
    if duration <= 0 and len(proc.stdout) > 1000:
        duration = max(60.0, len(proc.stdout) / 3000.0)

    # Opsiyonel: /get-video-info/{videoId} ile title al
    title = ""
    try:
        with httpx.Client(timeout=10.0) as client:
            ri = client.get(f"https://{host}/get-video-info/{video_id}", headers=headers)
            if ri.status_code == 200:
                info = ri.json()
                title = str(info.get("title", ""))[:500]
    except Exception:
        pass

    meta = {
        "title": title,
        "description": "",
        "channel": "",
        "categories": "",
        "tags": "",
        "platform": "youtube",
    }
    print(f"[RapidAPI yt-mp3] OK: {url[:50]}...")
    return buffer, duration, meta


def _download_audio_via_rapidapi_ytvideodl(
    url: str, host: str, api_key: str
) -> tuple[io.BytesIO, float, dict] | None:
    """
    youtube-video-download.p.rapidapi.com: GET /video?videourl=URL
    Proxied/CDN URL dönebilir (googlevideo 403 bypass).
    """
    if "youtube.com" not in url and "youtu.be" not in url:
        return None
    api_url = f"https://{host.rstrip('/')}/video?videourl={urllib.parse.quote(url)}"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": host}
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(api_url, headers=headers)
            if r.status_code != 200:
                print(f"[RapidAPI yt-videodl] {r.status_code}")
                return None
            api_data = r.json()
    except Exception as e:
        print(f"[RapidAPI yt-videodl] {e}")
        return None

    download_url = (
        api_data.get("link") or api_data.get("url") or api_data.get("downloadUrl")
        or api_data.get("download_link")
    )
    if not download_url:
        links = api_data.get("links") or api_data.get("formats") or []
        for item in links if isinstance(links, list) else []:
            if isinstance(item, dict) and (item.get("url") or item.get("link")):
                download_url = item.get("url") or item.get("link")
                break
    if not download_url or not str(download_url).startswith(("http://", "https://")):
        print(f"[RapidAPI yt-videodl] No URL. Keys: {list(api_data.keys())[:10]}")
        return None

    print(f"[RapidAPI yt-videodl] Downloading... ({download_url[:60]}...)")
    headers_dl = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.youtube.com/",
    }
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(download_url, headers=headers_dl)
            if r.status_code not in (200, 206):
                print(f"[RapidAPI yt-videodl] Download {r.status_code}")
                return None
            raw_data = r.content
    except Exception as e:
        print(f"[RapidAPI yt-videodl] Download error: {e}")
        return None

    if len(raw_data) < 1000 or raw_data[:4] == b"<htm" or raw_data[:5] == b"<!DOC":
        print(f"[RapidAPI yt-videodl] Invalid data ({len(raw_data)} bytes)")
        return None

    proc = subprocess.run(
        [
            FFMPEG, "-i", "pipe:0",
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        input=raw_data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        print(f"[RapidAPI yt-videodl] FFmpeg: {proc.stderr.decode(errors='ignore')[:100]}")
        return None

    buffer = io.BytesIO(proc.stdout)
    duration = float(api_data.get("duration") or api_data.get("lengthSeconds") or 0)
    if duration <= 0:
        duration = _get_duration_from_buffer(buffer)
        buffer.seek(0)
    if duration <= 0 and len(proc.stdout) > 1000:
        duration = max(60.0, len(proc.stdout) / 3000.0)

    meta = {
        "title": str(api_data.get("title", ""))[:500],
        "description": str(api_data.get("description", ""))[:500],
        "channel": str(api_data.get("channel") or api_data.get("author", "")),
        "categories": "",
        "tags": "",
        "platform": "youtube",
    }
    print(f"[RapidAPI yt-videodl] OK: {url[:50]}...")
    return buffer, duration, meta


def _download_audio_via_rapidapi_social(
    url: str, platform: str, host: str | None = None
) -> tuple[io.BytesIO, float, dict] | None:
    """
    Download audio via RapidAPI Social Download All In One. YouTube, X, TikTok, etc.
    POST /v1/social/autolink, {"url": "..."}
    """
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    host = host or os.getenv("RAPIDAPI_YOUTUBE_HOST", "").strip()
    if not api_key or not host:
        return None

    api_url = f"https://{host.rstrip('/')}/v1/social/autolink"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": host,
        "Content-Type": "application/json",
    }
    body = {"url": url}

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(api_url, headers=headers, json=body)
            if r.status_code != 200:
                print(f"[RapidAPI] API error: {r.status_code} {r.text[:200]}")
                return None
            api_data = r.json()
    except httpx.TimeoutException:
        print("[RapidAPI] API timeout")
        return None
    except Exception as e:
        print(f"[RapidAPI] API error: {e}")
        return None

    # Hata varsa logla (X vb. için API farklı yanıt verebilir)
    if api_data.get("error") or api_data.get("status") == "error":
        print(f"[RapidAPI social] API error: {api_data.get('message', '')[:80]}")

    download_url = (
        api_data.get("link")
        or api_data.get("downloadUrl")
        or api_data.get("url")
        or api_data.get("download_link")
    )
    if not download_url:
        medias = api_data.get("medias")
        if not medias and isinstance(api_data.get("data"), dict):
            medias = api_data["data"].get("medias")
        if isinstance(medias, list) and medias:
            # TikTok: audio (mp3) tercih et, yoksa ilk medya
            for m in medias:
                if not isinstance(m, dict):
                    continue
                if (m.get("type") or "").lower() == "audio":
                    download_url = m.get("url") or m.get("link")
                    if download_url:
                        break
            if not download_url:
                m = medias[0] if isinstance(medias[0], dict) else {}
                download_url = m.get("url") or m.get("link")
        if not download_url:
            data = api_data.get("data") or api_data.get("result")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                data = data[0]
            if isinstance(data, dict):
                download_url = data.get("url") or data.get("link") or data.get("downloadUrl")
                if not download_url:
                    dmedias = data.get("medias")
                    if isinstance(dmedias, list) and dmedias and isinstance(dmedias[0], dict):
                        for m in dmedias:
                            if (m.get("type") or "").lower() == "audio":
                                download_url = m.get("url") or m.get("link")
                                break
                        if not download_url:
                            download_url = dmedias[0].get("url") or dmedias[0].get("link")
    if not download_url or not str(download_url).startswith(("http://", "https://")):
        msg = api_data.get("message", "")[:80]
        print(f"[RapidAPI social] No download link. status={api_data.get('status')} message={msg!r} keys={list(api_data.keys())}")
        return None

    # Stream audio into memory (no disk)
    # Referer platforma göre
    if platform == "tiktok":
        ref = "https://www.tiktok.com/"
    elif platform == "twitter":
        ref = "https://x.com/"
    else:
        ref = "https://www.youtube.com/"
    download_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": ref,
        "Origin": ref.rstrip("/"),
        "Range": "bytes=0-",
    }
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            with client.stream("GET", download_url, headers=download_headers) as stream:
                if stream.status_code not in (200, 206):
                    print(f"[RapidAPI social] Download {stream.status_code}")
                    return None
                audio_buffer = io.BytesIO()
                for chunk in stream.iter_bytes(chunk_size=8192):
                    audio_buffer.write(chunk)
    except httpx.TimeoutException:
        print("[RapidAPI] Download timeout")
        return None
    except Exception as e:
        print(f"[RapidAPI] Download error: {e}")
        return None

    audio_buffer.seek(0)
    raw_data = audio_buffer.read()
    audio_buffer.seek(0)
    if len(raw_data) < 1000:
        print("[RapidAPI] Downloaded data too small")
        return None

    # ffmpeg ile opus 16kHz'e dönüştür (pipe, disk yok)
    proc = subprocess.run(
        [
            FFMPEG, "-i", "pipe:0",
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        input=raw_data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="ignore")[:200]
        print(f"[RapidAPI] FFmpeg error: {err}")
        if "Invalid data" in err or "Error opening input" in err:
            print("[RapidAPI] social-download response may not be audio for this URL (e.g. YouTube unsupported or HTML)", file=sys.stderr, flush=True)
        return None

    buffer = io.BytesIO(proc.stdout)
    duration = float(api_data.get("duration") or api_data.get("lengthSeconds") or 0)
    # TikTok: duration ms cinsinden olabilir (>10000 ise ms kabul et)
    if duration > 10000:
        duration = duration / 1000.0
    if duration <= 0 and len(proc.stdout) > 0:
        duration = _get_duration_from_buffer(buffer)
        buffer.seek(0)
    if duration <= 0 and len(proc.stdout) > 1000:
        duration = max(60.0, len(proc.stdout) / 3000.0)

    data_obj = api_data.get("data")
    title = str(api_data.get("title") or (data_obj.get("title") if isinstance(data_obj, dict) else "") or "")
    meta = {
        "title": title,
        "description": str(api_data.get("description", "") or "")[:500],
        "channel": str(api_data.get("channel", "") or api_data.get("author", "") or api_data.get("uploader", "") or ""),
        "categories": "",
        "tags": "",
        "platform": platform,
    }
    print(f"[RapidAPI] OK ({host}): {url[:60]}...")
    return buffer, duration, meta


def _extract_youtube_video_id(url: str) -> str | None:
    """Extract video_id from YouTube URL. Supports watch?v=, youtu.be/, shorts/."""
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return None
    # youtu.be/VIDEO_ID
    m = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # youtube.com/shorts/VIDEO_ID
    m = re.search(r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # youtube.com/watch?v=VIDEO_ID
    m = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    # youtube.com/embed/VIDEO_ID
    m = re.search(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})", url)
    if m:
        return m.group(1)
    return None


def _download_audio_via_invidious(video_id: str) -> tuple[io.BytesIO, float, dict] | None:
    """Download audio via Invidious API. Tries multiple base URLs. Returns None on failure."""
    urls = _invidious_urls()
    data = None
    base_used = None

    for base in urls:
        base = base.rstrip("/")
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.get(f"{base}/api/v1/videos/{video_id}")
                if r.status_code != 200:
                    err_body = r.text[:200] if r.text else ""
                    print(f"[Invidious] {base} API error: {r.status_code} {err_body[:80]}")
                    continue
                data = r.json()
                if data.get("error"):
                    print(f"[Invidious] {base} error: {data.get('error', 'unknown')[:80]}")
                    continue
                base_used = base
                break
        except Exception as e:
            print(f"[Invidious] {base} Error: {e}")
            continue

    if not data or not base_used:
        return None

    formats = data.get("adaptiveFormats") or data.get("formatStreams") or []
    audio_formats = [
        f for f in formats
        if isinstance(f, dict) and (f.get("type") or "").startswith("audio/")
    ]
    if not audio_formats:
        print(f"[Invidious] {base_used} No audio format found (formats: {len(formats)})")
        return None

    # Pick highest bitrate audio format (bitrate may be string or int)
    def _bitrate_val(f: dict) -> int:
        try:
            b = f.get("bitrate") or 0
            return int(b) if b else 0
        except (ValueError, TypeError):
            return 0

    best = max(audio_formats, key=_bitrate_val)
    audio_url = best.get("url")
    if not audio_url:
        print(f"[Invidious] {base_used} No URL in audio format")
        return None
    if not audio_url.startswith(("http://", "https://")):
        audio_url = (base_used.rstrip("/") + "/" + audio_url.lstrip("/"))

    # Stream audio data (in-memory)
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            r = client.get(audio_url)
            if r.status_code != 200:
                print(f"[Invidious] {base_used} Stream error: {r.status_code}")
                return None
            raw_data = r.content
    except Exception as e:
        print(f"[Invidious] {base_used} Stream Error: {e}")
        return None

    if not raw_data:
        return None

    # ffmpeg ile ogg/opus 16kHz'e dönüştür (pipe üzerinden, disk yok)
    proc = subprocess.run(
        [
            FFMPEG, "-i", "pipe:0",
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        input=raw_data,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        print(f"[Invidious] FFmpeg error: {proc.stderr.decode(errors='ignore')[:200]}")
        return None

    buffer = io.BytesIO(proc.stdout)
    duration = float(data.get("lengthSeconds") or 0)
    if duration <= 0 and len(proc.stdout) > 0:
        duration = _get_duration_from_buffer(buffer)
        buffer.seek(0)
    if duration <= 0 and len(proc.stdout) > 1000:
        duration = max(60.0, len(proc.stdout) / 3000.0)

    meta = {
        "title": data.get("title", ""),
        "description": (data.get("description") or "")[:500],
        "channel": data.get("author", "") or data.get("channel", ""),
        "categories": "",
        "tags": ", ".join((data.get("keywords") or [])[:15]) if isinstance(data.get("keywords"), list) else "",
        "platform": "youtube",
    }
    print(f"[Invidious] OK: {video_id} via {base_used}")
    return buffer, duration, meta


def _detect_platform(url: str) -> str:
    if "twitter.com" in url or "x.com" in url:
        return "twitter"
    return "youtube"


def _normalize_youtube_url(url: str) -> str:
    """Convert youtu.be and shorts links to canonical youtube.com/watch?v= (RapidAPI compatibility)."""
    video_id = _extract_youtube_video_id(url)
    if not video_id:
        return url
    return f"https://www.youtube.com/watch?v={video_id}"


def _is_broadcast_url(url: str) -> bool:
    """Whether URL is an X/Twitter broadcast or events page."""
    return "/i/broadcasts/" in url or "/i/events/" in url


def _get_duration_from_buffer(buffer: io.BytesIO) -> float:
    """Get audio duration from buffer via ffprobe (fallback when duration=0)."""
    buffer.seek(0)
    data = buffer.read()
    buffer.seek(0)
    proc = subprocess.run(
        [
            FFPROBE,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-i", "pipe:0",
        ],
        input=data,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0 or not proc.stdout:
        return 0.0
    try:
        return float(proc.stdout.decode().strip())
    except (ValueError, TypeError):
        return 0.0


def download_audio(url: str) -> tuple[io.BytesIO, float, dict]:
    platform = _detect_platform(url)
    if platform == "youtube":
        url = _normalize_youtube_url(url)

    # YouTube + X: try yt-dlp first (no cookies). 403/fail -> RapidAPI
    result = _download_audio_via_ytdlp_subprocess(url, None, platform)
    if result is not None:
        return result
    print("[yt-dlp] Failed, trying RapidAPI...")

    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    hosts = _rapidapi_hosts()
    if not api_key or not hosts:
        raise RuntimeError("RAPIDAPI_KEY and RAPIDAPI_HOSTS (or RAPIDAPI_YOUTUBE_HOST) required")

    for host in hosts:
        host_lower = host.lower()
        if "youtube-mp3-audio-video-downloader" in host_lower:
            result = _download_audio_via_rapidapi_ytmp3(url, host, api_key)
        elif "yt-api" in host_lower:
            result = _download_audio_via_rapidapi_ytapi(url, host, api_key)
        elif "youtube-video-download" in host_lower:
            result = _download_audio_via_rapidapi_ytvideodl(url, host, api_key)
        else:
            result = _download_audio_via_rapidapi_social(url, platform, host)
        if result is not None:
            return result
        print(f"[RapidAPI] {host} failed, trying next...")

    print("[download_audio] All downloaders failed (yt-dlp + all RapidAPI hosts)", file=sys.stderr, flush=True)
    raise RuntimeError(
        "Downloader Service Unavailable (yt-dlp and RapidAPI fallbacks failed). "
        "Check RAPIDAPI_KEY, RAPIDAPI_HOSTS, and server logs."
    )


def extract_audio_chunk(
    buffer: io.BytesIO, start_sec: float, duration_sec: float
) -> np.ndarray | None:
    buffer.seek(0)
    data = buffer.read()
    buffer.seek(0)

    proc = subprocess.run(
        [
            FFMPEG,
            "-ss", str(start_sec),
            "-i", "pipe:0",
            "-t", str(duration_sec),
            "-f", "s16le", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-loglevel", "error", "pipe:1",
        ],
        input=data,
        capture_output=True,
    )
    raw = proc.stdout
    if not raw:
        return None
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


# -- Transcription ------------------------------------------------------------


def _extract_chunk_wav(buffer: io.BytesIO, start_sec: float, duration_sec: float) -> bytes | None:
    """Extract a chunk from the audio buffer as WAV bytes (for Groq API)."""
    buffer.seek(0)
    data = buffer.read()
    buffer.seek(0)

    proc = subprocess.run(
        [
            FFMPEG,
            "-ss", str(start_sec),
            "-i", "pipe:0",
            "-t", str(duration_sec),
            "-f", "wav", "-acodec", "pcm_s16le",
            "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-loglevel", "error", "pipe:1",
        ],
        input=data,
        capture_output=True,
    )
    return proc.stdout if proc.stdout else None


def _groq_client():
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)


def transcribe_chunk_groq(wav_bytes: bytes, offset_sec: float, language: str | None = None) -> list[dict]:
    """Transcribe WAV bytes via Groq Whisper API, return segments with absolute timestamps."""
    client = _groq_client()
    if not client:
        raise RuntimeError("Groq API key not configured")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(wav_bytes)
        tmp.close()

        kwargs: dict = {
            "model": "whisper-large-v3-turbo",
            "file": open(tmp.name, "rb"),
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if language:
            kwargs["language"] = language

        result = client.audio.transcriptions.create(**kwargs)

        segments = []
        for seg in (result.segments or []):
            text = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
            start = seg.get("start", 0) if isinstance(seg, dict) else getattr(seg, "start", 0)
            end = seg.get("end", 0) if isinstance(seg, dict) else getattr(seg, "end", 0)
            if text:
                segments.append({
                    "start": start + offset_sec,
                    "end": end + offset_sec,
                    "text": text,
                })
        return segments
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# Minimum audio length for local Whisper (1 sec at 16kHz); shorter chunks can cause reshape errors
MIN_SAMPLES_LOCAL_WHISPER = 16000


def transcribe_chunk_local(audio: np.ndarray, offset_sec: float, language: str | None = None) -> list[dict]:
    """Fallback: transcribe with local Whisper model."""
    if audio is None or len(audio) < MIN_SAMPLES_LOCAL_WHISPER:
        print(f"[Whisper] Skipping chunk at {offset_sec}s: audio too short (len={len(audio) if audio is not None else 0})", file=sys.stderr, flush=True)
        return []
    opts: dict = {"fp16": False}
    if language:
        opts["language"] = language
    try:
        result = whisper_model.transcribe(audio, **opts)
    except Exception as e:
        print(f"[Whisper] transcribe failed at offset {offset_sec}s (len={len(audio)}): {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return []  # skip bad chunk (e.g. reshape/tensor) instead of failing whole request
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"] + offset_sec,
            "end": seg["end"] + offset_sec,
            "text": seg["text"].strip(),
        })
    return segments


def download_and_transcribe_sync(url: str, source_lang: str | None = None) -> tuple[str, list[dict], dict]:
    """
    Download + transcribe (sync). Hermes skill can call this step separately.
    Returns: (full_transcript, segments, video_meta)
    """
    audio_buffer, duration, video_meta = download_audio(url)
    num_chunks = max(1, math.ceil(duration / CHUNK_DURATION))
    use_groq = _groq_client() is not None
    all_segments: list[dict] = []

    try:
        for i in range(num_chunks):
            start = i * CHUNK_DURATION
            segs = None
            if use_groq:
                try:
                    wav_bytes = _extract_chunk_wav(audio_buffer, start, CHUNK_DURATION)
                    if wav_bytes:
                        segs = transcribe_chunk_groq(wav_bytes, start, source_lang)
                except Exception:
                    segs = None
            if segs is None:
                chunk_audio = extract_audio_chunk(audio_buffer, start, CHUNK_DURATION)
                if chunk_audio is None or len(chunk_audio) == 0:
                    break
                segs = transcribe_chunk_local(chunk_audio, start, source_lang)
            all_segments.extend(segs or [])
            gc.collect()
    finally:
        audio_buffer.close()

    if not all_segments:
        raise RuntimeError("Transcription returned empty - does the video have audio?")
    full_transcript = " ".join(seg["text"] for seg in all_segments)
    return full_transcript, all_segments, video_meta


# -- Nous API: Summary -------------------------------------------------------


def summarize_with_nous(transcript: str, lang: str, meta: dict | None = None) -> str:
    meta = meta or {}
    context_lines = []
    if meta.get("title"):
        context_lines.append(f"Video Title: {meta['title']}")
    if meta.get("channel"):
        context_lines.append(f"Channel: {meta['channel']}")
    if meta.get("categories"):
        context_lines.append(f"Category: {meta['categories']}")
    if meta.get("tags"):
        context_lines.append(f"Tags: {meta['tags']}")
    if meta.get("description"):
        context_lines.append(f"Video Description (excerpt): {meta['description']}")
    context_block = "\n".join(context_lines)

    client = _nous_client()
    response = client.chat.completions.create(
        model="Hermes-4-70B",
        messages=[
            {
                "role": "system",
                "content": (
                    f"{NOUS_REASONING_PREAMBLE}\n\n"
                    f"You are an expert video content analyst. Your summary must be detailed, accurate, and useful.\n\n"
                    f"**Reasoning (do this inside <think> tags):**\n"
                    f"1. Use the title and description to anchor the main topic.\n"
                    f"2. Determine the genre/theme (gaming, educational, tech review, podcast, interview, news, vlog, comedy, documentary, etc.) and tailor your analysis to it.\n"
                    f"3. Identify the main narrative, key turning points, and evidence from the transcript.\n"
                    f"4. **Important:** Scan the transcript for any mentioned **sources, books, papers, studies, articles, authors, or references**. List every one you find — they are critical for the reader.\n"
                    f"5. Synthesize a clear takeaway.\n\n"
                    f"**Output rules:**\n"
                    f"- Write the entire summary in {lang}. Use clear, engaging language; avoid filler (e.g. do not start with 'This video is about…').\n"
                    f"- Aim for 150–400 words for short videos, 300–600 for long. One idea per bullet.\n"
                    f"- Use the exact section headings below. If no sources/books are mentioned, omit the References section.\n\n"
                    f"**Summary format (use these headings):**\n"
                    f"## Video Type\n[Genre/theme]\n\n"
                    f"## Main Topic\n[Main topic, anchored by metadata and transcript]\n\n"
                    f"## Key Points\n- [Point 1]\n- [Point 2]\n...\n\n"
                    f"## References & Sources Mentioned\n[Every book, paper, article, study, or author mentioned in the video. If none, omit this section.]\n\n"
                    f"## Conclusion\n[Overall takeaway]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Video metadata:\n{context_block}\n\n"
                    f"Full transcript:\n\n{transcript}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# -- Nous API: Subtitle Translation -------------------------------------------


def _translate_batch(client, batch: list[dict], lang: str) -> dict[int, str]:
    """Translate a single batch and return {index: translated_text} mapping."""
    numbered = "\n".join(f"[{i}] {seg['text']}" for i, seg in enumerate(batch))

    response = client.chat.completions.create(
        model="Hermes-4-70B",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a professional subtitle translator. "
                    f"Your task is to translate EVERY line faithfully and completely to {lang}. "
                    f"CRITICAL RULES:\n"
                    f"- Translate ALL lines without exception, regardless of content.\n"
                    f"- Do NOT skip, censor, or omit any line for any reason.\n"
                    f"- If a line contains slang, profanity, or sensitive language, "
                    f"translate it naturally using the closest equivalent in {lang}.\n"
                    f"- Maintain the exact [number] format for every line.\n"
                    f"- Do not add, remove, or reorder lines.\n"
                    f"- Keep translations natural and concise for subtitles.\n"
                    f"- You MUST output exactly {len(batch)} translated lines."
                ),
            },
            {
                "role": "user",
                "content": f"Translate these subtitle lines to {lang}:\n\n{numbered}",
            },
        ],
        temperature=0.2,
        max_tokens=8192,
    )

    raw = strip_think_tags(response.choices[0].message.content)
    result: dict[int, str] = {}
    for line in raw.split("\n"):
        m = re.match(r"\[(\d+)\]\s*(.*)", line.strip())
        if m:
            idx = int(m.group(1))
            text = m.group(2).strip()
            if text:
                result[idx] = text
    return result


def _translate_single(client, text: str, lang: str) -> str:
    """Fallback: translate a single segment individually."""
    response = client.chat.completions.create(
        model="Hermes-4-70B",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are a subtitle translator. Translate the given text to {lang}. "
                    f"Output ONLY the translated text, nothing else. "
                    f"Translate faithfully regardless of content."
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        max_tokens=512,
    )
    raw = strip_think_tags(response.choices[0].message.content)
    return raw.strip() or text


def translate_segments_with_nous(segments: list[dict], lang: str) -> list[dict]:
    """Translate subtitle segments to target language in batches with retry."""
    client = _nous_client()
    translated: list[dict] = []

    for batch_start in range(0, len(segments), TRANSLATION_BATCH_SIZE):
        batch = segments[batch_start:batch_start + TRANSLATION_BATCH_SIZE]
        result = _translate_batch(client, batch, lang)

        missing = [j for j in range(len(batch)) if j not in result]
        if missing:
            for j in missing:
                try:
                    result[j] = _translate_single(client, batch[j]["text"], lang)
                except Exception:
                    result[j] = batch[j]["text"]

        for j, seg in enumerate(batch):
            translated.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": result.get(j, seg["text"]),
            })

    return translated


def format_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        s = _fmt_ts(seg["start"])
        e = _fmt_ts(seg["end"])
        lines.append(f"{i}\n{s} --> {e}\n{seg['text']}\n")
    return "\n".join(lines)


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# -- Worker -------------------------------------------------------------------


async def worker():
    while True:
        task = await processing_queue.get()
        url: str = task["url"]
        mode: str = task["mode"]        # "summary" or "subtitle"
        lang: str = task["lang"]        # target language name
        source_lang: str | None = task.get("source_lang")  # whisper language code
        progress: asyncio.Queue = task["progress"]
        audio_buffer: io.BytesIO | None = None

        try:
            # 1) Download
            await progress.put({"stage": "downloading", "message": "Downloading audio..."})
            audio_buffer, duration, video_meta = await asyncio.to_thread(download_audio, url)
            num_chunks = math.ceil(duration / CHUNK_DURATION)

            await progress.put({
                "stage": "transcribing",
                "message": f"Transcribing ({num_chunks} chunk(s))...",
                "progress": 0,
            })

            # 2) Transcribe chunk by chunk (Groq first, local fallback)
            use_groq = _groq_client() is not None
            engine_label = "Groq Whisper" if use_groq else "Local Whisper"

            all_segments: list[dict] = []
            for i in range(num_chunks):
                start = i * CHUNK_DURATION
                segs = None

                if use_groq:
                    wav_bytes = await asyncio.to_thread(
                        _extract_chunk_wav, audio_buffer, start, CHUNK_DURATION
                    )
                    if wav_bytes:
                        for groq_attempt in range(2):  # first try, then retry once after 429
                            try:
                                segs = await asyncio.to_thread(
                                    transcribe_chunk_groq, wav_bytes, start, source_lang
                                )
                                break
                            except Exception as exc:
                                err_str = str(exc)
                                # Daily quota exhausted (ASPD): do not fall back to local (avoids SEGV and hours of CPU)
                                if "429" in err_str and ("seconds of audio per day" in err_str or "ASPD" in err_str):
                                    print("Groq daily quota exceeded, not using local Whisper", file=sys.stderr, flush=True)
                                    raise RuntimeError(
                                        "Daily transcription quota exceeded (Groq limit). Try again tomorrow or upgrade at console.groq.com."
                                    )
                                if groq_attempt == 0 and "429" in err_str:
                                    print(f"Groq 429 on chunk {i}, waiting 60s then retry...", file=sys.stderr, flush=True)
                                    await asyncio.sleep(60)
                                    continue
                                print(f"Groq failed on chunk {i}, falling back to local: {exc}")
                                segs = None
                                break
                        del wav_bytes
                    else:
                        segs = None

                if segs is None:
                    chunk_audio = await asyncio.to_thread(
                        extract_audio_chunk, audio_buffer, start, CHUNK_DURATION
                    )
                    if chunk_audio is None or len(chunk_audio) == 0:
                        print(f"[Whisper] Chunk {i + 1}/{num_chunks} empty, skipping", file=sys.stderr, flush=True)
                        await progress.put({
                            "stage": "transcribing",
                            "message": f"[{engine_label}] Chunk {i + 1}/{num_chunks} empty, skipped",
                            "progress": round((i + 1) / num_chunks * 100),
                        })
                    else:
                        try:
                            segs = await asyncio.to_thread(
                                transcribe_chunk_local, chunk_audio, start, source_lang
                            )
                        except Exception as local_exc:
                            print(f"[Whisper] Chunk {i + 1}/{num_chunks} local failed: {local_exc}", file=sys.stderr, flush=True)
                            segs = []
                        del chunk_audio
                        engine_label = "Local Whisper (fallback)"

                all_segments.extend(segs or [])
                gc.collect()

                await progress.put({
                    "stage": "transcribing",
                    "message": f"[{engine_label}] Transcription: {i + 1}/{num_chunks} chunk(s) done",
                    "progress": round((i + 1) / num_chunks * 100),
                })

            if not all_segments:
                raise RuntimeError("Transcription returned empty - does the video have audio?")

            audio_buffer.close()
            audio_buffer = None
            gc.collect()

            full_transcript = " ".join(seg["text"] for seg in all_segments)

            # 3) AI processing
            if mode == "subtitle":
                await progress.put({"stage": "thinking", "message": f"Translating subtitles to {lang}..."})
                translated = await asyncio.to_thread(
                    translate_segments_with_nous, all_segments, lang
                )
                srt_text = format_srt(translated)

                await progress.put({
                    "stage": "done",
                    "message": "Complete!",
                    "subtitle": srt_text,
                    "transcript": full_transcript,
                })
            else:
                await progress.put({"stage": "thinking", "message": f"AI is summarizing in {lang}..."})
                summary = await asyncio.to_thread(
                    summarize_with_nous, full_transcript, lang, video_meta
                )

                await progress.put({
                    "stage": "done",
                    "message": "Complete!",
                    "summary": summary,
                    "transcript": full_transcript,
                })

        except Exception as exc:
            await progress.put({"stage": "error", "message": f"Error: {str(exc)}"})
        finally:
            if audio_buffer is not None:
                audio_buffer.close()
            gc.collect()
            processing_queue.task_done()


# -- FastAPI ------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model
    _resolve_tools()
    whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    workers = [asyncio.create_task(worker()) for _ in range(CONCURRENT_WORKERS)]
    yield
    for t in workers:
        t.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join("static", "index.html"), encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/v1/summarize")
async def api_v1_summarize(request: Request):
    """
    Sync JSON endpoint for RapidAPI. POST body: {url, mode?, lang?, source_lang?}
    mode: summary | subtitle, lang: English, Turkish, etc., source_lang: Auto | en | tr | ...
    """
    if not _is_rapidapi_request(request):
        return JSONResponse({"error": "x-rapidapi-key header required"}, status_code=401)

    rate_key = f"rapidapi:{request.headers.get('x-rapidapi-key', '')}"
    if not _consume_request(rate_key, RATE_LIMIT_MAX_RAPIDAPI):
        return JSONResponse({"error": f"Rate limit reached ({RATE_LIMIT_MAX_RAPIDAPI}/hour)"}, status_code=429)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    url = (body.get("url") or "").strip()
    # Strip invisible chars (e.g. from Telegram)
    url = re.sub(r"[\u200b-\u200d\ufeff]", "", url)
    if not url or not re.search(r"youtube\.com|youtu\.be|twitter\.com|x\.com", url, re.I):
        return JSONResponse({"error": "Valid YouTube or X (Twitter) URL required"}, status_code=400)
    # Normalize YouTube URL early; reject invalid links
    if "youtube.com" in url or "youtu.be" in url:
        url = _normalize_youtube_url(url)
        if not _extract_youtube_video_id(url):
            return JSONResponse(
                {"error": "Could not parse YouTube video ID from URL. Check the link."},
                status_code=400,
            )

    mode = body.get("mode", "summary")
    if mode not in ("summary", "subtitle"):
        mode = "summary"
    lang = body.get("lang", "English")
    sl = body.get("source_lang", "Auto")
    source_lang = LANG_CODE_MAP.get(sl) if sl in LANG_CODE_MAP else (sl if isinstance(sl, str) and len(sl) == 2 else None)

    progress_queue: asyncio.Queue = asyncio.Queue()
    task = {
        "url": url,
        "mode": mode,
        "lang": lang,
        "source_lang": source_lang,
        "progress": progress_queue,
        "user_cookies": None,
    }

    if processing_queue.full():
        return JSONResponse({"error": "Server busy, try again later"}, status_code=503)

    await processing_queue.put(task)

    while True:
        msg = await progress_queue.get()
        stage = msg.get("stage")
        if stage == "done":
            return JSONResponse({
                "status": "ok",
                "summary": msg.get("summary"),
                "subtitle": msg.get("subtitle"),
                "transcript": msg.get("transcript", ""),
            })
        if stage == "error":
            message = msg.get("message", "Unknown error")
            # Download error -> 503, clear message to client
            if "downloader" in message.lower() or "download" in message.lower() or "unavailable" in message.lower():
                return JSONResponse(
                    {"error": "Could not download video. Try another link or try again later."},
                    status_code=503,
                )
            return JSONResponse({"error": message}, status_code=500)


@app.post("/api/v1/download_and_transcribe")
async def api_v1_download_and_transcribe(request: Request):
    """
    Hermes skill: call this first to download + transcribe.
    Body: { url, source_lang? }. Returns: { transcript, segments, meta }.
    """
    if not _is_rapidapi_request(request):
        return JSONResponse({"error": "x-rapidapi-key header required"}, status_code=401)
    rate_key = f"rapidapi:{request.headers.get('x-rapidapi-key', '')}"
    if not _consume_request(rate_key, RATE_LIMIT_MAX_RAPIDAPI):
        return JSONResponse({"error": f"Rate limit reached ({RATE_LIMIT_MAX_RAPIDAPI}/hour)"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    url = (body.get("url") or "").strip()
    url = re.sub(r"[\u200b-\u200d\ufeff]", "", url)
    if not url or not re.search(r"youtube\.com|youtu\.be|twitter\.com|x\.com", url, re.I):
        return JSONResponse({"error": "Valid YouTube or X (Twitter) URL required"}, status_code=400)
    if "youtube.com" in url or "youtu.be" in url:
        url = _normalize_youtube_url(url)
        if not _extract_youtube_video_id(url):
            return JSONResponse({"error": "Could not parse YouTube video ID from URL"}, status_code=400)
    sl = body.get("source_lang", "Auto")
    source_lang = LANG_CODE_MAP.get(sl) if sl in LANG_CODE_MAP else (sl if isinstance(sl, str) and len(sl) == 2 else None)
    try:
        transcript, segments, meta = await asyncio.to_thread(
            download_and_transcribe_sync, url, source_lang
        )
        return JSONResponse({
            "status": "ok",
            "transcript": transcript,
            "segments": segments,
            "meta": meta,
        })
    except RuntimeError as e:
        msg = str(e)
        if "download" in msg.lower() or "unavailable" in msg.lower():
            return JSONResponse(
                {"error": "Could not download video. Try another link or try again later."},
                status_code=503,
            )
        return JSONResponse({"error": msg}, status_code=500)
    except Exception as e:
        msg = str(e)
        if "download" in msg.lower() or "unavailable" in msg.lower():
            return JSONResponse(
                {"error": "Could not download video. Try another link or try again later."},
                status_code=503,
            )
        return JSONResponse({"error": msg}, status_code=500)


@app.post("/api/v1/summarize_from_transcript")
async def api_v1_summarize_from_transcript(request: Request):
    """
    Hermes skill: call after transcript is ready to get summary.
    Body: { transcript, lang?, meta? }. Returns: { summary }.
    """
    if not _is_rapidapi_request(request):
        return JSONResponse({"error": "x-rapidapi-key header required"}, status_code=401)
    rate_key = f"rapidapi:{request.headers.get('x-rapidapi-key', '')}"
    if not _consume_request(rate_key, RATE_LIMIT_MAX_RAPIDAPI):
        return JSONResponse({"error": f"Rate limit reached ({RATE_LIMIT_MAX_RAPIDAPI}/hour)"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    transcript = (body.get("transcript") or "").strip()
    if not transcript:
        return JSONResponse({"error": "transcript required"}, status_code=400)
    lang = body.get("lang", "English")
    meta = body.get("meta") or {}
    try:
        summary = await asyncio.to_thread(summarize_with_nous, transcript, lang, meta)
        return JSONResponse({"status": "ok", "summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/v1/subtitle_from_transcript")
async def api_v1_subtitle_from_transcript(request: Request):
    """
    Hermes skill: call when transcript/segments are ready (e.g. skill did download+transcribe).
    Body: { segments, lang? }. Returns: { srt, transcript }.
    """
    if not _is_rapidapi_request(request):
        return JSONResponse({"error": "x-rapidapi-key header required"}, status_code=401)
    rate_key = f"rapidapi:{request.headers.get('x-rapidapi-key', '')}"
    if not _consume_request(rate_key, RATE_LIMIT_MAX_RAPIDAPI):
        return JSONResponse({"error": f"Rate limit reached ({RATE_LIMIT_MAX_RAPIDAPI}/hour)"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    segments = body.get("segments")
    if not segments or not isinstance(segments, list):
        return JSONResponse({"error": "segments (list of {start, end, text}) required"}, status_code=400)
    lang = body.get("lang", "English")
    try:
        translated = await asyncio.to_thread(translate_segments_with_nous, segments, lang)
        srt_text = format_srt(translated)
        transcript = " ".join(seg.get("text", "") for seg in segments).strip()
        return JSONResponse({"status": "ok", "srt": srt_text, "transcript": transcript})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/remaining")
async def api_remaining(request: Request):
    ip = request.client.host
    remaining_verified = _get_remaining(ip, RATE_LIMIT_MAX)
    remaining_unverified = _get_remaining(ip, RATE_LIMIT_MAX_UNVERIFIED)
    return JSONResponse({
        "remaining": remaining_verified,
        "remaining_unverified": remaining_unverified,
        "max": RATE_LIMIT_MAX,
        "max_unverified": RATE_LIMIT_MAX_UNVERIFIED,
        "window": RATE_LIMIT_WINDOW,
    })


@app.get("/api/process")
async def process(
    request: Request,
    url: str,
    mode: str = "summary",
    lang: str = "English",
    source_lang: str = "Auto",
    cf_token: str = "",
    cookie_id: str = "",
):
    ip = request.client.host
    is_rapidapi = _is_rapidapi_request(request)

    if is_rapidapi:
        rate_key, limit = _get_rate_limit_key(request)
        verified = True
    else:
        turnstile_result = verify_turnstile(cf_token)
        if turnstile_result is False:
            return JSONResponse({"error": "Bot verification failed. Please refresh and try again."}, status_code=403)
        verified = turnstile_result is True
        limit = RATE_LIMIT_MAX if verified else RATE_LIMIT_MAX_UNVERIFIED
        rate_key = ip

    if not _consume_request(rate_key, limit):
        msg = f"Rate limit reached ({limit}/day)." + ("" if verified else " Complete bot verification for higher limits.")
        return JSONResponse({"error": msg}, status_code=429)

    progress_queue: asyncio.Queue = asyncio.Queue()

    async def event_stream():
        whisper_lang = LANG_CODE_MAP.get(source_lang)
        task = {
            "url": url,
            "mode": mode,
            "lang": lang,
            "source_lang": whisper_lang,
            "progress": progress_queue,
        }

        if processing_queue.full():
            yield sse({"stage": "waiting", "message": "Waiting in queue..."})

        await processing_queue.put(task)

        while True:
            msg = await progress_queue.get()
            yield sse(msg)
            if msg.get("stage") in ("done", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
