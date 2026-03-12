# Plan: Çeviri yükünü modelden almak — **İPTAL**

**Karar:** Çeviri ve analizi hafif servise taşımıyoruz. Tüm analiz ve çeviriyi **Hermes (model)** ile yapmaya devam ediyoruz; kalite ve hackathon hikayesi (Hermes-heavy pipeline) için. Ayrıntılar için **PLAN_HACKATHON_HERMES.md** kullanılacak.

---

## (Eski) Mevcut durum

| İş | Nerede | Kim yapıyor |
|----|--------|-------------|
| Özet (summary) | Backend (NouScript API) | Hermes-4-70B (Nous API) |
| Altyazı çevirisi (subtitle translation) | Backend (NouScript API) | Hermes-4-70B (Nous API), batch’ler halinde |

Yani hem özet hem de segment çevirisi aynı ağır modelde; altyazı için çok sayıda batch çağrı yapılıyor.

---

## Hedef

- **Çeviri yükünü** Hermes-4-70B’den almak (maliyet + gecikme azalsın).
- **Özet** modelde kalsın (kalite ve bağlam için).
- İstersen çeviriyi **agent tarafında** veya **hafif bir serviste** yapalım.

---

## Seçenekler

### A) Backend’de çeviri için hafif servis (önerilen)

- **Ne:** Altyazı çevirisini backend’de yapmaya devam et, ama artık **Hermes-4-70B yerine** başka bir servis kullan.
- **Nerede:** `app.py` içinde `translate_segments_with_nous` yerine (veya yanında) `translate_segments_with_X` eklenir; config/env ile seçilir.
- **Çeviri kaynağı örnekleri:**
  - **LibreTranslate** (self-host veya public API): ücretsiz, çok dil, REST API.
  - **Groq + küçük model** (örn. llama): zaten Groq kullanıyorsunuz; hızlı, segment çevirisi için yeterli.
  - **Google Translate API / DeepL:** ücretli, kalite iyi.
- **Artıları:** Tek yerden değişiklik, web + Telegram Sumbot + Hermes skill hepsi aynı hafif çeviriyi kullanır. Agent’a ek sorumluluk yok.
- **Eksileri:** Agent “çeviriyi yapıyor” hissi vermez; sadece model yükü azalır.

### B) Agent / skill çeviriyi yapsın

- **Ne:** Altyazı isteğinde skill: önce `download_and_transcribe` ile segment’leri alır, sonra **çeviriyi agent tarafında** yapar (agent bir “translation” tool veya dış API çağrısı kullanır), SRT’yi skill oluşturur veya backend’e gönderir.
- **Akış (örnek):**  
  1. Kullanıcı: “Altyazı, İngilizce.”  
  2. Skill → `POST /api/v1/download_and_transcribe` → segment’ler döner.  
  3. Skill → çeviri API’si veya agent’ın translate aracı → çevrilmiş metinler.  
  4. Skill → SRT formatla (skill’de veya `POST /api/v1/format_srt` gibi hafif bir endpoint ile).  
  5. Kullanıcıya altyazı dosyası verilir.
- **Çeviri kim yapacak?**
  - **Agent’ın kendi modeli:** Hermes Agent yine bir modele (örn. Hermes-4-70B) bağlıysa, çeviriyi agent yapsa da yük modele gider; modelden yükü almış olmayız.
  - **Agent bir “translate” tool kullanırsa:** Örn. skill, LibreTranslate / Groq / Google’ı çağıran bir tool; agent o tool’u kullanır. O zaman çeviri yükü gerçekten modelden kalkar.
- **Artıları:** Çeviri “agent tarafında” olur; mimari olarak agent’a daha fazla iş verilir.
- **Eksileri:** Skill’de SRT mantığı veya ek endpoint gerekir; web ve Sumbot için ayrıca backend’de hafif çeviri yine gerekebilir (yoksa onlar da modeli kullanmaya devam eder).

### C) Hibrit

- **Web + Sumbot:** Backend’de hafif çeviri (A).  
- **Hermes skill:** Skill, segment’leri aldıktan sonra aynı hafif çeviri API’sini (veya backend’e `POST /api/v1/translate_segments` ile) çağırır; SRT’yi backend döner veya skill formatlar.  
- Böylece hem model yükü kalkar hem de “çeviri agent/skill tarafında” denebilir (skill tetikliyor ve gerekirse backend’deki hafif servisi kullanıyor).

---

## Önerilen sıra (pratik)

1. **Backend’de hafif çeviri (A)**  
   - `translate_segments_with_nous` yanına `translate_segments_with_libretranslate` veya `translate_segments_with_groq_small` ekle.  
   - Env ile seçim: `USE_NOUS_FOR_SUBTITLE_TRANSLATION=false` gibi; false iken hafif servis kullanılsın.  
   - Böylece **modelden çeviri yükü kalkar**; web, Sumbot ve ileride skill hepsi bunu kullanabilir.

2. **İsteğe bağlı: Skill’i “çeviriyi tetikliyor” yap (C)**  
   - Subtitle modunda skill: `download_and_transcribe` → ardından `POST /api/v1/translate_segments` (backend hafif çeviriyi yapar) → `POST /api/v1/format_srt` veya mevcut response’ta SRT dön.  
   - Dokümantasyonda “Çeviri, agent (skill) tarafından tetiklenir; backend hafif çeviri servisini kullanır” denebilir; yük yine modelde olmaz.

3. **İleride:** Agent’a gerçekten “translation tool” (LibreTranslate / Groq vb.) eklenirse, skill o tool’u da kullanabilir; o zaman çeviriyi tamamen agent tarafına taşımak da seçenek olur.

---

## Kısa özet

- **Çeviri işini modelden almak:** Evet, altyazı çevirisini hafif bir servise (LibreTranslate, Groq küçük model vb.) taşımak yükü kaldırır.  
- **Çeviriyi “agent’a yaptırmak”:** İki anlamda olabilir:  
  - Agent’ın **tetiklemesi** (skill, backend’deki hafif çeviriyi çağırır) → planlanabilir, yük modelde olmaz.  
  - Agent’ın **kendi modeli** ile yapması → yük modelde kalır, sadece çağıran taraf değişir.  
- **Pratik adım:** Önce backend’de çeviri için hafif servis; sonra skill’i bu akışı (download_and_transcribe + translate_segments + SRT) kullanacak şekilde güncellemek. Böylece hem model yükü azalır hem de istersen “çeviriyi agent/skill tarafı tetikliyor” diyebilirsin.

Bu plana göre bir sonraki adım: backend’de hangi hafif çeviri servisini (LibreTranslate / Groq / başka) kullanmak istediğine karar verip, `translate_segments_with_X` taslağını çıkarmak olabilir.
