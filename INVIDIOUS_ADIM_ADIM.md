# Invidious Kurulumu — Adım Adım Rehber

Her adımı sırayla yap. Bir adım bitmeden diğerine geçme.

---

## Adım 1: Sunucuya Bağlan

**Ne yapıyorsun:** Bilgisayarından sunucuna uzaktan bağlanıyorsun.

1. Bilgisayarında **PowerShell** veya **CMD** aç
2. Şu komutu yaz (IP adresini kendi sunucunla değiştir):

```
ssh root@187.124.91.33
```

3. Enter'a bas
4. İlk seferde "Are you sure..." diye sorarsa `yes` yaz, Enter
5. Şifre sorarsa sunucu şifreni yaz (yazarken görünmez, normal)
6. `root@...` benzeri bir satır görüyorsan bağlandın

---

## Adım 2: Docker Kurulumu

**Ne yapıyorsun:** Docker'ın kurulu olup olmadığını kontrol edip, yoksa kuruyorsun.

1. Şu komutu yaz ve Enter'a bas:

```
docker --version
```

2. **Eğer** "command not found" veya benzeri hata görürsen, sırayla şunları yaz:

```
apt update
```

Enter, bekle. Sonra:

```
apt install -y docker.io docker-compose
```

Enter, bekle. Sonra:

```
systemctl enable docker
```

Enter. Sonra:

```
systemctl start docker
```

Enter.

3. **Eğer** `docker --version` bir sürüm numarası gösterdiyse (örn. Docker version 24.0.7), Docker zaten kurulu. Bir sonraki adıma geç.

---

## Adım 3: Invidious Klasörü ve Veritabanı Şeması

**Ne yapıyorsun:** Invidious için klasör oluşturup veritabanı tablolarını (config/sql) indiriyorsun.

1. Klasör oluştur ve Invidious repo'sunu geçici olarak klonla:

```
mkdir -p /opt/invidious
cd /opt/invidious
git clone --depth 1 https://github.com/iv-org/invidious.git invidious-tmp
```

2. config/sql ve init script'i kopyala:

```
cp -r invidious-tmp/config ./
mkdir -p docker
cp invidious-tmp/docker/init-invidious-db.sh docker/
rm -rf invidious-tmp
```

3. `config/sql` ve `docker/init-invidious-db.sh` dosyaları hazır olmalı.

---

## Adım 4: docker-compose.yml Dosyası Oluştur

**Ne yapıyorsun:** Invidious için ayar dosyasını oluşturuyorsun.

1. Şu komutu yaz ve Enter'a bas (ilk satır):

```
nano docker-compose.yml
```

2. Sunucuda iki rastgele anahtar üret (SSH oturumunda):

```
openssl rand -hex 16
```
İlk çıktıyı kopyala → `HMAC_ANAHTARINI_BURAYA_YAPIŞTIR` yerine yapıştır.

```
openssl rand -hex 16
```
İkinci çıktıyı kopyala → `COMPANION_ANAHTARINI_BURAYA_YAPIŞTIR` yerine yapıştır.

3. Açılan metin editöründe **hiçbir şey silmeden** aşağıdaki metni **tamamen** kopyala ve yapıştır. Anahtarları değiştir:

```yaml
version: "3"
services:
  inv_db:
    image: postgres:14
    volumes:
      - ./dbdata:/var/lib/postgresql/data
      - ./config/sql:/config/sql
      - ./docker/init-invidious-db.sh:/docker-entrypoint-initdb.d/init-invidious-db.sh
    environment:
      - POSTGRES_DB=invidious
      - POSTGRES_USER=kutsal
      - POSTGRES_PASSWORD=nouscript
  invidious:
    image: quay.io/invidious/invidious:latest
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      INVIDIOUS_DATABASE_URL: postgres://kutsal:nouscript@inv_db:5432/invidious
      INVIDIOUS_CONFIG: |
        hmac_key: "HMAC_ANAHTARINI_BURAYA_YAPIŞTIR"
        invidious_companion:
          - private_url: "http://companion:8282/companion"
        invidious_companion_key: "COMPANION_ANAHTARINI_BURAYA_YAPIŞTIR"
    depends_on:
      - inv_db
    restart: always
  companion:
    image: quay.io/invidious/invidious-companion:latest
    environment:
      SERVER_SECRET_KEY: "COMPANION_ANAHTARINI_BURAYA_YAPIŞTIR"
    restart: always
    volumes:
      - companioncache:/var/tmp/youtubei.js:rw
volumes:
  companioncache:
```

