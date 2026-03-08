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

import numpy as np
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

import whisper
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

RATE_LIMIT_MAX = 5
RATE_LIMIT_MAX_UNVERIFIED = 3
RATE_LIMIT_WINDOW = 3600  # 1 hour
rate_limit_store: dict[str, list[float]] = {}  # ip -> [timestamps]

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
processing_queue: asyncio.Queue = asyncio.Queue(maxsize=1)

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


def _nous_client() -> OpenAI:
    return OpenAI(
        base_url="https://inference-api.nousresearch.com/v1",
        api_key=os.getenv("NOUS_API_KEY", ""),
    )


# -- Audio (in-memory) -------------------------------------------------------


def _detect_platform(url: str) -> str:
    if "twitter.com" in url or "x.com" in url:
        return "twitter"
    return "youtube"


def download_audio(url: str) -> tuple[io.BytesIO, float, dict]:
    platform = _detect_platform(url)

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "no_playlist": True,
    }

    cookies_path = os.getenv("COOKIES_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    if os.path.isfile(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    if platform == "youtube":
        ydl_opts["extractor_args"] = {
            "youtube": {"player_client": ["web", "android", "ios"]}
        }

    if platform == "twitter":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["extractor_args"] = {"twitter": {"api": ["syndication"]}}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        formats = info.get("formats") or []
        audio_url = info.get("url", "")
        if not audio_url and formats:
            for f in reversed(formats):
                if f.get("acodec") and f["acodec"] != "none":
                    audio_url = f["url"]
                    break
            if not audio_url:
                audio_url = formats[-1].get("url", "")

        duration = float(info.get("duration") or 0)

    meta = {
        "title": info.get("title", "") or info.get("fulltitle", ""),
        "description": (info.get("description") or "")[:500],
        "channel": info.get("channel", "") or info.get("uploader", "") or info.get("uploader_id", ""),
        "categories": ", ".join(info.get("categories") or []),
        "tags": ", ".join((info.get("tags") or [])[:15]),
        "platform": platform,
    }

    proc = subprocess.run(
        [
            FFMPEG, "-i", audio_url,
            "-vn", "-acodec", "libopus", "-ar", str(SAMPLE_RATE), "-ac", "1",
            "-f", "ogg", "-loglevel", "error", "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Audio download error: {proc.stderr.decode(errors='ignore')}")

    return io.BytesIO(proc.stdout), duration, meta


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


def transcribe_chunk_local(audio: np.ndarray, offset_sec: float, language: str | None = None) -> list[dict]:
    """Fallback: transcribe with local Whisper model."""
    opts: dict = {"fp16": False}
    if language:
        opts["language"] = language
    result = whisper_model.transcribe(audio, **opts)
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"] + offset_sec,
            "end": seg["end"] + offset_sec,
            "text": seg["text"].strip(),
        })
    return segments


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
                    f"You are an expert video content analyst. "
                    f"First, determine the genre/theme of the video from the metadata "
                    f"and transcript (e.g. gaming stream, educational tutorial, tech review, "
                    f"podcast, music, news, vlog, comedy, documentary, etc.). "
                    f"Then tailor your entire analysis to that context — use the appropriate "
                    f"terminology, perspective, and evaluation criteria for that genre.\n\n"
                    f"For example: a gaming stream should be analyzed in terms of gameplay, "
                    f"strategy, highlights, and entertainment value; an educational video "
                    f"should focus on concepts taught, learning outcomes, and clarity; "
                    f"a tech review should cover specs, pros/cons, and verdict.\n\n"
                    f"Think deeply inside <think> tags, then provide "
                    f"a clean, structured summary in {lang}.\n\n"
                    f"Summary format:\n"
                    f"## Video Type\n[Detected genre/theme of the video]\n\n"
                    f"## Main Topic\n[Main topic, tailored to the video type]\n\n"
                    f"## Key Points\n- [Point 1]\n- [Point 2]\n...\n\n"
                    f"## Conclusion\n[Overall takeaway, relevant to the genre]"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here is the video metadata:\n{context_block}\n\n"
                    f"Here is the full transcript:\n\n{transcript}"
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
                    try:
                        wav_bytes = await asyncio.to_thread(
                            _extract_chunk_wav, audio_buffer, start, CHUNK_DURATION
                        )
                        if wav_bytes:
                            segs = await asyncio.to_thread(
                                transcribe_chunk_groq, wav_bytes, start, source_lang
                            )
                            del wav_bytes
                    except Exception as exc:
                        print(f"Groq failed on chunk {i}, falling back to local: {exc}")
                        segs = None

                if segs is None:
                    chunk_audio = await asyncio.to_thread(
                        extract_audio_chunk, audio_buffer, start, CHUNK_DURATION
                    )
                    if chunk_audio is None or len(chunk_audio) == 0:
                        break
                    segs = await asyncio.to_thread(
                        transcribe_chunk_local, chunk_audio, start, source_lang
                    )
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
            await progress.put({"stage": "error", "message": f"Error: {exc}"})
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
    task = asyncio.create_task(worker())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join("static", "index.html"), encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


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
async def process(request: Request, url: str, mode: str = "summary", lang: str = "English", source_lang: str = "Auto", cf_token: str = ""):
    ip = request.client.host

    turnstile_result = verify_turnstile(cf_token)
    if turnstile_result is False:
        return JSONResponse({"error": "Bot verification failed. Please refresh and try again."}, status_code=403)

    verified = turnstile_result is True
    limit = RATE_LIMIT_MAX if verified else RATE_LIMIT_MAX_UNVERIFIED

    if not _consume_request(ip, limit):
        msg = f"Rate limit reached ({limit}/hour)." + ("" if verified else " Complete bot verification for higher limits.")
        return JSONResponse({"error": msg}, status_code=429)

    progress_queue: asyncio.Queue = asyncio.Queue()

    async def event_stream():
        whisper_lang = LANG_CODE_MAP.get(source_lang)
        task = {"url": url, "mode": mode, "lang": lang, "source_lang": whisper_lang, "progress": progress_queue}

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
