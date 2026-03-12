#!/bin/bash
# Run step-by-step on server. You can copy-paste each block separately.
# Or: chmod +x SUNUCU_ADIM_ADIM.sh && bash SUNUCU_ADIM_ADIM.sh

cd /opt/nouscript

# Quick update + restart (run only this if needed):
#   git pull && sudo systemctl restart nouscript && sudo systemctl restart nouscript-telegram-bot 2>/dev/null; echo "Done."

echo "========== Step 1: Git pull =========="
git pull
ls -la test_web_backend.py hermes_skill_nouscript_video/ 2>/dev/null || true

echo ""
echo "========== Step 2: .env check =========="
echo "--- /opt/nouscript/.env ---"
grep -E "NOUSCRIPT_API_BASE|RAPIDAPI_KEY|TELEGRAM_BOT_TOKEN" /opt/nouscript/.env 2>/dev/null || true
echo "--- ~/.hermes/.env (Hermes token) ---"
grep TELEGRAM_BOT_TOKEN ~/.hermes/.env 2>/dev/null || true

echo ""
echo "========== Step 3: Backend test =========="
source .venv/bin/activate
python test_web_backend.py || echo "Backend test failed (503/500 possible)."

echo ""
echo "========== Step 4: Web service =========="
systemctl status uvicorn --no-pager 2>/dev/null || systemctl status nouscript --no-pager 2>/dev/null || ps aux | grep -E "uvicorn|gunicorn" | grep -v grep || true

echo ""
echo "========== Step 6: Telegram bot service =========="
systemctl status nouscript-telegram-bot --no-pager 2>/dev/null || true

echo ""
echo "========== Step 7: Hermes gateway =========="
hermes gateway status 2>/dev/null || true

echo ""
echo "========== Step 8: Hermes skill =========="
ls -la ~/.hermes/skills/nouscriptvideo/ 2>/dev/null || echo "Skill folder missing; see SUNUCU_KONTROL.md Step 8 for setup."

echo ""
echo "========== Done. Step 5 (browser test) and Telegram tests are manual. =========="
