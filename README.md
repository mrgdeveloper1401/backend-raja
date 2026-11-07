# 🚂 Raja Ticket Reservation System (reserv-ticket-raja)

سیستم هوشمند، خودکار و پرسرعت برای مانیتورینگ، رزرو و خرید بلیط قطار رجا، مجهز به ابزارهای دور زدن سیستم‌های ضدبات، تسک‌های پس‌زمینه و مدیریت همزمان درخواست‌ها.

---

## 🛠️ تکنولوژی‌ها و پکیج‌های کلیدی (Tech Stack)

این پروژه با یک استک مدرن و بهینه برای اسکرپینگ و پردازش‌های همزمان توسعه یافته است:

- **هسته وب:** Django + Django Bolt
- **دیتابیس:** PostgreSQL (به همراه درایور پرسرعت `psycopg` با Connection Pooling)
- **صف و تسک‌های پس‌زمینه:** Celery + Redis (به همراه `hiredis` و `msgpack` برای حداکثر سرعت)
- **زمان‌بندی دقیق:** APScheduler (برای استارت دقیق تسک‌ها در لحظه باز شدن فروش بلیط)
- **اتوماسیون و دور زدن ضدبات (Anti-Bot):** 
  - `patchright` & `playwright` (کنترل مرورگر بدون لو رفتن فرستادن سیگنال‌های اتوماسیون)
  - `humanization-playwright` (شبیه‌سازی حرکت طبیعی موس و رفتار انسانی)
  - `pypasser[all,speech]` (حل خودکار صوتی کپچاها)
- **شبکه و پایداری:** `httpx` (Async HTTP) و `tenacity` (سیستم Retry هوشمند برای خطاهای شبکه)
- **ابزارهای توسعه:** IPython, IPDB, Django Debug Toolbar, jdatetime (تاریخ شمسی)

---

## ⚙️ پیش‌نیازهای نصب (Prerequisites)

- پایتون نسخه ۳.۱۴ یا بالاتر
- `uv` (مدیریت پکیج و محیط مجازی فوق‌العاده سریع)
- دیتابیس PostgreSQL و سرور Redis فعال روی سیستم

---

## 📥 راه‌اندازی سریع پروژه (Quick Start)

### ۱. کلون کردن و ورود به دایرکتوری پروژه
```bash
git clone https://github.com/mrgdeveloper1401/backend-raja.git
cd reserv-ticket-raja
```
---

### اجرای پروژه
```bash
uv init -p 3.14
 uv add -r requirements.txt --default-index=https://package-mirror.liara.ir/repository/pypi/simple
```
