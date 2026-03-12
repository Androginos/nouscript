# NouScript

**Multi-Platform Video & Audio Intelligence — Hermes Agent & Web**

NouScript turns video and audio from YouTube, X (Twitter), and Twitter Spaces into structured summaries and subtitles. **We build on [Hermes Agent](https://github.com/NousResearch/hermes-agent):** the gateway and **nouscript-video** skill *trigger* the pipeline (download → transcription → summary) by calling the NouScript API. The **model** [Hermes-4-70B](https://nousresearch.com) by Nous Research does the actual **summary and translation** (14 languages); the agent does not run the model, it only invokes the API that uses it. The same API backs the website and the Telegram Sumbot.

---

## Why Hermes-4-70B for summaries?

The **AI layer** of NouScript (summaries, subtitle translation) uses **Hermes-4-70B** from Nous Research. This model brings:

- **Deep reasoning** — Structured `<think>` chains enable systematic reasoning before producing summaries, leading to more accurate and nuanced analysis.
- **Context-aware summarization** — The model infers video genre (gaming, education, tech review, podcast, etc.) from metadata and transcript, then tailors its analysis accordingly. A gaming stream is evaluated differently than an educational tutorial.
- **Professional translation** — Subtitle translations preserve tone, nuance, and domain-specific terminology without censorship or truncation.
- **Multi-language output** — 14 languages supported for both summaries and subtitles, with natural fluency across languages.

Without this **model’s** reasoning capabilities, NouScript would be limited to generic summarization. **Summary and translation are done by the model (Hermes-4-70B), not by the agent:** the agent runs the skill, which calls the NouScript API; the API then calls the model for the actual text. Hermes Agent is the chat interface and the skill that *invokes* the API.

---

## Features

| Feature | Description |
|--------|-------------|
| **Multi-platform** | YouTube, X (Twitter) videos, and recorded Twitter Spaces |
| **Summary mode** | Structured output: Video Type, Main Topic, Key Points, Conclusion |
| **Subtitle mode** | Timestamped translations with SRT export |
| **14 languages** | Output in English, Turkish, Spanish, French, German, etc. |
| **Video language** | Source language selection for better transcription accuracy |
| **Export** | `.txt` for summaries, `.srt` for subtitles |
| **Query history** | Local storage of recent queries (up to 20) |
| **Security** | Cloudflare Turnstile + IP rate limiting (5 queries/hour) |
| **Telegram Bot** | Dedicated bot for summary/subtitles (link → choice → file + optional in-chat text) |
| **Hermes Agent & Skills** | Video summary/subtitle via Hermes agent; skill triggers download+transcribe then summarize (two-step API) |
| **RapidAPI** | Sync JSON API for integrations (`/api/v1/summarize`, plus `download_and_transcribe` and `summarize_from_transcript` for skill use) |

---

## Tech Stack

**Hermes Agent–centric:**

- **Hermes Agent** — Gateway, skills, Telegram chat bot (@Nouscript_bot). The **nouscript-video** skill triggers the full pipeline: **download** (yt-dlp / RapidAPI) → **transcription** (Whisper, via API) → **summary** (Hermes-4-70B via API). So download and transcription are invoked by the skill; they run on the NouScript API when the skill calls `/api/v1/download_and_transcribe` and `/api/v1/summarize_from_transcript`.
- **Transcription (skill pipeline):** Triggered by the Hermes skill via the API — Groq Whisper API (`whisper-large-v3-turbo`) + local Whisper fallback. Same pipeline is used by the website and the Telegram Sumbot when they call the API.
- **Summary & translation (the model, not the agent):** [Hermes-4-70B](https://portal.nousresearch.com/models) by Nous Research produces the actual summary and subtitle translation. The **agent** only triggers the pipeline (skill → API); the **model** runs on the backend (Nous API) when the NouScript API requests it.
- **Backend:** FastAPI, Python (NouScript API consumed by the web, Telegram Sumbot, and Hermes skill).
- **Frontend:** Single-page HTML, SSE for real-time progress (website).
- **Media:** yt-dlp, ffmpeg (used by the API when the skill or web requests a video).

---

## Quick Start

```bash
# Clone
git clone https://github.com/Androginos/nouscript.git
cd nouscript

# Environment
cp .env.example .env
# Edit .env: NOUS_API_KEY, GROQ_API_KEY, TURNSTILE_SECRET_KEY

# Install
pip install -r requirements.txt

# Run
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

---

## Ways to Use NouScript (expanded scope)

| Channel | Description |
|--------|-------------|
| **Website** | [nouscript.com](https://nouscript.com) — paste a YouTube or X link, get summary or subtitles with real-time progress. |
| **Telegram Bot** | Dedicated Sumbot: send a video link, choose Summary or Subtitles, receive the result as in-chat text (for summary) plus a `.txt` / `.srt` file. Uses the same NouScript API (RapidAPI key). Configure `TELEGRAM_BOT_TOKEN`, `NOUSCRIPT_API_BASE`, `RAPIDAPI_KEY` in `.env`. |
| **Hermes Agent & Skills** | We use **Hermes Agent** (the agent framework): e.g. @Nouscript_bot on Telegram for chat, with the **nouscript-video** skill. The skill runs video **download + transcript** and **summary from transcript** as separate API steps (`/api/v1/download_and_transcribe`, `/api/v1/summarize_from_transcript`). See `hermes_skill_nouscript_video/` for setup. |

The backend (download, Whisper, Groq/Nous summary) is shared; only the entry point (web, Telegram Sumbot, or Hermes skill) differs.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NOUS_API_KEY` | [Nous Research API](https://portal.nousresearch.com) key — **required for Hermes-4-70B** |
| `GROQ_API_KEY` | [Groq](https://console.groq.com) key for Whisper transcription |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret for bot protection |
| `RAPIDAPI_KEY` | Required for RapidAPI-style clients (Telegram Sumbot, Hermes skill, `/api/v1/*`) |
| `TELEGRAM_BOT_TOKEN` | For the Telegram Sumbot (summary/subtitles). Hermes uses a separate bot token in `~/.hermes/.env`. |
| `NOUSCRIPT_API_BASE` | Base URL of the API (e.g. `https://nouscript.com`) for Telegram bot and Hermes skill |

---

## Built With

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — Agent framework (gateway, skills, Telegram chat)
- **[Nous Research](https://nousresearch.com)** — Hermes-4-70B inference API for summaries and translations
- **[Hermes-4-70B](https://portal.nousresearch.com/models)** — Model used in the backend for reasoning and summarization
- **[Groq](https://groq.com)** — Whisper transcription
- **[Cloudflare Turnstile](https://www.cloudflare.com/products/turnstile/)** — Bot protection

---

## Developers

- **Kutsal** — [@gurhankutsal](https://x.com/gurhankutsal) | Discord: kutsal
- **Gizdusum** — [@gizdusumandnode](https://x.com/gizdusumandnode) | Discord: gizdusum

*Uses Hermes Agent (gateway, skills) and Hermes-4-70B (Nous Research) for summaries. Powered by Innovation.*
