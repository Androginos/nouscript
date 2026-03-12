#!/bin/bash
# Sunucuda adım adım çalıştır. Her bölümü ayrı ayrı kopyalayıp yapıştırabilirsin.
# Veya: chmod +x SUNUCU_ADIM_ADIM.sh && bash SUNUCU_ADIM_ADIM.sh

cd /opt/nouscript

# Hızlı güncelleme + restart (sadece bunu çalıştırmak için):
#   git pull && sudo systemctl restart nouscript && sudo systemctl restart nouscript-telegram-bot 2>/dev/null; echo "Done."

echo "========== Adım 1: Git pull =========="
git pull
ls -la test_web_backend.py hermes_skill_nouscript_video/ 2>/dev/null || true

echo ""
echo "========== Adım 2: .env kontrol =========="
echo "--- /opt/nouscript/.env ---"
grep -E "NOUSCRIPT_API_BASE|RAPIDAPI_KEY|TELEGRAM_BOT_TOKEN" /opt/nouscript/.env 2>/dev/null || true
echo "--- ~/.hermes/.env (Hermes token) ---"
grep TELEGRAM_BOT_TOKEN ~/.hermes/.env 2>/dev/null || true

echo ""
echo "========== Adım 3: Backend test =========="
source .venv/bin/activate
python test_web_backend.py || echo "Backend test hata verdi (503/500 olabilir)."

echo ""
echo "========== Adım 4: Web servisi =========="
systemctl status uvicorn --no-pager 2>/dev/null || systemctl status nouscript --no-pager 2>/dev/null || ps aux | grep -E "uvicorn|gunicorn" | grep -v grep || true

echo ""
echo "========== Adım 6: Telegram bot servisi =========="
systemctl status nouscript-telegram-bot --no-pager 2>/dev/null || true

echo ""
echo "========== Adım 7: Hermes gateway =========="
hermes gateway status 2>/dev/null || true

echo ""
echo "========== Adım 8: Hermes skill =========="
ls -la ~/.hermes/skills/nouscript-video/ 2>/dev/null || echo "Skill klasörü yok; kurulum komutları SUNUCU_KONTROL.md Adım 8'de."

echo ""
echo "========== Bitti. Adım 5 (tarayıcı testi) ve Telegram testleri elle yapılacak. =========="
