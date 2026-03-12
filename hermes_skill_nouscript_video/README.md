# Hermes Skill: NouScript Video Summary

Install this skill so Hermes can request video summaries or subtitles.

## Setup (on server)

1. **Copy the folder**

   Copy the contents of `hermes_skill_nouscript_video` into the Hermes skills directory as **nouscript-video**:

   ```bash
   # Example: project at /opt/nouscript
   mkdir -p ~/.hermes/skills/nouscript-video
   cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
   cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
   chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py
   ```

2. **Environment variables**

   In `~/.hermes/.env`:

   ```env
   NOUSCRIPT_API_BASE=https://nouscript.com
   RAPIDAPI_KEY=your_rapidapi_key_here
   ```

   (If NouScript runs on the same server, reuse the existing `RAPIDAPI_KEY`.)

3. **Restart Hermes gateway**

   ```bash
   hermes gateway stop
   hermes gateway start
   ```

## Usage

- In **Telegram**, talk to **@Nouscript_bot** (Hermes).
- Example: “Summarize this video: https://youtube.com/watch?v=...”
- Or send `/nouscript-video` and then the link.
- The agent loads the skill and calls the API via `call_nouscript.py`, then returns the summary or subtitle text.

## Notes

- For **summary**, the skill triggers two API steps: first **download + transcribe**, then **summary from transcript**. For **subtitles**, a single full-pipeline call is used.
- Long videos may take 1–5 minutes; the agent will wait.

## Confirmation: Video download and transcript via Hermes skill

**Download and transcription are triggered by the Hermes agent skill’s API calls.**

1. User sends a video link and “summarize” to @Nouscript_bot (Hermes) on Telegram.
2. Hermes uses this skill; `call_nouscript.py` runs.
3. In **summary mode** the skill calls, in order:
   - **1) `POST /api/v1/download_and_transcribe`** — Video download (yt-dlp / RapidAPI) + audio transcription (Whisper). Returns: transcript + meta.
   - **2) `POST /api/v1/summarize_from_transcript`** — Summary from transcript (Groq/Nous). Returns: summary.
4. In **subtitle mode** the skill makes a single call: `POST /api/v1/summarize` (mode=subtitle); download and transcript are done on the API.
5. The API result is returned to the skill; Hermes delivers the text to the user.

So **video download and transcript** are performed by the first step (`download_and_transcribe`) that the skill explicitly calls; the summary step is a separate API call. The website (nouscript.com) and the Telegram Sumbot continue to use the single endpoint (`/api/v1/summarize`) for the full pipeline.
