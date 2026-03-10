# YouTube Cookie Kurulumu

"Sign in to confirm you're not a bot" hatası alıyorsanız cookies kullanmanız gerekir.

---

## Yöntem 1: yt-dlp ile (En Kolay)

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
