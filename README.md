# 🎵 Audoix (@audio_uz_bot) — Telegram Musiqa va Media Boti

**Audoix** — Telegramdagi eng zamonaviy, xatosiz, o'ta tezkor asinxron musiqa qidiruv, audio aniqlash (Shazam) va ijtimoiy tarmoqlardan media yuklovchi professional bot.

---

## ✨ Bot Xususiyatlari

1. **🎵 Qo'shiq nomi, ijrochi yoki qo'shiq matni (lyrics) bo'yicha qidirish:**
   - Har qanday matn yozsangiz, bot eng mos 5 ta musiqani raqamli tugmalar bilan chiqaradi.
   - Tanlangan musiqa bir necha soniyada yuqori sifatli MP3 holatida jo'natiladi.
2. **🎙 Ovozli xabar, video va videoxabarlardan musiqa aniqlash (Shazam):**
   - Ovozli xabar (voice), video, dumaloq video (kruglyash / video_note) yoki audio fayl yuborilganda qo'shiqni aniqlaydi va to'liq variantini topib beradi.
3. **🔗 Ijtimoiy tarmoqlardan video va musiqa yuklash:**
   - Instagram (Reels, Post), TikTok (suv belgisiz), YouTube / Shorts, Pinterest, Twitter havolalari yuborilganda videoni va uning musiqasini MP3 qilib yuklab beradi.
4. **⚡️ SQLite Kesh Tizimi (Ultra-Fast):**
   - Bir marta yuklangan har qanday qo'shiq yoki video bazada saqlanadi. Keyingi safar xuddi shu musiqa so'ralganda internetdan qayta yuklanmasdan **0.1 soniyada** yuboriladi!
5. **👥 Admin paneli:**
   - `/stats` — Bot foydalanuvchilari va keshdagi musiqalar soni.
   - `/broadcast <xabar>` — Barcha bot a'zolariga xabar yuborish.

---

## 🐙 Loyihani GitHubga Yuklash (Git Qo'llanmasi)

Loyihani o'zingizning GitHub hisobingizga yuklash uchun quyidagi ketma-ketlikni bajaring:

### 1-qadam: GitHub'da yangi Repository oching
1. [github.com](https://github.com) ga kiring va **New repository** tugmasini bosing.
2. Repositoriyga nom bering (masalan: `audoix-music-bot`).
3. **Public** yoki **Private** tanlang va **Create repository** tugmasini bosing.

### 2-qadam: Terminalda buyruqlarni bajaring
Kompyuteringiz terminalida ushbu papkaga kiring va buyruqlarni ketma-ket yozing:

```bash
cd C:\Users\USER\.gemini\antigravity-ide\scratch\xits-music-bot

git init
git add .
git commit -m "feat: initial commit of audoix telegram music bot"
git branch -M main
git remote add origin https://github.com/SIZNING_GITHUB_USERNAME/audoix-music-bot.git
git push -u origin main
```

*(Eslatma: `.gitignore` fayli sozlangan, shuning uchun `.env` faylidagi maxfiy bot tokeningiz GitHubga tushmaydi va xavfsiz qoladi).*

---

## 🚀 Serverda (Linux VPS) 24/7 Ishga Tushirish

Serverda 1-klikda avtomatik o'rnatish:
```bash
git clone https://github.com/SIZNING_GITHUB_USERNAME/audoix-music-bot.git
cd audoix-music-bot
cp .env.example .env
nano .env   # Bot tokeningizni yozing
chmod +x setup_server.sh
./setup_server.sh
```

---

## 📁 Loyiha Tuzilishi

```
audoix-music-bot/
├── config.py                 # Bot konfiguratsiyasi va FFmpeg sozlamalari
├── database.py               # SQLite ma'lumotlar bazasi va kesh tizimi
├── main.py                   # Botni ishga tushiruvchi asosiy fayl
├── requirements.txt          # Python kutubxonalari
├── run.bat                   # Windows uchun 1-klikda ishga tushirish fayli
├── setup_server.sh           # Linux VPS 1-klikda o'rnatish skripti
├── Dockerfile                # Docker sozlamalari
├── docker-compose.yml        # Docker compose fayli
├── .gitignore                # Git maxfiylik filtri
├── .env.example              # Namuna konfiguratsiya
│
├── handlers/                 # Buyruq va xabarlar
│   ├── start.py              # /start va /help
│   ├── text_search.py        # Qo'shiq qidirish va yuklash
│   ├── media_shazam.py       # Ovoz va videodan musiqa topish
│   ├── downloader.py         # Instagram/TikTok/YouTube yuklovchi
│   └── admin.py              # Admin buyruqlari (/stats, /broadcast)
│
├── services/                 # Asosiy xizmatlar
│   ├── music_service.py      # Musiqa qidirish va MP3 konvertatsiya
│   ├── recognition_service.py# Ovozdan qo'shiqni aniqlash
│   ├── downloader_service.py # Ijtimoiy tarmoq video yuklash
│   └── ffmpeg_helper.py      # FFmpeg audio qayta ishlash
│
└── utils/                    # Tugmalar va yordamchilar
    └── keyboards.py          # O'zbekcha tugmalar
```
