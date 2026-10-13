# 🚀 audoix Botni Render.com (Bepul) Serverga 24/7 Joylashtirish Qo'llanmasi

Ushbu qo'llanma orqali botingizni [Render.com](https://render.com) orqali **100% bepul** va **24/7 uhlamaydigan** qilib ishga tushirishingiz mumkin.

---

## 1-QADAM: GitHub'ga Repozitoriy Yuklash
1. [github.com/new](https://github.com/new) manziliga o'ting.
2. Repozitoriy nomi: `audoix-bot` (Public yoki Private).
3. Loyihadagi barcha fayllarni GitHub'ga yuklang (upload files).

---

## 2-QADAM: Render.com da Yangi Servis Yaratish
1. [Render.com](https://dashboard.render.com) ga kiring va **"New +"** -> **"Web Service"** tugmasini bosing.
2. **"Build and deploy from a Git repository"** ni tanlang.
3. GitHub hisobingizni ulab, `audoix-bot` repozitoriyingizni tanlang (**Connect**).

---

## 3-QADAM: Sozlamalarni To'ldirish

* **Name:** `audoix-bot`
* **Region:** `Frankfurt (EU Central)` yoki `Singapore`
* **Branch:** `main` (yoki `master`)
* **Runtime:** `Docker` *(Bizning loyihamizda tayyor Dockerfile bor, u FFmpeg va barcha kerakli dasturlarni avtomatik o'rnatadi)*
* **Instance Type:** `Free` (bepul)

### Environment Variables (Muhit O'zgaruvchilari):
Quyidagi tugmani bosing: **"Add Environment Variable"** va qo'shing:
* **`BOT_TOKEN`** = `8512907281:AAElcCU-vTvw-FHsZf-bHxYuTWumJI4VP58`
* **`ADMIN_USERNAME`** = `KF_AZIM`
* **`PORT`** = `10000`

So'ngra sahifa pastidagi **"Deploy Web Service"** (yoki "Create Web Service") tugmasini bosing!

---

## 4-QADAM: Botni 24/7 Uhlamaydigan Qilish (Anti-Sleep) ⚡️

Render bepul tarifda 15 daqiqa davomida so'rov kelmasa servisni "uhlatib" qo'yadi. 
Buning oldini olish va **24/7 to'xtovsiz ishlashi uchun**:

1. Render bergan sayt havolasini nusxalang (masalan: `https://audoix-bot.onrender.com`).
2. [cron-job.org](https://cron-job.org) yoki [uptimerobot.com](https://uptimerobot.com) saytiga bepul ro'yxatdan o'ting.
3. Yangi monitor (yoki cron job) qo'shing:
   * **URL:** `https://audoix-bot.onrender.com/` (yoki `/health`)
   * **Interval:** Har 5 daqiqada (Every 5 minutes)
4. Saqlang!

Endi bu xizmat har 5 daqiqada Render'ga ping berib turadi va botingiz **hech qachon uhlamaydi, 24/7 faol turadi**!
