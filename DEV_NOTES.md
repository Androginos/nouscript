# NouScript — Development Notes

---

## Emergency / Rollback

**To return to the last known good version:**

```bash
git fetch origin
git checkout 7bc91df
# or: git reset --hard 7bc91df
```

| | Value |
|---|-------|
| **Commit** | `7bc91df` |
| **Full hash** | `7bc91df234d3d23a6875698e1469bc2121b4cd20` |
| **Date** | 2026-03-10 |
| **Message** | fix: yt-dlp --cookiefile -> --cookies for X fallback |

Revert to this commit if the Hermes Agent trial fails or in an emergency.

---

## 2025-03-10 Session Summary

### Done
- **Rate counter HUD:** 8/5 bug fixed → `max` taken dynamically from API (8/10)
- **EventSource cache-busting:** `_t=Date.now()` added for new video links (first-video repeat issue)
- **yt-dlp X fallback:** `--cookiefile` → `--cookies` (yt-dlp current version compatibility)

### X (Twitter) Flow
1. RapidAPI social-download → often "No medias found"
2. yt-dlp fallback → `cookies.txt` may be required (Netscape format)
3. **Alternative (reviewed, not implemented):** Twitter Video Downloader API (`twitter-video-downloader5.p.rapidapi.com`)

### Known State
- **Server:** Hostinger VPS, **8GB RAM** — NouScript + Hermes Agent run together without issue
- **Local Whisper fallback:** Slow on long videos (e.g. 63 chunks) when Groq is missing/failing (expected)
- **Server .env:** `RAPIDAPI_HOSTS`, `RAPIDAPI_KEY`, `GROQ_API_KEY`, `NOUS_API_KEY`, `TURNSTILE_SECRET_KEY`

---

## Hermes Agent Migration (Planned)

**Because of YouTube IP / googlevideo 403** we use the RapidAPI chain (yt-mp3, yt-api, social-download).

**Constraint:** No cookies. Video is obtained via API only.

**Hybrid flow (implemented):**
- **YouTube + X shared:** yt-dlp first (no cookies) → on failure, RapidAPI
- RapidAPI remains as fallback.

---

## Deployment Strategy (Important)

**Live site must not be affected.** Demo / promo video in preparation.

1. **Hermes setup:** Install Hermes Agent on server; existing NouScript (nouscript.com) keeps running as-is.
2. **Test:** Test Hermes in isolation locally or on server until stable.
3. **Live update:** Update live site only after Hermes is ready. Until then, do not change the current site.

---

## Hermes Agent Setup (Server)

```bash
# 1. Connect to server
ssh root@SERVER_IP

# 2. Install Hermes (does not touch NouScript; installs under ~/.hermes)
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 3. Refresh shell
source ~/.bashrc

# 4. Choose provider (Nous Portal OAuth or OpenRouter API key)
hermes model

# 5. Check
hermes doctor
hermes version

# 6. First chat (test)
hermes
```

**Install path:** `~/.hermes/hermes-agent` — NouScript at `/opt/nouscript` is separate and unaffected.

**Setup completed (2026-03-10):**
- Model: nousresearch/hermes-4-70b (Nous Portal OAuth)
- Terminal (hermes): Working ✓
- Telegram bot: Resolved — token, GATEWAY_ALLOW_ALL_USERS, log check
- Next step: Create video summary skill

---

## Follow-up
- [ ] Test X links (was yt-dlp --cookies fix deployed?)
- [ ] Twitter Video Downloader API integration if needed
- [ ] Groq check for long videos (is `GROQ_API_KEY` set on server?)
