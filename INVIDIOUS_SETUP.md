# Invidious Kurulumu (187.124.91.33)

YouTube videoları için cookie gerektirmeyen Invidious kurulumu.

---

## 1. Sunucuya Bağlan

```bash
ssh root@187.124.91.33
```

---

## 2. Docker Kur (yoksa)

```bash
apt update && apt install -y docker.io docker-compose
systemctl enable docker
systemctl start docker
```

---

## 3. Invidious Klasörü ve docker-compose

```bash
mkdir -p /opt/invidious
cd /opt/invidious
nano docker-compose.yml
```

İçeriği yapıştır:

```yaml
version: "3"
services:
  inv_db:
    image: postgres:14
    volumes:
      - ./dbdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=invidious
      - POSTGRES_USER=kutsal
      - POSTGRES_PASSWORD=nouscript

  invidious:
    image: quay.io/invidious/invidious:latest
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - INVIDIOUS_DATABASE_URL=postgres://kutsal:nouscript@inv_db:5432/invidious
    depends_on:
      - inv_db
    restart: always
```

**Not:** `127.0.0.1:3000` — Sadece localhost'tan erişilebilir (güvenlik). NouScript aynı sunucuda olduğu için `localhost:3000` ile bağlanır.

Kaydet: `Ctrl+O` → Enter → `Ctrl+X`

---

## 4. Başlat

```bash
cd /opt/invidious
docker-compose up -d
```

İlk çalıştırmada veritabanı oluşturulur, 1–2 dakika sürebilir.

---

## 5. Kontrol

```bash
docker ps
curl -s http://localhost:3000/api/v1/stats
```

`curl` JSON dönerse Invidious çalışıyordur.

---

## 6. NouScript .env (opsiyonel)

Invidious farklı portta veya host'taysa:

```bash
nano /opt/nouscript/.env
```

Ekle:
```
INVIDIOUS_URL=http://localhost:3000
```

---

## 7. NouScript'i Yeniden Başlat

```bash
cd /opt/nouscript
pip install httpx
systemctl restart nouscript
```

---

## Özet

| Bileşen | Adres |
|---------|-------|
| Invidious | http://localhost:3000 (sadece sunucu içi) |
| NouScript | Invidious'a localhost üzerinden bağlanır |

YouTube linkleri artık cookie olmadan çalışmalı.
