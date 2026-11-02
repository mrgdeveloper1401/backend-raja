#!/bin/bash
set -e

# ۱. ساخت مانیتور مجازی
Xvfb :99 -screen 0 1920x1080x24 &

# ۲. اجرای یک Window Manager بسیار سبک برای جابجایی پنجره‌ها
fluxbox &

# ۳. اجرای سرور VNC سبک
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 &

# ۴. وب‌سوکت noVNC برای مشاهده از طریق مرورگر اینترنت
websockify --web=/usr/share/novnc 6080 localhost:5900 &

# ۵. اجرای ورکر سلری با صف اختصاصی booker
exec celery -A core worker -l INFO
