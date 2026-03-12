# Sunucu Güncelleme ve Adım Adım Kontrol

Sunucuda sırayla aşağıdaki adımları uygulayın. Her adımın sonunda "Tamam" veya çıktıyı not alın.

---

## Adım 1 — Sunucuya bağlan ve projeyi güncelle

```bash
ssh root@SUNUCU_IP
cd /opt/nouscript
git pull
```

**Beklenen:** `Fast-forward` veya `Already up to date`. Yeni dosyalar: `WEB_TEST.md`, `test_web_backend.py`, `hermes_skill_nouscript_video/`.

**Kontrol:** `ls -la test_web_backend.py hermes_skill_nouscript_video/` → dosyalar görünmeli.

---

## Adım 2 — .env kontrolü

```bash
grep -E "NOUSCRIPT_API_BASE|RAPIDAPI_KEY|TELEGRAM_BOT_TOKEN" /opt/nouscript/.env
```

**Beklenen:**
- `NOUSCRIPT_API_BASE=https://nouscript.com` (veya kendi domain)
- `RAPIDAPI_KEY=...` (dolu)
- `TELEGRAM_BOT_TOKEN=8551707483...` (Sumbot token’ı — sadece video bot için)

**Kontrol:** Hermes için token **burada olmamalı**. Hermes token’ı sadece `~/.hermes/.env` içinde.

```bash
grep TELEGRAM_BOT_TOKEN ~/.hermes/.env
```

**Beklenen:** Tek satır, `8629978322...` (Hermes / @Nouscript_bot).

---

## Adım 3 — Backend test (pipeline çalışıyor mu?)

```bash
cd /opt/nouscript
source .venv/bin/activate
python test_web_backend.py
```

**Beklenen:** `OK status: 200` ve `Summary (ilk 500 karakter): ...` (özet metni).

**Eğer hata:** `HTTP Hata: 503` veya `Could not download video` → indirme/pipeline sorunu; uvicorn loglarına bakın (Adım 5). Farklı bir kısa YouTube linki deneyin:  
`python test_web_backend.py "https://www.youtube.com/watch?v=VIDEO_ID"`

---

## Adım 4 — NouScript web uygulaması çalışıyor mu?

```bash
# Uvicorn hangi servis adıyla çalışıyorsa (nouscript, uvicorn, gunicorn vb.)
systemctl status uvicorn
# veya
systemctl status nouscript
```

**Beklenen:** `active (running)`.

Çalışmıyorsa başlatın. Servis adını bilmiyorsanız:  
`ps aux | grep -E "uvicorn|gunicorn" | grep -v grep`

---

## Adım 5 — Video özet web’den çalışıyor mu?

Tarayıcıda: **https://nouscript.com** (veya kendi domain).

1. Bir YouTube linki yapıştırın.
2. **Summary** seçin, dil İngilizce/Türkçe.
3. Turnstile’ı geçin, Submit.
4. **Beklenen:** Downloading → Transcribing → … → Done, özet metni görünsün.

**Hata alırsanız:** Sunucuda `journalctl -u uvicorn -n 30 --no-pager` (veya ilgili servis adı) ile log’a bakın.

---

## Adım 6 — Telegram video bot (Sumbot) çalışıyor mı?

```bash
sudo systemctl status nouscript-telegram-bot
```

**Beklenen:** `active (running)`.

Kapalıysa:
```bash
sudo systemctl start nouscript-telegram-bot
```

**Telegram’da test:** @NouScript_Sumbot → `/start` → karşılama mesajı gelmeli. Link atın → Summary veya Subtitles → (pipeline çalışıyorsa dosya gelir; 503 ise “Could not download video...” mesajı gelir).

---

## Adım 7 — Hermes gateway (isteğe bağlı)

Hermes sohbet botunu kullanacaksanız:

```bash
hermes gateway status
```

**Beklenen:** Çalışıyorsa `active` veya benzeri. Kapalıysa: `hermes gateway start`.

**Kontrol:** `~/.hermes/.env` içinde **sadece** `TELEGRAM_BOT_TOKEN=8629978322...` (Hermes token’ı) olmalı.

**Telegram’da test:** @Nouscript_bot → mesaj yazın → Hermes cevap vermeli.

---

## Adım 8 — Hermes skill (video özet Hermes ile)

Hermes’e video özet aldırmak için skill kurulu mu?

```bash
ls -la ~/.hermes/skills/nouscript-video/
```

**Beklenen:** `SKILL.md` ve `call_nouscript.py` görünmeli.

**Yoksa kurun:**
```bash
mkdir -p ~/.hermes/skills/nouscript-video
cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py
```

`~/.hermes/.env` içinde `NOUSCRIPT_API_BASE` ve `RAPIDAPI_KEY` tanımlı olmalı (Adım 2’de Hermes .env’i ayrı kontrol edin). Sonra: `hermes gateway restart`.

---

## Özet tablo

| # | Ne | Komut / Nerede | Beklenen |
|---|----|-----------------|----------|
| 1 | Repo güncel | `cd /opt/nouscript && git pull` | Fast-forward, yeni dosyalar |
| 2 | .env | `grep ... /opt/nouscript/.env` ve `~/.hermes/.env` | Doğru token’lar, API key |
| 3 | Backend API | `python test_web_backend.py` | 200, özet metni |
| 4 | Web servisi | `systemctl status uvicorn` (veya ilgili servis) | active (running) |
| 5 | Web arayüzü | Tarayıcı → nouscript.com → link + Summary | Özet çıktı |
| 6 | Sumbot | `systemctl status nouscript-telegram-bot` + Telegram | /start, link → cevap |
| 7 | Hermes | `hermes gateway status` + Telegram @Nouscript_bot | Sohbet cevabı |
| 8 | Hermes skill | `ls ~/.hermes/skills/nouscript-video/` | SKILL.md, call_nouscript.py |

Tüm adımlar tamamlandığında sunucu ve tüm özellikler güncel ve kontrol edilmiş olur.