4. **Değiştirmen gereken yerler (istersen):**
   - `kutsal` = veritabanı kullanıcı adı
   - `nouscript` = veritabanı şifresi
   - `HMAC_ANAHTARINI_BURAYA_YAPIŞTIR` = 1. anahtar (openssl rand -hex 16)
   - `COMPANION_ANAHTARINI_BURAYA_YAPIŞTIR` = 2. anahtar (Invidious ve companion'da aynı olmalı)

4. Kaydetmek için: `Ctrl+O` → Enter → `Ctrl+X`

---

## Adım 5: Invidious'u Başlat

**Ne yapıyorsun:** Docker ile Invidious'u çalıştırıyorsun.

1. Hâlâ `/opt/invidious` klasöründe olduğundan emin ol. Değilsen:

```
cd /opt/invidious
```

2. Şu komutu yaz:

```
docker-compose up -d
```

3. Enter
4. İlk seferde 1–2 dakika sürebilir (görüntüler indirilir)
5. "done" veya "Started" benzeri bir şey görünce bitti

---

## Adım 6: Çalışıyor mu Kontrol Et

**Ne yapıyorsun:** Invidious'un düzgün ayağa kalktığını kontrol ediyorsun.

**Önemli:** Bu komutu **sunucudaki SSH oturumunda** çalıştır (kendi bilgisayarında değil). SSH ile bağlıyken terminal sunucunun terminalidir; `localhost` = sunucunun kendisi.

1. SSH oturumunda (hâlâ sunucudasın) şu komutu yaz:

```
curl -s http://localhost:3000/api/v1/stats
```

2. Enter
3. **Eğer** uzun bir JSON metni görüyorsan → Başarılı
4. **Eğer** "Connection refused" veya boş cevap görüyorsan → Bir sorun var, Adım 5'i tekrarla veya `docker ps` ile container'ları kontrol et

---

## Adım 7: NouScript'i Güncelle

**Ne yapıyorsun:** NouScript'in Invidious'u kullanması için kodu ve bağımlılıkları güncelliyorsun.

1. NouScript klasörüne geç:

```
cd /opt/nouscript
```

2. Son kodları al:

```
git pull
```

3. Sanal ortamı aktif et:

```
source venv/bin/activate
```

4. httpx kur:

```
pip install httpx
```

5. Servisi yeniden başlat:

```
systemctl restart nouscript
```

6. Enter

---

## Adım 8: Test Et

**Ne yapıyorsan:** YouTube linkiyle NouScript'i deniyorsun.

1. Tarayıcıda NouScript sitesini aç (örn. http://187.124.91.33 veya domain adresin)
2. Bir YouTube linki yapıştır (örn. https://www.youtube.com/watch?v=dQw4w9WgXcQ)
3. Process'e tıkla
4. Özet veya altyazı gelirse kurulum tamam

---

## Sorun Çıkarsa

**"relation videos does not exist" hatası:**
Veritabanı tabloları oluşturulmamış. Adım 3'ü (config/sql ve init script) yaptıktan sonra veritabanını sıfırlayıp yeniden başlat:

```
cd /opt/invidious
docker-compose down
rm -rf dbdata
docker-compose up -d
```

**Invidious başlamıyorsa:**
```
cd /opt/invidious
docker-compose logs
```
Çıktıyı incele, hata mesajı var mı bak.

**NouScript hâlâ "Sign in" hatası veriyorsa:**
- Invidious çalışıyor mu: `curl -s http://localhost:3000/api/v1/stats`
- NouScript yeniden başlatıldı mı: `systemctl restart nouscript`
- Loglara bak: `journalctl -u nouscript -n 30`
