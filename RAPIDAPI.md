# NouScript — RapidAPI Entegrasyonu

NouScript hem web arayüzü (nouscript.com) hem de RapidAPI üzerinden kullanılabilir.

---

## RapidAPI YouTube Downloader (İndirme Servisi)

NouScript, YouTube indirmesi için opsiyonel olarak bir RapidAPI YouTube Downloader servisi kullanabilir. Bu yöntem bot tespitini bypass eder, bakım gerektirmez.

**Kurulum (.env):**
```
RAPIDAPI_KEY=your_rapidapi_key
RAPIDAPI_YOUTUBE_HOST=youtube-video-downloader4.p.rapidapi.com
RAPIDAPI_YOUTUBE_PATH=/dl   # veya /convert (API'ye göre)
```

**Öncelik sırası:** RapidAPI → Invidious → yt-dlp

RapidAPI başarısız olursa otomatik fallback yapılır. Tüm yöntemler başarısız olursa "Downloader Service Unavailable" hatası gösterilir.

---

## İki Erişim Yolu

| Yol | Kimler için | Auth | Limit |
|-----|-------------|------|-------|
| **Web (nouscript.com)** | Son kullanıcılar | Cloudflare Turnstile | 5/saat (verified), 3/saat (unverified) |
| **RapidAPI** | Geliştiriciler, uygulamalar | x-rapidapi-key | 100/saat |

---

## RapidAPI Endpoint

**POST** `/api/v1/summarize`

**Headers:**
- `x-rapidapi-key`: RapidAPI abonelik anahtarınız
- `Content-Type: application/json`

**Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "mode": "summary",
  "lang": "English",
  "source_lang": "Auto"
}
```

| Parametre | Açıklama | Varsayılan |
|-----------|----------|------------|
| `url` | YouTube veya X (Twitter) video linki | (zorunlu) |
| `mode` | `summary` veya `subtitle` | `summary` |
| `lang` | Çıktı dili (English, Turkish, Spanish, vb.) | `English` |
| `source_lang` | Kaynak dil (Auto, en, tr, vb.) | `Auto` |

**Başarılı yanıt (summary):**
```json
{
  "status": "ok",
  "summary": "...",
  "transcript": "..."
}
```

**Başarılı yanıt (subtitle):**
```json
{
  "status": "ok",
  "subtitle": "1\n00:00:00,000 --> 00:00:05,000\n...",
  "transcript": "..."
}
```

---

## Sunucu Kurulumu

1. `.env` dosyasına ekleyin (opsiyonel, güvenlik için önerilir):
   ```
   RAPIDAPI_PROXY_SECRET=rapidapi_panelinden_alinan_secret
   ```

2. RapidAPI boş bırakılırsa, `x-rapidapi-key` header varlığı yeterli kabul edilir.

---

## RapidAPI'de Yayınlama

1. [RapidAPI Hub](https://rapidapi.com/hub) → Create API
2. Backend URL: `https://nouscript.com` (veya kendi domain'iniz)
3. Endpoint tanımı: POST `/api/v1/summarize`
4. Proxy Secret: `.env`'deki `RAPIDAPI_PROXY_SECRET` ile eşleştirin

---

## Örnek İstek (curl)

```bash
curl -X POST "https://nouscript.com/api/v1/summarize" \
  -H "x-rapidapi-key: YOUR_RAPIDAPI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","mode":"summary","lang":"Turkish"}'
```
