---
name: nouscriptvideo
description: Summarize, get transcript, or get subtitles for a YouTube or X video via NouScript API
version: 1.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, summary, youtube, transcript, subtitle]
    category: productivity
---

# NouScript Video Summary

Summarize a video, get the full transcript, or get subtitles by calling the NouScript API. All steps (download, transcribe, summary/subtitle) run on the API. Use when the user shares a YouTube or X link and wants a summary, transcript only, or subtitle file.

**Önemli:** Kullanıcı bir video linki (youtube.com, youtu.be, x.com) paylaşıp "transkript", "sadece transkript", "metnini çıkar", "özetle", "altyazı" istediğinde **mutlaka bu skill'i kullan**. "Yerine getiremem" deme; `call_nouscript.py` ile API'yi çağır. Link mesajda yoksa kullanıcıdan iste.

**Kullanıcı ipucu:** Agent bu skill'i seçmezse, mesajın başına **`/nouscriptvideo`** yazın (tire kullanmayın; slash sonrası tek kelime). Örnek: `/nouscriptvideo Bu videonun sadece transkriptini ver: https://youtube.com/watch?v=...`

## Agent yetkinlikleri (capabilities)

Bu skill ile Hermes agent şunları **tetikleyebilir** (işi API’de yürütür):

- **Video indirme** — Linkten ses/video indirme (yt-dlp / RapidAPI).
- **Transkripsiyon** — Sesi metne çevirme (ses → metin); özet veya altyazı olmadan sadece transkript de istenebilir.
- **Özetleme** — Transkriptten yapılandırılmış özet (Main Topic, Key Points, References, Conclusion).
- **Altyazı** — Çevrilmiş veya ham altyazı (SRT).

Kullanıcı “sadece transkript ver”, “metnini çıkar”, “özetle”, “altyazı al” gibi taleplerde bu yetkinlikler kullanılır.

## When to Use (always prefer this skill for video transcript/summary/subtitle)

- User sends a YouTube or X link **and** asks for summary, transcript, or subtitles → **use this skill**, run `call_nouscript.py`.
- Trigger phrases (with or without link in same message): "summarize this video", "get subtitles", "just the transcript", "özet çıkar", "altyazı al", "sadece transkript", "transkriptini ver", "metnini çıkar", "bu videonun transkripti", "video metni".
- If the message has no URL but the user clearly wants a video's transcript/summary/subtitle, ask: "Lütfen video linkini (YouTube veya X) gönderin." Then run the script with that link.
- **Do not** respond with "I cannot fulfill this request" for transcript/summary/subtitle; use the script instead.

## Prerequisites

- **Environment** (`~/.hermes/.env`):
  - `NOUSCRIPT_API_BASE` — e.g. `https://nouscript.com` (no trailing slash)
  - `RAPIDAPI_KEY` — for NouScript API (`x-rapidapi-key`)
- **Skill file:** `call_nouscript.py` in the same folder as this SKILL.md (e.g. `~/.hermes/skills/nouscriptvideo/`).

## Procedure

1. **Get the video URL** from the user's message. If missing, ask for it. Validate that it looks like a YouTube or X link.

2. **Ask what the user wants**: summary (text), transcript only (raw text), or subtitles (text). Default to summary if unclear. Optionally ask for output language (e.g. English, Turkish).

3. **Run the skill script** (so the agent does not embed API keys in chat). Replace `<VIDEO_URL>` with the actual URL in quotes. Optional third argument is language (e.g. `English`).
   - **Summary:** `python3 ~/.hermes/skills/nouscriptvideo/call_nouscript.py "<VIDEO_URL>" summary [lang]`
   - **Transcript only (sadece transkript):** `python3 ~/.hermes/skills/nouscriptvideo/call_nouscript.py "<VIDEO_URL>" transcript`
   - **Subtitles:** `python3 ~/.hermes/skills/nouscriptvideo/call_nouscript.py "<VIDEO_URL>" subtitle [lang]`
   If the skill was installed in a different path, use that path instead of `~/.hermes/skills/nouscriptvideo/`.

4. **Interpret the result**:
   - If the script prints JSON with `summary`, `transcript`, or `subtitle`/`srt`, show that text to the user. For long output (especially transcript), offer to save to a file.
   - If the script prints an error (e.g. "Could not download video"), relay that to the user and suggest another link or try again later.

5. **Optional**: If the user asked for a file, use `write_file` to save the summary or subtitle content and tell the user where it is.

## Pitfalls

- The API can take 1–5 minutes for long videos. Tell the user to wait.
- If the script fails with "NOUSCRIPT_API_BASE or RAPIDAPI_KEY is not set", the env vars are missing in `~/.hermes/.env`.
- 503 or "Could not download video" usually means the video could not be fetched (region, private, or service limit). Suggest another link.

## Verification

- User receives the summary, transcript, or subtitle text (or a clear error message).
- No API keys or secrets appear in the chat.
