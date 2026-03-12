# NouScript Web Sitesi Test Listesi

Önce web’i netleştirmek için aşağıdaki adımları uygulayın.

---

## 1. Backend’i doğrudan test (Turnstile / tarayıcı yok)

Sunucuda veya API’nin erişilebildiği yerde:

```bash
cd /opt/nouscript
source .venv/bin/activate
python test_web_backend.py
```

Veya curl ile (RAPIDAPI_KEY’i .env’den alın):

```bash
curl -s -X POST "https://nouscript.com/api/v1/summarize" \
  -H "Content-Type: application/json" \
  -H "x-rapidapi-key: BURAYA_RAPIDAPI_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","mode":"summary","lang":"English","source_lang":"Auto"}' \
  -w "\nHTTP: %{http_code}\n" | head -100
```

- **200 + JSON** (içinde `summary` veya `subtitle`) → backend çalışıyor.
- **503 / 500** → indirme veya pipeline hatası; uvicorn loglarına bakın.

---

## 2. Tarayıcıdan web arayüzü

1. **Adres:** https://nouscript.com (veya localhost:8000)
2. **Rate limit:** Sayfa açıldığında “X / 10 remaining” benzeri bir sayaç görünmeli.
3. **Link:** Geçerli bir YouTube veya X (Twitter) linki yapıştırın (örn. kısa bir video). **X testi:** `https://x.com/.../status/...` veya `https://twitter.com/.../status/...` ile Summary/Subtitles deneyin; backend YouTube ile aynı pipeline’ı kullanır (önce yt-dlp, gerekirse RapidAPI social).
4. **Mod:** Summary veya Subtitles seçin.
5. **Dil:** Hedef dili seçin.
6. **Turnstile:** “I’m not a robot” / doğrulama kutusunu tamamlayın (varsa).
7. **Submit:** “Summarize” / ilgili butona tıklayın.
8. **Beklenen:**  
   - Adımlar sırayla yeşil (Downloading → Transcribing → … → Done).  
   - En sonda özet metni veya altyazı metni + Export (.txt / .srt) görünmeli.
9. **Hata:** Kırmızı adım veya “Could not download video” / “Server error” → aynı linki **Backend’i doğrudan test** ile deneyin; uvicorn loglarına bakın.

---

## 3. Kontrol listesi

| # | Ne test ediliyor           | Nasıl                         | Beklenen                          |
|---|----------------------------|-------------------------------|-----------------------------------|
| 1 | API v1 summarize (backend) | test_web_backend.py veya curl | 200, JSON’da summary veya error   |
| 2 | Ana sayfa yükleniyor       | Tarayıcıda /                  | Sayfa + rate sayaç                |
| 3 | Özet (Summary)             | Link + Summary + Submit       | Özet metni + export               |
| 4 | Altyazı (Subtitles)        | Link + Subtitles + Submit     | SRT metni + export                |
| 5 | X (Twitter) linki          | X/twitter status URL + Submit  | Özet veya altyazı (yt-dlp / RapidAPI social) |
| 6 | Hata mesajı                | Geçersiz link veya 503        | Net hata mesajı (download vs.)   |

---

## 4. Sorun çıkarsa

- **503 / “Could not download video”**  
  - yt-dlp ve RapidAPI zinciri (YouTube için social atlanıyor).  
  - Uvicorn log: `journalctl -u uvicorn -n 50` veya çalıştırdığınız uvicorn çıktısı.  
  - Farklı bir YouTube linki (kısa, public) deneyin.
- **500 / “Unknown error”**  
  - Uvicorn log’ta Python traceback’e bakın.
- **Turnstile hatası**  
  - .env’de `TURNSTILE_SECRET_KEY` doğru mu, site key frontend ile uyumlu mu kontrol edin.

Bu listeyi tamamladıktan sonra web özelliği netleşmiş olur; ardından Telegram / Hermes’e geçebilirsiniz.
