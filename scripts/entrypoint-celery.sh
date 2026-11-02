#!/bin/bash
set -e

# ۱. پاکسازی lock files
rm -f /tmp/.X99-lock
rm -f /app/raja_user_data/SingletonLock
rm -f /app/raja_user_data/SingletonSocket

# ۲. socket directory
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# ۳. Xvfb
Xvfb :99 -screen 0 1920x1080x24 -ac -noreset +extension GLX +render \
     2>&1 | tee /tmp/xvfb.log &

# ۴. صبر برای آماده شدن Xvfb
echo "Waiting for Xvfb..."
for i in $(seq 1 60); do
    DISPLAY=:99 xdpyinfo >/dev/null 2>&1 && echo "Xvfb ready (attempt $i)" && break
    [ "$i" -eq 60 ] && { echo "Xvfb failed to start!"; cat /tmp/xvfb.log; exit 1; }
    sleep 0.5
done

export DISPLAY=:99

# ۵. fluxbox
fluxbox 2>/dev/null &

# ۶. x11vnc روی پورت 5900 — بدون هیچ WebSocket flag
x11vnc -display :99 -forever -nopw -shared \
       -rfbport 5900 \
       -noxdamage -noscr -noxfixes -noipv6 \
       2>&1 | tee /tmp/x11vnc.log &

# ۷. صبر برای آماده شدن x11vnc
sleep 2

# ۸. websockify به عنوان bridge: 6080 → localhost:5900
websockify --web=/usr/share/novnc \
           --heartbeat=30 \
           6080 localhost:5900 \
           2>&1 | tee /tmp/websockify.log &

# ۹. Celery worker
exec celery -A core worker -l INFO -Q celery,booker
