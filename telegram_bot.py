"""
NouScript Telegram Bot — Video link alır, özet veya altyazı seçtirir, .txt/.srt gönderir.
Hermes katmanı şimdilik yok; doğrudan NouScript API kullanılır.
"""
import io
import os
import re
import sys
import traceback

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = os.getenv("NOUSCRIPT_API_BASE", "").rstrip("/")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()

# Geçerli video linki (YouTube, X/Twitter)
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|(?:twitter|x)\.com/\S+/status/\d+)",
    re.I,
)

# chat_id -> son gönderilen video URL (seçim butonuna basınca kullanılacak)
pending_url: dict[int, str] = {}

WELCOME_MESSAGE = """Welcome to the NouScript Video Summarizer Bot 👋

Send me a YouTube or X (Twitter) video link, and I will:
• Generate a structured summary as a .txt file, or
• Create subtitles that you can download as .txt/.srt

How it works:
1) Paste a video link in this chat
2) Choose "Summary" or "Subtitles" from the options
3) Wait a bit while I process the video
4) Download your .txt/.srt file directly from Telegram

Whenever you're ready, just send a video link to get started."""


def extract_url(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    m = URL_PATTERN.search(text.strip())
    return m.group(0).strip() if m else None


async def call_nouscript_api(url: str, mode: str) -> dict:
    """NouScript /api/v1/summarize çağrısı."""
    if not API_BASE or not RAPIDAPI_KEY:
        raise RuntimeError("NOUSCRIPT_API_BASE or RAPIDAPI_KEY is not set in .env")

    endpoint = f"{API_BASE}/api/v1/summarize"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY}
    payload = {
        "url": url,
        "mode": mode,
        "lang": "English",
        "source_lang": "Auto",
    }

    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(endpoint, json=payload, headers=headers)
        if resp.status_code >= 500:
            body = resp.text
            print(f"[API 5xx] status={resp.status_code} body={body[:500]}", file=sys.stdout)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text(WELCOME_MESSAGE)
    except Exception:
        traceback.print_exc(file=sys.stdout)
        raise


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_id = update.effective_chat.id
        text = update.message and update.message.text
        if not text:
            return

        url = extract_url(text)
        if not url:
            await update.message.reply_text(
                "Please send a valid YouTube or X (Twitter) video link.\n\n"
                "Example:\nhttps://www.youtube.com/watch?v=xxxxxxxxx"
            )
            return

        pending_url[chat_id] = url
        keyboard = [
            [
                InlineKeyboardButton("Summary (.txt)", callback_data="summary"),
                InlineKeyboardButton("Subtitles (.txt)", callback_data="subtitle"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "What would you like for this video?",
            reply_markup=reply_markup,
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
        raise


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        await query.answer()

        chat_id = update.effective_chat.id
        choice = query.data  # "summary" or "subtitle"

        url = pending_url.pop(chat_id, None)
        if not url:
            await query.edit_message_text("This link has expired. Please send the video link again.")
            return

        await query.edit_message_text("Processing your video, this may take a few minutes…")

        try:
            data = await call_nouscript_api(url, mode=choice)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await query.edit_message_text(f"Something went wrong: {e}")
            return

        if choice == "summary":
            content = (data.get("summary") or "").strip()
            if not content:
                await query.edit_message_text("Could not generate a summary.")
                return
            filename = "summary.txt"
        else:
            content = (data.get("subtitle") or "").strip()
            if not content:
                await query.edit_message_text("Could not generate subtitles.")
                return
            filename = "subtitles.srt" if re.match(r"^\d+\s", content) else "subtitles.txt"

        buf = io.BytesIO(content.encode("utf-8"))
        buf.name = filename

        await context.bot.send_document(
            chat_id=chat_id,
            document=buf,
            filename=filename,
            caption="Here is your file.",
        )
        await query.edit_message_text("Done. You can download the file above.")
    except Exception:
        traceback.print_exc(file=sys.stdout)
        raise


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Yakalanmamış hataları terminale yazdır."""
    err = getattr(context, "error", None)
    if err:
        traceback.print_exception(type(err), err, err.__traceback__, file=sys.stdout)
    else:
        traceback.print_exc(file=sys.stdout)
    if update and isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Bot encountered an error. Check server logs.",
            )
        except Exception:
            pass


def main() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")

    builder = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(30.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
    )
    app = builder.build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_error_handler(error_handler)

    print("NouScript Telegram bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
