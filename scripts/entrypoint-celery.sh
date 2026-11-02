#!/bin/bash
set -e

# ۱. پاکسازی فایل‌های قفل احتمالی از اجرای قبلی
rm -f /tmp/.X99-lock

# ۲. ساخت مانیتور مجازی
Xvfb :99 -screen 0 1920x1080x24 &

# ⚠️ مکث کوتاه برای اطمینان از بالا آمدن Xvfb
sleep 5

# ۳. اجرای یک Window Manager بسیار سبک برای جابجایی پنجره‌ها
fluxbox &

# ۴. اجرای سرور VNC سبک
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &

# ۵. وب‌سوکت noVNC برای مشاهده از طریق مرورگر اینترنت
websockify --web=/usr/share/novnc 6080 localhost:5900 &

# ۶. اجرای ورکر سلری با صف اختصاصی booker
exec celery -A core worker -l INFO
