# Sunucuda adım adım — kopyala yapıştır

SSH ile sunucuya bağlandıktan sonra aşağıdaki blokları **sırayla** kopyalayıp terminale yapıştır. Her adımdan sonra çıktıyı kontrol et.

---

## Adım 1 — Repo güncelle

```bash
cd /opt/nouscript
git pull
ls -la test_web_backend.py hermes_skill_nouscript_video/
```

Beklenen: `git pull` başarılı, `test_web_backend.py` ve `hermes_skill_nouscript_video/` listelenir.

---

## Adım 2 — .env kontrol

```bash
echo "=== NouScript .env ==="
grep -E "NOUSCRIPT_API_BASE|RAPIDAPI_KEY|TELEGRAM_BOT_TOKEN" /opt/nouscript/.env

echo "=== Hermes .env (tek satır 862... olmalı) ==="
grep TELEGRAM_BOT_TOKEN ~/.hermes/.env
```

Beklenen: NouScript’te `8551707483...` (Sumbot), Hermes’te sadece `8629978322...`.

---

## Adım 3 — Backend test

```bash
cd /opt/nouscript
source .venv/bin/activate
python test_web_backend.py
```

Beklenen: `OK status: 200` ve özet metni. 503/500 çıkarsa pipeline sorunu var.

---

## Adım 4 — Web servisi

```bash
systemctl status uvicorn --no-pager
```

Çalışmıyorsa (inactive):

```bash
sudo systemctl start uvicorn
```

(Servis adı farklıysa: `systemctl status nouscript` veya `ps aux | grep uvicorn` ile kontrol et.)

---

## Adım 5 — Tarayıcı

Tarayıcıda https://nouscript.com aç → YouTube linki yapıştır → Summary → Submit. Özet çıkmalı.

---

## Adım 6 — Telegram Sumbot

```bash
sudo systemctl status nouscript-telegram-bot --no-pager
```

Kapalıysa:

```bash
sudo systemctl start nouscript-telegram-bot
```

Telegram’da @NouScript_Sumbot → `/start` → link at → Summary/Subtitles tıkla.

---

## Adım 7 — Hermes gateway (isteğe bağlı)

```bash
hermes gateway status
```

Kapalıysa:

```bash
hermes gateway start
```

Telegram’da @Nouscript_bot’a mesaj at → cevap gelmeli.

---

## Adım 8 — Hermes skill kurulumu

```bash
ls ~/.hermes/skills/nouscript-video/
```

`SKILL.md` ve `call_nouscript.py` yoksa:

```bash
mkdir -p ~/.hermes/skills/nouscript-video
cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py
```

`~/.hermes/.env` içinde `NOUSCRIPT_API_BASE` ve `RAPIDAPI_KEY` var mı kontrol et. Yoksa ekle. Sonra:

```bash
hermes gateway stop
hermes gateway start
```

---

## Tek seferde çalıştırmak istersen

```bash
cd /opt/nouscript
git pull
bash SUNUCU_ADIM_ADIM.sh
```

(Adım 5 tarayıcı ve Telegram testleri yine elle yapılacak.)
