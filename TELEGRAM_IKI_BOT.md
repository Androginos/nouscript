# Telegram: İki Bot Kurulumu (Baştan Kontrollü)

Hermes = genel AI sohbet | NouScript bot = sadece video özet/altyazı. İkisi aynı token'ı kullanamaz; iki ayrı bot gerekir.

---

## Adım 1 — BotFather: İki bot, iki token

1. Telegram'da [@BotFather](https://t.me/BotFather) aç.
2. **Bot 1 (Hermes için — zaten var):**
   - Mevcut bot: `@Nouscript_bot` (veya senin adın). Token'ı **bir yere not et** (Hermes gateway bu token'ı kullanacak).
3. **Bot 2 (Video özet için):** `@NouScript_Sumbot`
   - Bu botun token'ı **sadece** `telegram_bot.py` (video özet/altyazı) için kullanılır. Bu projedeki `.env` / sunucuda `/opt/nouscript/.env` içine yazılır.

Sonuç:
- **Token A** = Hermes gateway (@Nouscript_bot, sohbet) → `~/.hermes/.env`
- **Token B** = Video bot (@NouScript_Sumbot) → bu proje `.env` / `/opt/nouscript/.env`

---

## Adım 2 — Sunucuda Hermes .env (Token A)

Dosya: `~/.hermes/.env` (root isen `/root/.hermes/.env`)

```env
TELEGRAM_BOT_TOKEN=<Token A - Hermes için>
GATEWAY_ALLOW_ALL_USERS=true
```

Kontrol:
```bash
cat ~/.hermes/.env | grep -E "TELEGRAM|GATEWAY"
```

---

## Adım 3 — Sunucuda NouScript .env (Token B = @NouScript_Sumbot)

Dosya: `/opt/nouscript/.env`

Video bot bu projedeki `TELEGRAM_BOT_TOKEN` ile çalışır. Bu dosyada **mutlaka** şunlar olsun (NouScript web + video bot için):

```env
# Mevcut NouScript değişkenleri (zaten varsa dokunma)
NOUS_API_KEY=...
GROQ_API_KEY=...
RAPIDAPI_KEY=...
RAPIDAPI_HOSTS=...
TURNSTILE_SECRET_KEY=...

# Video bot (telegram_bot.py) — Token B kullanır
TELEGRAM_BOT_TOKEN=<Token B - sadece video bot için>
NOUSCRIPT_API_BASE=https://nouscript.com
```

`NOUSCRIPT_API_BASE` = sitenin gerçek adresi (https ile, sonda / yok).

Kontrol:
```bash
cd /opt/nouscript
grep -E "TELEGRAM_BOT_TOKEN|NOUSCRIPT_API_BASE|RAPIDAPI_KEY" .env
```

---

## Adım 4 — Hermes gateway’i başlat (Token A)

```bash
hermes gateway stop   # önce varsa durdur
hermes gateway start
hermes gateway status
```

Kontrol: Telegram’da **Bot 1** (Hermes’in bağlı olduğu bot) ile konuş → sohbet cevap vermeli.

---

## Adım 5 — NouScript video bot servisini başlat (Token B)

```bash
sudo systemctl restart nouscript-telegram-bot
sudo systemctl status nouscript-telegram-bot
```

Kontrol: Telegram’da **Bot 2** (yeni açtığın video bot) ile `/start` yaz → karşılama mesajı gelmeli. Link at → Summary/Subtitles → dosya gelmeli.

---

## Adım 6 — Çakışma kontrolü

Aynı token iki yerde kullanılıyorsa "Conflict" hatası alırsın. Doğru ayar:

| Yer | Kullanılan token |
|-----|-------------------|
| `~/.hermes/.env` | Token A (Hermes botu) |
| `/opt/nouscript/.env` | Token B (Video botu) |

Process kontrolü:
```bash
ps aux | grep -E "telegram_bot|hermes"
```
- Bir tane `python .../telegram_bot.py` (systemd)
- Bir tane Hermes gateway process’i

---

## Özet

1. BotFather’da iki bot: biri Hermes (mevcut), biri video (yeni).
2. Hermes .env = Token A | Nouscript .env = Token B.
3. `hermes gateway start` + `systemctl start nouscript-telegram-bot`.
4. İki farklı Telegram botu: biri sohbet, biri video özet.
