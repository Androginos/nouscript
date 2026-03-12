# Hermes Skill: NouScript Video Summary

Install this skill so Hermes can request video **summaries**, **transcript only**, or **subtitles**.

## Setup (on server)

1. **Copy the folder**

   Copy the contents of `hermes_skill_nouscript_video` into the Hermes skills directory as **nouscript-video**:

   ```bash
   # Example: project at /opt/nouscript
   mkdir -p ~/.hermes/skills/nouscript-video
   cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
   cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
   cp /opt/nouscript/hermes_skill_nouscript_video/local_download_transcribe.py ~/.hermes/skills/nouscript-video/
   chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py ~/.hermes/skills/nouscript-video/local_download_transcribe.py
   ```

   Ensure **yt-dlp** and **ffmpeg** are in PATH. For local transcription, install: `pip install openai` (in the Hermes env).

2. **Environment variables**

   In `~/.hermes/.env`:

   ```env
   NOUSCRIPT_API_BASE=https://nouscript.com
   RAPIDAPI_KEY=your_rapidapi_key_here
   GROQ_API_KEY=your_groq_key_here
   ```

   `GROQ_API_KEY` is used when Hermes does download+transcribe locally. If missing, the skill falls back to NouScript API for those steps.

3. **Restart Hermes gateway**

   ```bash
   hermes gateway stop
   hermes gateway start
   ```

## Usage

- In **Telegram**, talk to **@Nouscript_bot** (Hermes).
- **Summary:** “Summarize this video: https://youtube.com/watch?v=...”
- **Transcript only:** “Just the transcript for this video: …” / “Sadece transkript ver: …”
- **Subtitles:** “Get subtitles for …” / “Altyazı al: …”
- Or send `/nouscript-video` and then the link.
- The agent loads the skill and calls the API via `call_nouscript.py`, then returns the summary, transcript, or subtitle text.

## Updating the skill on the server

When the repo’s `hermes_skill_nouscript_video/` is updated (e.g. new `transcript` mode, capability text):

```bash
cd /opt/nouscript && git pull
cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py
hermes gateway restart
```

See **SUNUCU_KONTROL.md** → Adım 8b for the full checklist.

## Notes

- **Summary:** two API steps — `download_and_transcribe`, then `summarize_from_transcript`.
- **Transcript only:** one API step — `download_and_transcribe`; returns transcript (and segments) without summary or subtitle.
- **Subtitles:** single full-pipeline call (`/api/v1/summarize`, mode=subtitle).
- Long videos may take 1–5 minutes; the agent will wait.

## Who does what (Hermes does download + transcript)

**Download and transcription are triggered by the Hermes agent skill’s API calls.**

1. User sends a video link and “summarize” to @Nouscript_bot (Hermes) on Telegram.
2. Hermes uses this skill; `call_nouscript.py` runs.
3. In **summary mode** the skill calls, in order:
   - **1) `POST /api/v1/download_and_transcribe`** — Video download (yt-dlp / RapidAPI) + audio transcription (Whisper). Returns: transcript + meta.
   - **2) `POST /api/v1/summarize_from_transcript`** — Summary from transcript (Groq/Nous). Returns: summary.
4. In **subtitle mode** the skill makes a single call: `POST /api/v1/summarize` (mode=subtitle); download and transcript are done on the API.
5. The API result is returned to the skill; Hermes delivers the text to the user.

So **video download and transcript** are performed by the first step (`download_and_transcribe`) that the skill explicitly calls; the summary step is a separate API call. The website (nouscript.com) and the Telegram Sumbot continue to use the single endpoint (`/api/v1/summarize`) for the full pipeline.
