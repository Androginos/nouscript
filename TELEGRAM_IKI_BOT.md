# Telegram: Two-Bot Setup (Controlled from Scratch)

Hermes = general AI chat | NouScript bot = video summary/subtitles only. They cannot share the same token; you need two separate bots.

---

## Step 1 — BotFather: Two bots, two tokens

1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. **Bot 1 (for Hermes — may already exist):**
   - Existing bot: `@Nouscript_bot` (or your name). **Save its token** (Hermes gateway will use it).
3. **Bot 2 (for video summary):** `@NouScript_Sumbot`
   - This bot’s token is used **only** for `telegram_bot.py` (video summary/subtitles). Put it in the project `.env` or on the server in `/opt/nouscript/.env`.

Result:
- **Token A** = Hermes gateway (@Nouscript_bot, chat) → `~/.hermes/.env`
- **Token B** = Video bot (@NouScript_Sumbot) → this project’s `.env` / `/opt/nouscript/.env`

---

## Step 2 — Hermes .env on server (Token A)

File: `~/.hermes/.env` (or `/root/.hermes/.env` if root)

```env
TELEGRAM_BOT_TOKEN=<Token A - for Hermes>
GATEWAY_ALLOW_ALL_USERS=true
```

Check:
```bash
cat ~/.hermes/.env | grep -E "TELEGRAM|GATEWAY"
```

---

## Step 3 — NouScript .env on server (Token B = @NouScript_Sumbot)

File: `/opt/nouscript/.env`

The video bot runs with `TELEGRAM_BOT_TOKEN` from this project. This file **must** contain (for NouScript web + video bot):

```env
# Existing NouScript variables (leave as-is if already set)
NOUS_API_KEY=...
GROQ_API_KEY=...
RAPIDAPI_KEY=...
RAPIDAPI_HOSTS=...
TURNSTILE_SECRET_KEY=...

# Video bot (telegram_bot.py) — uses Token B
TELEGRAM_BOT_TOKEN=<Token B - video bot only>
NOUSCRIPT_API_BASE=https://nouscript.com
```

`NOUSCRIPT_API_BASE` = real site URL (https, no trailing slash).

Check:
```bash
cd /opt/nouscript
grep -E "TELEGRAM_BOT_TOKEN|NOUSCRIPT_API_BASE|RAPIDAPI_KEY" .env
```

---

## Step 4 — Start Hermes gateway (Token A)

```bash
hermes gateway stop   # stop if already running
hermes gateway start
hermes gateway status
```

Check: In Telegram, talk to **Bot 1** (the bot Hermes uses) → chat should respond.

---

## Step 5 — Start NouScript video bot service (Token B)

```bash
sudo systemctl restart nouscript-telegram-bot
sudo systemctl status nouscript-telegram-bot
```

Check: In Telegram, send `/start` to **Bot 2** (the video bot) → welcome message. Send a link → Summary/Subtitles → file should arrive.

---

## Step 6 — Conflict check

If the same token is used in both places you get a "Conflict" error. Correct setup:

| Location | Token used |
|----------|------------|
| `~/.hermes/.env` | Token A (Hermes bot) |
| `/opt/nouscript/.env` | Token B (Video bot) |

Process check:
```bash
ps aux | grep -E "telegram_bot|hermes"
```
- One `python .../telegram_bot.py` (systemd)
- One Hermes gateway process

---

## Summary

1. Two bots in BotFather: one for Hermes (existing), one for video (new).
2. Hermes .env = Token A | NouScript .env = Token B.
3. `hermes gateway start` + `systemctl start nouscript-telegram-bot`.
4. Two different Telegram bots: one for chat, one for video summary.
