# Hermes Skill: NouScript Video Summary

Hermes’e video özeti/altyazı aldırtmak için bu skill’i kurun.

## Kurulum (sunucuda)

1. **Klasörü kopyala**

   Projeden veya repodan `hermes_skill_nouscript_video` içeriğini Hermes skills dizinine kopyalayıp **nouscript-video** adıyla kaydedin:

   ```bash
   # Örnek: proje /opt/nouscript ise
   mkdir -p ~/.hermes/skills/nouscript-video
   cp /opt/nouscript/hermes_skill_nouscript_video/SKILL.md ~/.hermes/skills/nouscript-video/
   cp /opt/nouscript/hermes_skill_nouscript_video/call_nouscript.py ~/.hermes/skills/nouscript-video/
   chmod +x ~/.hermes/skills/nouscript-video/call_nouscript.py
   ```

2. **Ortam değişkenleri**

   `~/.hermes/.env` içinde şunlar olsun:

   ```env
   NOUSCRIPT_API_BASE=https://nouscript.com
   RAPIDAPI_KEY=your_rapidapi_key_here
   ```

   (Aynı sunucuda NouScript çalışıyorsa `RAPIDAPI_KEY` zaten vardır; aynısını kullanın.)

3. **Hermes gateway’i yeniden başlat**

   ```bash
   hermes gateway stop
   hermes gateway start
   ```

## Kullanım

- **Telegram’da @Nouscript_bot** (Hermes) ile konuşun.
- Örnek: “Şu videonun özetini çıkar: https://youtube.com/watch?v=...”
- Veya: `/nouscript-video` yazıp linki verin.
- Agent skill’i yükleyip `call_nouscript.py` ile API’yi çağırır ve özet/altyazı metnini size döner.

## Not

- **Özet (summary)** için skill iki API adımını tetikler: önce **indirme + transkript**, sonra **transkriptten özet**. Altyazı (subtitle) için tek çağrı (tam pipeline) kullanılır.
- Uzun videolarda 1–5 dakika sürebilir; agent bekleyecektir.

## Teyit: Video indirme ve transcript Hermes skill ile

**İndirme ve transkripsiyon, Hermes agent skill’in tetiklediği API adımlarıyla yapılır.**

1. Kullanıcı Telegram’da @Nouscript_bot (Hermes)’e video linki + “özet çıkar” der.
2. Hermes bu skill’i kullanır; `call_nouscript.py` çalışır.
3. **Özet modunda** skill sırayla şu iki endpoint’i çağırır:
   - **1) `POST /api/v1/download_and_transcribe`** — Video indirme (yt-dlp / RapidAPI) + ses transkripsiyonu (Whisper). Sonuç: transcript + meta.
   - **2) `POST /api/v1/summarize_from_transcript`** — Transkript metninden özet (Groq/Nous). Sonuç: summary.
4. **Altyazı modunda** skill tek çağrı yapar: `POST /api/v1/summarize` (mode=subtitle); indirme ve transkript API’de yapılır.
5. API sonucu skill’e döner; Hermes kullanıcıya metni iletir.

Yani **video indirme ve transcript**, Hermes skill’in açıkça çağırdığı ilk adım (`download_and_transcribe`) ile yapılır; özet adımı ayrı bir API çağrısıdır. Web (nouscript.com) ve Telegram Sumbot ise tek endpoint (`/api/v1/summarize`) ile tam pipeline kullanmaya devam eder.
