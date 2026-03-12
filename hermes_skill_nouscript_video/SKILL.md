---
name: nouscript-video
description: Summarize or get subtitles for a YouTube or X (Twitter) video via NouScript API
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, summary, youtube, transcript]
    category: productivity
---

# NouScript Video Summary

Summarize a video or get subtitles by calling the NouScript API. Use when the user shares a YouTube or X (Twitter) link and wants a summary or subtitle file.

## When to Use

- User sends a YouTube link (youtube.com, youtu.be) or X/Twitter link (x.com, twitter.com) and asks for a summary or subtitles.
- User says "summarize this video", "get subtitles for this", "özet çıkar", "altyazı al" with a link.

## Prerequisites

- `~/.hermes/.env` must contain:
  - `NOUSCRIPT_API_BASE` — e.g. `https://nouscript.com` (no trailing slash)
  - `RAPIDAPI_KEY` — same key used by NouScript API for `x-rapidapi-key`
- The helper script `call_nouscript.py` must be in the same folder as this SKILL.md (e.g. `~/.hermes/skills/nouscript-video/call_nouscript.py`).

## Procedure

1. **Get the video URL** from the user's message. If missing, ask for it. Validate that it looks like a YouTube or X link.

2. **Ask what the user wants**: summary (text) or subtitles (text). Default to summary if unclear.

3. **Call the API** using the helper script (so the agent does not embed the API key in chat). Use the full path to the script. Replace `<VIDEO_URL>` with the actual URL (keep it in quotes).
   - Summary: `python3 ~/.hermes/skills/nouscript-video/call_nouscript.py "<VIDEO_URL>" summary`
   - Subtitles: `python3 ~/.hermes/skills/nouscript-video/call_nouscript.py "<VIDEO_URL>" subtitle`
   If the skill was installed in a different path, use that path instead of `~/.hermes/skills/nouscript-video/`.

4. **Interpret the result**:
   - If the script prints JSON with `summary` or `subtitle`, show that text to the user. For long output, offer to save to a file or summarize the main points.
   - If the script prints an error (e.g. "Could not download video"), relay that to the user and suggest trying another link or again later.

5. **Optional**: If the user asked for a file, use `write_file` to save the summary or subtitle content to a path (e.g. `summary.txt` or `subtitles.txt`) and tell the user where it is.

## Pitfalls

- The API can take 1–5 minutes for long videos. Tell the user to wait.
- If the script fails with "NOUSCRIPT_API_BASE or RAPIDAPI_KEY is not set", the env vars are missing in the Hermes environment; they must be set in `~/.hermes/.env`.
- 503 or "Could not download video" usually means the video could not be fetched (region, private, or service limit). Suggest another link.

## Verification

- User receives the summary or subtitle text (or a clear error message).
- No API keys or secrets appear in the chat.
