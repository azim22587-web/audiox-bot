# 🌐 audoix Botni Serverga (Linux VPS / Cloud) 24/7 Joylashtirish Qo'llanmasi

Bot doimiy (24/7) to'xtovsiz, o'ta tez va xatolarsiz ishlashi uchun uni **Linux VPS serverga** (masalan, Ubuntu 22.04 / 24.04) joylashtirish eng to'g'ri va professional usuldir.

---

## 1-USUL: Linux VPS Serverda Ishga Tushirish (Tavsiya etiladi ⭐️)

Istalgan arzon VPS serverdan (masalan: [Hetzner](https://www.hetzner.com), [Timeweb Cloud](https://timeweb.cloud), [VDSina](https://vdsina.ru), [DigitalOcean](https://digitalocean.com)) **Ubuntu 22.04 yoki 24.04** tizimli server oling (oyiga $2 - $4 bo'ladi).

### 1-qadam: Serverga ulanish (SSH orqali)
Kompyuteringiz terminalida (yoki PuTTY dasturida):
```bash
ssh root@SERVER_IP_MANZILINGIZ
```

### 2-qadam: Bot fayllarini serverga yuklash
Fayllarni GitHub orqali yoki to'g'ridan-to'g'ri serverga yuklang:
```bash
git clone SIZNING_GITHUB_REPO_LINKINGIZ
cd audoix-music-bot
```

yoki serverda yangi papka ochib:
```bash
mkdir audoix-music-bot && cd audoix-music-bot
```

### 3-qadam: `.env` faylini sozlash
Serverda `.env` faylini ochib tokeningizni kiriting:
```bash
nano .env
```
Fayl ichiga:
```env
BOT_TOKEN=8512907281:AAElcCU-vTvw-FHsZf-bHxYuTWumJI4VP58
ADMIN_IDS=SIZNING_TELEGRAM_ID
AUDD_API_KEY=
```
Saqlash uchun: `Ctrl + O`, `Enter` va chiqish uchun `Ctrl + X`.

### 4-qadam: 1-Klikda avtomatik o'rnatish
Skriptga ruxsat bering va bajaring:
```bash
chmod +x setup_server.sh
./setup_server.sh
```

Barcha ishlar (Python, FFmpeg, kutubxonalar, SQLite va 24/7 `systemd` avtomatik servis) avtomatik o'rnatiladi va ishga tushadi!

---

## 🛠 Serverdagi Asosiy Buyruqlar

- **Bot holatini ko'rish**:
  ```bash
  sudo systemctl status audoix
  ```
- **Botni qayta ishga tushirish**:
  ```bash
  sudo systemctl restart audoix
  ```
- **Botni to'xtatish**:
  ```bash
  sudo systemctl stop audoix
  ```
- **Jonli loglarni (xatolar va so'rovlarni) ko'rish**:
  ```bash
  sudo journalctl -u audoix -f
  ```

---

## 2-USUL: Docker orqali ishga tushirish (Ixtiyoriy)

Agar serveringizda Docker o'rnatilgan bo'lsa:
```bash
docker compose up -d --build
```
Loglarni ko'rish:
```bash
docker compose logs -f
```
