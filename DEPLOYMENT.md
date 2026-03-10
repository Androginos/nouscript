# NouScript — Sunucuya Kurulum Rehberi (Adım Adım)

Bu rehber Hostinger VPS üzerinde NouScript'i sıfırdan kurmanız için hazırlanmıştır.

---

## Ön Hazırlık

Hostinger panelinden şunları not edin:
- **Sunucu IP adresi** (örn: `123.45.67.89`)
- **SSH kullanıcı adı** (genelde `root` veya Hostinger'ın verdiği kullanıcı)
- **SSH şifresi** veya **SSH key**

---

## Adım 1: Sunucuya Bağlanın

### Windows (PowerShell veya CMD)

```bash
ssh root@SUNUCU_IP_ADRESI
```

Örnek: `ssh root@123.45.67.89`

İlk bağlantıda "Are you sure you want to continue connecting?" diye sorarsa `yes` yazıp Enter'a basın. Sonra şifrenizi girin.

### Bağlantı başarılıysa

Terminalde `root@sunucu:~#` benzeri bir satır görürsünüz. Artık sunucudasınız.

---

## Adım 2: Sistemi Güncelleyin

```bash
apt update && apt upgrade -y
```

Bu işlem 1–2 dakika sürebilir.

---

## Adım 3: Gerekli Yazılımları Kurun

### Python 3.11 ve pip

```bash
apt install -y python3.11 python3.11-venv python3-pip
```

### ffmpeg (ses işleme için)

```bash
apt install -y ffmpeg
```

### Git (projeyi indirmek için)

```bash
apt install -y git
```

### Nginx (web sunucusu, reverse proxy için)

```bash
apt install -y nginx
```

---

## Adım 4: Projeyi Sunucuya Kopyalayın

```bash
cd /opt
git clone https://github.com/Androginos/nouscript.git
cd nouscript
```

Proje `/opt/nouscript` klasörüne indirilmiş olacak.

---

## Adım 5: Python Ortamını Hazırlayın

```bash
cd /opt/nouscript
python3.11 -m venv venv
source venv/bin/activate
```

`(venv)` yazısı görünüyorsa sanal ortam aktif demektir.

### Bağımlılıkları kurun

```bash
pip install -r requirements.txt
```

---

## Adım 6: .env Dosyasını Oluşturun

```bash
nano .env
```

Açılan editörde şunları yazın (kendi değerlerinizle değiştirin):

```
NOUS_API_KEY=sk-buraya-nous-api-keyiniz
GROQ_API_KEY=gsk-buraya-groq-api-keyiniz
TURNSTILE_SECRET_KEY=0x4AAAAAACm1Jlcp91L8pLzLYy43ZNo0nz4
```

Kaydetmek için: `Ctrl+O` → Enter → `Ctrl+X`

---

## Adım 7: Uygulamayı Test Edin

```bash
cd /opt/nouscript
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

Tarayıcıda `http://SUNUCU_IP:8000` adresine gidin. Sayfa açılıyorsa çalışıyor demektir.

Durdurmak için: `Ctrl+C`

---

## Adım 8: Systemd Servisi Oluşturun (Her açılışta otomatik başlasın)

```bash
nano /etc/systemd/system/nouscript.service
```

İçine şunu yapıştırın:

```ini
[Unit]
Description=NouScript Video Intelligence
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/nouscript
EnvironmentFile=-/opt/nouscript/.env
Environment="PATH=/opt/nouscript/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="COOKIES_FILE=/opt/nouscript/cookies.txt"
Environment="INVIDIOUS_URL=http://localhost:3000"
ExecStart=/opt/nouscript/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Kaydet: `Ctrl+O` → Enter → `Ctrl+X`

### Servisi etkinleştirip başlatın

```bash
systemctl daemon-reload
systemctl enable nouscript
systemctl start nouscript
systemctl status nouscript
```

`active (running)` yazıyorsa servis çalışıyor demektir.

---

## Adım 9: Nginx Reverse Proxy Kurun

```bash
nano /etc/nginx/sites-available/nouscript
```

İçine şunu yazın (`SUNUCU_IP` yerine kendi IP'nizi veya domain adınızı yazın):

```nginx
server {
    listen 80;
    server_name SUNUCU_IP_veya_domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Kaydet: `Ctrl+O` → Enter → `Ctrl+X`

### Siteyi etkinleştirin

```bash
ln -s /etc/nginx/sites-available/nouscript /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

`nginx -t` hatasız ise yapılandırma doğrudur.

---

## Adım 10: SSL (HTTPS) — İsteğe Bağlı

Domain adınız varsa ve HTTPS istiyorsanız:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d domain.com
```

Certbot adımlarını takip edin. Sonrasında site `https://domain.com` üzerinden erişilebilir olur.

---

## Özet Komutlar (Hızlı Referans)

| İşlem | Komut |
|-------|-------|
| Servisi başlat | `systemctl start nouscript` |
| Servisi durdur | `systemctl stop nouscript` |
| Servisi yeniden başlat | `systemctl restart nouscript` |
| Logları izle | `journalctl -u nouscript -f` |
| Nginx yeniden yükle | `systemctl reload nginx` |

---

## Sorun Giderme

### "Port 8000 already in use"
```bash
systemctl stop nouscript
# veya
lsof -i :8000
kill -9 PID_NUMARASI
```

### Loglara bakmak
```bash
journalctl -u nouscript -n 50 --no-pager
```

### .env değiştiyse
```bash
systemctl restart nouscript
```

---

## Cloudflare Turnstile Notu

Canlı sitede Turnstile kullanıyorsanız, Cloudflare panelinde domain'inizi ekleyip yeni Site Key ve Secret Key alın. `.env` dosyasındaki `TURNSTILE_SECRET_KEY` değerini güncelleyin.

---

## YouTube indirme: Sadece RapidAPI

İndirme **sadece RapidAPI (yt-api)** ile yapılır. Invidious veya yt-dlp yedek değildir.

### .env (zorunlu)

```
RAPIDAPI_KEY=rapidapi_keyiniz
RAPIDAPI_HOSTS=yt-api.p.rapidapi.com
```

### "Downloader Service Unavailable" hatası

1. **Sunucu .env kontrolü** — `RAPIDAPI_HOSTS=yt-api.p.rapidapi.com` olmalı (social-download-all-in-one değil).
2. **Logları inceleyin** — `journalctl -u nouscript -f` ile hangi adımda hata verdiğini görün:
   - `[RapidAPI yt-api] Download 403` — googlevideo sunucu IP'sini engelliyor
   - `[RapidAPI yt-api] Got HTML instead of audio` — 403/engellenme
   - `[RapidAPI yt-api] FFmpeg: Invalid data` — indirilen veri geçersiz
3. **RapidAPI aboneliği** — yt-api için RapidAPI'de abonelik gerekli.
