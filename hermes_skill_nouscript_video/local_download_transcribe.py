#!/usr/bin/env python3
"""
Hermes skill: run download + transcribe on the Hermes side (yt-dlp + Groq).
Prints JSON { transcript, segments, meta } to stdout, or { error } and exits non-zero.
Usage: python3 local_download_transcribe.py "<video_url>" [source_lang]
Requires: GROQ_API_KEY in env, yt-dlp and ffmpeg in PATH.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

SAMPLE_RATE = 16000
CHUNK_DURATION = 300  # 5 min
LOG_PREFIX = "[nouscript-local-dt]"


def _log(msg: str) -> None:
    print(f"{LOG_PREFIX} {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC {msg}", file=sys.stderr, flush=True)


def _normalize_youtube(url: str) -> str:
    if "youtu.be/" in url:
        m = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url


def _download_audio_ytdlp(url: str) -> tuple[bytes, float, dict] | None:
    url = _normalize_youtube(url)
    ytdlp = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not ytdlp:
        _log("ERROR: yt-dlp not found in PATH")
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _log("ERROR: ffmpeg not found in PATH")
        return None
    _log(f"Downloading audio: {url[:60]}...")
    out_dir = tempfile.mkdtemp()
    out_tpl = os.path.join(out_dir, "audio.%(ext)s")
    cmd = [
        ytdlp, "-x", "-f", "worst", "-o", out_tpl,
        "--no-playlist", "--quiet", "--no-warnings",
        "--audio-format", "opus", "--audio-quality", "0",
    ]
    if "youtube.com" in url or "youtu.be" in url:
        cmd.extend(["--extractor-args", "youtube:player_client=mweb,android,web"])
    cmd.append(url)
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        _log("Download OK")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        _log(f"Download failed: {e}")
        return None
    files = [f for f in os.listdir(out_dir) if f.endswith((".opus", ".m4a", ".webm", ".mp3", ".ogg"))]
    if not files:
        return None
    path = os.path.join(out_dir, files[0])
    with open(path, "rb") as f:
        data = f.read()
    # duration: rough from file size if needed
    duration = 60.0
    try:
        r = subprocess.run(
            [ffmpeg, "-i", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in (r.stderr or "").splitlines():
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                if len(parts) >= 3:
                    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                    duration = h * 3600 + m * 60 + s
                break
    except Exception:
        if len(data) > 10000:
            duration = max(60.0, len(data) / 3000.0)
    try:
        for f in os.listdir(out_dir):
            os.unlink(os.path.join(out_dir, f))
        os.rmdir(out_dir)
    except OSError:
        pass
    meta = {"title": "", "description": "", "channel": "", "platform": "youtube" if "youtube" in url else "x"}
    return data, duration, meta


def _extract_chunk_wav(audio_data: bytes, start_sec: float, duration_sec: float, ffmpeg: str) -> bytes | None:
    proc = subprocess.run(
        [
            ffmpeg, "-ss", str(start_sec), "-i", "pipe:0", "-t", str(duration_sec),
            "-f", "wav", "-acodec", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-loglevel", "error", "pipe:1",
        ],
        input=audio_data,
        capture_output=True,
        timeout=120,
    )
    return proc.stdout if proc.stdout else None


def _transcribe_chunk_groq(wav_bytes: bytes, offset_sec: float, language: str | None, client) -> list[dict]:
    import tempfile as tf
    tmp = tf.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(wav_bytes)
        tmp.close()
        kwargs = {
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
                segments.append({"start": start + offset_sec, "end": end + offset_sec, "text": text})
        return segments
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: local_download_transcribe.py <video_url> [source_lang]"}))
        sys.exit(1)
    url = sys.argv[1].strip()
    url = re.sub(r"[\u200b-\u200d\ufeff]", "", url)
    if not re.search(r"youtube\.com|youtu\.be|twitter\.com|x\.com", url, re.I):
        print(json.dumps({"error": "Valid YouTube or X URL required"}))
        sys.exit(1)
    source_lang = None
    if len(sys.argv) > 2:
        sl = sys.argv[2].strip()
        lang_map = {
            "Auto": None, "English": "en", "Turkish": "tr", "Spanish": "es", "French": "fr",
            "German": "de", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja",
            "Korean": "ko", "Chinese": "zh", "Arabic": "ar", "Hindi": "hi", "Italian": "it", "Dutch": "nl",
        }
        source_lang = lang_map.get(sl) if sl in lang_map else (sl if len(sl) == 2 else None)

    _log(f"Start url={url[:50]}... source_lang={source_lang}")
    result = _download_audio_ytdlp(url)
    if not result:
        _log("Failing: could not download video")
        print(json.dumps({"error": "Could not download video (yt-dlp failed or missing)"}))
        sys.exit(1)
    audio_data, duration, meta = result
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print(json.dumps({"error": "ffmpeg not found in PATH"}))
        sys.exit(1)

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        _log("ERROR: GROQ_API_KEY not set")
        print(json.dumps({"error": "GROQ_API_KEY not set"}))
        sys.exit(1)
    try:
        from openai import OpenAI
    except ImportError:
        print(json.dumps({"error": "openai package required for Groq (pip install openai)"}))
        sys.exit(1)
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

    num_chunks = max(1, int((duration + CHUNK_DURATION - 1) // CHUNK_DURATION))
    _log(f"Transcribing {num_chunks} chunk(s), duration ~{duration:.0f}s")
    all_segments = []
    for i in range(num_chunks):
        start = i * CHUNK_DURATION
        wav = _extract_chunk_wav(audio_data, start, CHUNK_DURATION, ffmpeg)
        if not wav:
            _log(f"WARN: no WAV for chunk {i + 1}/{num_chunks}")
            continue
        try:
            segs = _transcribe_chunk_groq(wav, start, source_lang, client)
            all_segments.extend(segs)
            _log(f"Chunk {i + 1}/{num_chunks} OK ({len(segs)} segments)")
        except Exception as e:
            _log(f"ERROR: Groq transcribe failed chunk {i + 1}: {e}")
            print(json.dumps({"error": f"Transcription failed: {e}"}))
            sys.exit(1)

    if not all_segments:
        _log("ERROR: Transcription returned empty")
        print(json.dumps({"error": "Transcription returned empty"}))
        sys.exit(1)
    transcript = " ".join(s["text"] for s in all_segments)
    _log(f"Done: {len(all_segments)} segments, transcript len={len(transcript)}")
    out = {"transcript": transcript, "segments": all_segments, "meta": meta}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
