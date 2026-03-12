---
name: nouscript-video
description: Summarize or get subtitles for a YouTube or X video; Hermes does download and transcript, API does summary/translation
version: 1.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, summary, youtube, transcript]
    category: productivity
---

# NouScript Video Summary

Summarize a video or get subtitles. **Hermes (this skill) does download and transcription** using yt-dlp and Groq Whisper; **NouScript API** is used only for summary or subtitle translation (Hermes-4-70B). Use when the user shares a YouTube or X link and wants a summary or subtitle file.

## When to Use

- User sends a YouTube link (youtube.com, youtu.be) or X/Twitter link (x.com, twitter.com) and asks for a summary or subtitles.
- User says "summarize this video", "get subtitles for this", "özet çıkar", "altyazı al" with a link.

## Prerequisites

- **Environment** (`~/.hermes/.env`):
  - `NOUSCRIPT_API_BASE` — e.g. `https://nouscript.com` (no trailing slash)
  - `RAPIDAPI_KEY` — for NouScript API (`x-rapidapi-key`)
  - `GROQ_API_KEY` — for transcription when Hermes does download+transcribe locally
- **System:** `yt-dlp`, `ffmpeg` in PATH (for download and audio chunks). **No cookies required** — download is cookie-free; if YouTube blocks, the skill falls back to NouScript API (which may use RapidAPI).
- **Python:** `openai` package (for Groq: `pip install openai`).
- **Skill files** in the same folder as this SKILL.md (e.g. `~/.hermes/skills/nouscript-video/`):
  - `call_nouscript.py` — main entry (runs local download+transcribe, then calls API)
  - `local_download_transcribe.py` — Hermes-side download (yt-dlp) and transcribe (Groq)

If local download/transcribe fails (e.g. missing yt-dlp or GROQ_API_KEY), the script falls back to calling NouScript API for download+transcribe as well.

## Procedure

1. **Get the video URL** from the user's message. If missing, ask for it. Validate that it looks like a YouTube or X link.

2. **Ask what the user wants**: summary (text) or subtitles (text). Default to summary if unclear. Optionally ask for output language (e.g. English, Turkish).

3. **Run the skill script** (so the agent does not embed API keys in chat). Replace `<VIDEO_URL>` with the actual URL in quotes. Optional third argument is language (e.g. `English`).
   - **Summary:** `python3 ~/.hermes/skills/nouscript-video/call_nouscript.py "<VIDEO_URL>" summary [lang]`
   - **Subtitles:** `python3 ~/.hermes/skills/nouscript-video/call_nouscript.py "<VIDEO_URL>" subtitle [lang]`
   If the skill was installed in a different path, use that path instead of `~/.hermes/skills/nouscript-video/`.

4. **Interpret the result**:
   - If the script prints JSON with `summary` or `subtitle`/`srt`, show that text to the user. For long output, offer to save to a file.
   - If the script prints an error (e.g. "Could not download video"), relay that to the user and suggest another link or try again later.

5. **Optional**: If the user asked for a file, use `write_file` to save the summary or subtitle content and tell the user where it is.

## Who Does What

- **Hermes (skill):** Download (yt-dlp) and transcription (Groq Whisper). Runs on the machine where Hermes gateway runs.
- **NouScript API:** Summary (Hermes-4-70B) or subtitle translation (Hermes-4-70B) only; no download or Whisper on API for this flow when local step succeeds.

## Pitfalls

- Download and transcription can take 1–5 minutes for long videos. Tell the user to wait.
- If "GROQ_API_KEY not set" or "yt-dlp not found", the script will fall back to API for download+transcribe (NouScript server does the work).
- 503 or "Could not download video" usually means the video could not be fetched. Suggest another link.

## Verification

- User receives the summary or subtitle text (or a clear error message).
- No API keys or secrets appear in the chat.
