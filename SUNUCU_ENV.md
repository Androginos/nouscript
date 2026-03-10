# Sunucu .env (RapidAPI sadece)

İndirme **sadece RapidAPI** ile yapılır. Invidious kullanılmaz.

```env
NOUS_API_KEY=...
TURNSTILE_SECRET_KEY=...
GROQ_API_KEY=...

RAPIDAPI_KEY=...
RAPIDAPI_HOSTS=youtube-video-download.p.rapidapi.com,yt-api.p.rapidapi.com,social-download-all-in-one.p.rapidapi.com
```

- **YouTube:** youtube-video-download (proxied, 403 bypass) → yt-api → social-download
- **TikTok/X:** social-download-all-in-one

**Not:** youtube-video-download ayrı RapidAPI aboneliği gerektirebilir (InsaneMedia). Yoksa listeden çıkarın.
