#!/usr/bin/env bash
set -Eeuo pipefail

BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PIDS=()

if (( EUID == 0 )); then
    echo "اسکریپت را با کاربر nar و بدون sudo اجرا کن."
    exit 1
fi

for cmd in git uv npm setsid; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "دستور $cmd در PATH پیدا نشد."
        exit 1
    fi
done

cleanup() {
    trap - EXIT INT TERM

    if ((${#PIDS[@]} == 0)); then
        return
    fi

    echo
    echo "در حال توقف بک‌اند، فرانت‌اند و Celery..."
    echo "منتظر پایان کار فرایندها بمان."

    # ارسال SIGTERM به تمام اعضای گروه پردازشی هر سرویس
    for pid in "${PIDS[@]}"; do
        kill -TERM -- "-$pid" 2>/dev/null || true
    done

    wait 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'echo "خطا در خط $LINENO؛ اجرا متوقف شد." >&2' ERR

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

echo "========== اجرای فرانت‌اند =========="
cd "$BASE_DIR/raja-reserv-train"

setsid npm run start &
PIDS+=("$!")

echo
echo "هر سه سرویس اجرا شدند."
echo "برای توقف همه: Ctrl+C"
echo "PID اسکریپت: $$"

# اگر یکی از سرویس‌ها خارج شود، بقیه نیز متوقف می‌شوند.
set +e
wait -n "${PIDS[@]}"
STATUS=$?
set -e

echo "یکی از سرویس‌ها خارج شد؛ سایر سرویس‌ها متوقف می‌شوند."
exit "$STATUS"