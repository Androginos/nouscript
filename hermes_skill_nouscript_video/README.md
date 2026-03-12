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
