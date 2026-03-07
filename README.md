# NouScript

**Multi-Platform Video & Audio Intelligence — Powered by Hermes-4-70B**

NouScript transforms any video or audio content from YouTube, X (Twitter), and recorded Twitter Spaces into deep-dive insights and precision-engineered summaries. At its core lies the **reasoning power of Hermes-4-70B** by [Nous Research](https://nousresearch.com), enabling context-aware analysis and high-fidelity translation across 14 languages.

---

## Why Hermes-4-70B?

The entire intelligence layer of NouScript is built around **Hermes-4-70B** from Nous Research. This model brings:

- **Deep reasoning** — Structured `<think>` chains enable systematic reasoning before producing summaries, leading to more accurate and nuanced analysis.
- **Context-aware summarization** — The model infers video genre (gaming, education, tech review, podcast, etc.) from metadata and transcript, then tailors its analysis accordingly. A gaming stream is evaluated differently than an educational tutorial.
- **Professional translation** — Subtitle translations preserve tone, nuance, and domain-specific terminology without censorship or truncation.
- **Multi-language output** — 14 languages supported for both summaries and subtitles, with natural fluency across languages.

Without Hermes-4-70B’s reasoning capabilities, NouScript would be limited to generic summarization. We leverage Nous Research’s model to deliver **intelligent, context-aware** analysis that respects the nature of each piece of content.

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

---

## Tech Stack

- **AI / Reasoning:** [Hermes-4-70B](https://portal.nousresearch.com/models) by Nous Research — summaries, context analysis, translations
- **Transcription:** Groq Whisper API (`whisper-large-v3-turbo`) + local Whisper fallback
- **Backend:** FastAPI, Python
- **Frontend:** Single-page HTML, SSE for real-time progress
- **Media:** yt-dlp, ffmpeg

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

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NOUS_API_KEY` | [Nous Research API](https://portal.nousresearch.com) key — **required for Hermes-4-70B** |
| `GROQ_API_KEY` | [Groq](https://console.groq.com) key for Whisper transcription |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret for bot protection |

---

## Built With

- **[Nous Research](https://nousresearch.com)** — Hermes-4-70B inference API
- **[Hermes-4-70B](https://portal.nousresearch.com/models)** — Deep reasoning and summarization
- **[Groq](https://groq.com)** — Whisper transcription
- **[Cloudflare Turnstile](https://www.cloudflare.com/products/turnstile/)** — Bot protection

---

## Developers

- **Kutsal** — [@gurhankutsal](https://x.com/gurhankutsal) | Discord: kutsal
- **Gizdusum** — [@gizdusumandnode](https://x.com/gizdusumandnode) | Discord: gizdusum

*Developed with Hermes-4-70B by Nous Research. Powered by Innovation.*
