# YouTube Cookie Kurulumu

"Sign in to confirm you're not a bot" hatası alıyorsanız cookies kullanmanız gerekir.

---

## Kullanıcılar için (nouscript.com)

### Yöntem A: Eklenti (Otomatik)
1. [NouScript eklentisini](https://github.com/Androginos/nouscript/tree/main/extension) yükleyin (Chrome)
2. Sitede "YouTube için cookie izni ver" butonuna tıklayın
3. İzin verildiğinde videoları işleyebilirsiniz

### Yöntem B: Manuel yapıştır (Eklenti istemeyenler)
1. Tarayıcıda YouTube'a giriş yapın
2. [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) eklentisini yükleyin
3. YouTube açıkken eklentiyle cookies export edin
4. nouscript.com'da "Veya cookies.txt içeriğini yapıştır" bölümünü açın
5. Export edilen içeriği yapıştırıp "Kullan" deyin

---

## Site yöneticisi için (sunucu cookies.txt)

### Yöntem 1: yt-dlp ile (En Kolay)

yt-dlp zaten kurulu. Tarayıcıda **youtube.com'a giriş yapın**, sonra:

```bash
cd "c:\Users\aylin\OneDrive\Masaüstü\YouTube AI Summarizer"
yt-dlp --cookies-from-browser chrome --cookies cookies.txt "https://www.youtube.com/"
```

- `chrome` yerine `firefox`, `edge`, `brave` yazabilirsiniz (kullandığınız tarayıcı)
- `cookies.txt` proje klasöründe oluşur

**Not:** Tüm site cookie'lerini export eder. Dosyayı güvenli tutun, kimseyle paylaşmayın.

---

## Yöntem 2: export_cookies.py (Sadece YouTube + Google)

Sadece YouTube/Google cookie'lerini export eder (daha güvenli):

```bash
pip install browser_cookie3
cd "c:\Users\aylin\OneDrive\Masaüstü\YouTube AI Summarizer"
python export_cookies.py firefox
```

- **Firefox:** Tarayıcı açıkken çalışır
- **Chrome/Edge/Opera/Brave:** Tarayıcıyı **tamamen kapatın**, sonra çalıştırın
- Windows'ta Chrome "Unable to get key" verirse → Firefox veya Edge deneyin

---

## Sunucuya Yükleme

1. **SCP ile:**
   ```bash
   scp cookies.txt root@SUNUCU_IP:/opt/nouscript/
   ```

2. **Hostinger Dosya Yöneticisi:** `/opt/nouscript/` klasörüne `cookies.txt` yükleyin

3. **Servisi yeniden başlatın:**
   ```bash
   systemctl restart nouscript
   ```

---

## .env ile Özel Konum

Cookie dosyasını farklı bir yerde tutmak isterseniz:

```
COOKIES_FILE=/opt/nouscript/cookies.txt
```

---

## Önemli Notlar

- Cookies **1–2 haftada** expire olabilir. Hata tekrarlarsa yeniden export edin.
- `cookies.txt` `.gitignore`'da — Git'e eklenmez (güvenlik).
