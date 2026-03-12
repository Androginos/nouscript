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

- Çözümleme (indirme, transkripsiyon, özet) **NouScript API** tarafında yapılır; Hermes sadece isteği yollar ve sonucu iletir.
- Uzun videolarda API 1–5 dakika sürebilir; agent bekleyecektir.

## Teyit: Video indirme nerede yapılıyor?

**Video indirme Hermes agent veya skill tarafında yapılmaz.** Akış:

1. Kullanıcı Telegram’da @Nouscript_bot (Hermes)’e video linki + “özet çıkar” der.
2. Hermes bu skill’i kullanır; `call_nouscript.py` çalışır.
3. `call_nouscript.py` **NouScript API**’ye `POST /api/v1/summarize` (url, mode) gönderir.
4. **İndirme, transkripsiyon ve özet** tamamen **NouScript API (app.py)** tarafında yapılır (yt-dlp / RapidAPI, Whisper, Groq).
5. API sonucu (summary/subtitle JSON) skill’e döner; Hermes kullanıcıya metni iletir.

Yani Hermes skill yalnızca “istemci”: isteği API’ye iletir, cevabı kullanıcıya gösterir. Web sitesinden (nouscript.com) veya Telegram Sumbot’tan aynı linkle test ettiğinde aynı backend kullanılır.
