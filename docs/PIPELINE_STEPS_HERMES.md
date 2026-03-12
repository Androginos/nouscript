# Pipeline adımları: Hangileri Hermes ile yapılabilir?

Dört adımı netleştirip her birinde **Hermes Agent** (tetikleyici) ile **Hermes model (Hermes-4-70B)** (işi yapan AI) ayrımını yapıyorum.

---

## Kısa tablo

| Adım | Şu an kim yapıyor? | Hermes Agent ile? | Hermes model ile? |
|------|--------------------|-------------------|---------------------|
| **1. Video download** | Sunucunuz (yt-dlp / RapidAPI) | Evet — skill API’yi çağırır | Hayır — model video indirmez |
| **2. Transkript** | Sunucunuz (Whisper) veya Groq | Evet — skill API’yi çağırır | Hayır — model ses→metin yapmaz |
| **3. Çeviri** | Hermes-4-70B (Nous API) | Evet — skill API’yi çağırır | **Evet — model çeviriyi yapar** |
| **4. Özetleme** | Hermes-4-70B (Nous API) | Evet — skill API’yi çağırır | **Evet — model özeti yazar** |

---

## 1. Video download

- **Ne:** Linkten videonun sesini indirmek (yt-dlp, RapidAPI vb.).
- **Şu an nerede:** NouScript API (sizin sunucunuz); `download_audio()`.
- **Hermes Agent:** Skill, `/api/v1/...` çağrısıyla bu adımı **tetikleyebilir**. İndirme işi yine sizin sunucunuzda çalışır; Agent sadece “bunu çalıştır” der.
- **Hermes model (LLM):** Video indirme işi yapmaz; metin/sohbet modelidir.

**Özet:** Download’ı “Hermes ile” yapmak = **Hermes Agent’ın skill ile API’yi çağırması**. İşi yapan sizin sunucunuz.

---

## 2. Transkript (ses → metin)

- **Ne:** İndirilen sesi metne çevirmek (Whisper: Groq veya local).
- **Şu an nerede:** NouScript API (sizin sunucunuz veya Groq); `transcribe_chunk_groq` / `transcribe_chunk_local`.
- **Hermes Agent:** Skill, download_and_transcribe veya tam pipeline API’sini çağırarak bu adımı **tetikleyebilir**. Transkripsiyon sizin sunucunuzda veya Groq’ta çalışır.
- **Hermes model (LLM):** Ses–metin (STT) yapmaz; metin üzerinde çalışan bir dil modelidir.

**Özet:** Transkripti “Hermes ile” yapmak = yine **Agent’ın API’yi tetiklemesi**. İşi yapan Whisper (sizin sunucu veya Groq).

---

## 3. Çeviri (altyazı metnini hedef dile çevirme)

- **Ne:** Transkript segment’lerini hedef dile çevirip altyazı üretmek.
- **Şu an nerede:** NouScript API, Nous Research API’ye istek atar → **Hermes-4-70B** çeviriyi yapar (`translate_segments_with_nous`).
- **Hermes Agent:** Skill, örneğin `/api/v1/summarize` (mode=subtitle) veya download_and_transcribe + ayrı çeviri endpoint’i ile bu adımı **tetikleyebilir**.
- **Hermes model (LLM):** **Evet — çeviriyi asıl yapan odur.** Backend sadece transkripti ve ayarları gönderir; metin çıktısını model üretir.

**Özet:** Çeviri hem **Agent ile tetiklenebilir** hem de **model ile yapılır**. “Hermes ile çeviri” = Agent tetikler, model çevirir.

---

## 4. Özetleme

- **Ne:** Transkripti okuyup yapılandırılmış özet (Main Topic, Key Points, References, Conclusion vb.) yazmak.
- **Şu an nerede:** NouScript API, Nous Research API’ye istek atar → **Hermes-4-70B** özeti yazar (`summarize_with_nous`).
- **Hermes Agent:** Skill, `/api/v1/download_and_transcribe` + `/api/v1/summarize_from_transcript` veya tek `/api/v1/summarize` ile bu adımı **tetikleyebilir**.
- **Hermes model (LLM):** **Evet — özeti asıl yazan odur.** Backend transkripti ve prompt’u gönderir; özet metni model üretir.

**Özet:** Özetleme hem **Agent ile tetiklenebilir** hem de **model ile yapılır**. “Hermes ile özet” = Agent tetikler, model özetler.

---

## Görsel özet

```
[Kullanıcı: video linki]
        │
        ▼
┌───────────────────┐
│  Hermes Agent     │  ← Tetikleyici (skill, Telegram @Nouscript_bot)
│  (gateway + skill)│     Tüm adımları “başlatır”, işi kendisi yapmaz
└─────────┬─────────┘
          │ API çağrıları (NOUSCRIPT_API_BASE)
          ▼
┌───────────────────┐
│  NouScript API    │
│  (sizin sunucu)   │
└─────────┬─────────┘
          │
    ┌─────┴─────┬──────────────┬──────────────┐
    ▼           ▼              ▼              ▼
┌────────┐ ┌─────────┐ ┌─────────────┐ ┌─────────────┐
│Download│ │Transkript│ │  Çeviri     │ │  Özetleme   │
│yt-dlp  │ │ Whisper  │ │ Hermes-4-70B│ │ Hermes-4-70B│
│RapidAPI│ │Groq/local│ │ (Nous API)  │ │ (Nous API)  │
└────────┘ └─────────┘ └─────────────┘ └─────────────┘
   Sunucu    Sunucu/Groq      Model            Model
```

---

## “Hermes ile yapmak” iki anlama geliyor

| Anlam | Açıklama | Hangi adımlar? |
|-------|----------|-----------------|
| **Agent tetikler** | Hermes skill, NouScript API’yi çağırır; iş sizin sunucuda veya Nous’ta yapılır. | Dördü de: download, transkript, çeviri, özet — hepsi skill ile tetiklenebilir. |
| **Model yapar** | İşi yapan AI, Hermes-4-70B (metin üreten LLM). | Sadece **çeviri** ve **özetleme**. Download ve transkript model tarafından yapılmaz. |

İstersen bir sonraki adımda “Agent ile sadece özet/çeviri tetikleyip download+transkripti başka bir serviste yapmak” gibi alternatif mimarileri de çıkarabiliriz.
