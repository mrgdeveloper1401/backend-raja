#!/usr/bin/bash
set -Eeuo pipefail

# تابع: آزادسازی پورت (SIGKILL به هر پردازه‌ای که روی آن گوش می‌دهد)
free_port() {
    local port=$1
    set +e
    if command -v fuser >/dev/null 2>&1; then
        fuser -KILL "${port}/tcp" >/dev/null 2>&1
    elif command -v lsof >/dev/null 2>&1; then
        local pids
        pids=$(lsof -ti tcp:"${port}" 2>/dev/null)
        if [ -n "$pids" ]; then
            kill -9 $pids 2>/dev/null
        fi
    fi
    # صبر تا پورت واقعاً آزاد شود
    for _ in {1..10}; do
        if ! (echo >/dev/tcp/127.0.0.1/"${port}") 2>/dev/null; then
            break
        fi
        sleep 0.2
    done
    set -e
}

free_port 8000
free_port 5555
free_port 3000

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIDS=()

echo "========== آماده‌سازی بک‌اند =========="
cd "$BASE_DIR/backend-raja"

git pull --ff-only
uv sync
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py sync_stations

echo "========== آماده‌سازی فرانت‌اند =========="
cd "$BASE_DIR/raja-reserv-train"

git pull --ff-only
npm run build

echo "========== اجرای بک‌اند =========="
cd "$BASE_DIR/backend-raja"

setsid uv run python manage.py runbolt &
PIDS+=("$!")

echo "========== اجرای Celery =========="
setsid uv run celery -A core worker -l INFO &
PIDS+=("$!")

echo "========== اجرای flower =========="
setsid uv run celery -A core flower &
PIDS+=("$!")

echo "========== اجرای فرانت‌اند =========="
cd "$BASE_DIR/raja-reserv-train"

setsid npm run start &
PIDS+=("$!")

echo
echo "✅ هر سه سرویس اجرا شدند."
echo "برای توقف همه: Ctrl+C"
echo "PID اسکریپت: $$"

set +e
wait -n "${PIDS[@]}"
STATUS=$?
set -e

echo "یکی از سرویس‌ها خارج شد؛ سایر سرویس‌ها متوقف می‌شوند."
exit "$STATUS"