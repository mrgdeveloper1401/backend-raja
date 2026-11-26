#!/usr/bin/bash
set -Eeuo pipefail

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