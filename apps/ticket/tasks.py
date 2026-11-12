# apps/ticket/tasks.py
import asyncio
import sys

import jdatetime
from celery import shared_task

from .booker import RajaBooker
from .models import Reservation, ReservationAttempt, Restitution
from .restitution import RestitutionTicket


def _configure_event_loop_for_platform():
    """
    اطمینان از استفاده از Event Loop سازگار با subprocess.

    - در ویندوز: تلاش برای تنظیم ProactorEventLoop (که از subprocess پشتیبانی می‌کند).
    - در لینوکس: نیازی به تنظیم نیست (SelectorEventLoop پیش‌فرض از subprocess پشتیبانی می‌کند).
    """
    if sys.platform == "win32":
        # در Python 3.14 تنظیم policy منسوخ شده است، اما اگر در دسترس باشد
        # به‌عنوان یک لایه اطمینان اضافی از آن استفاده می‌کنیم.
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError, DeprecationWarning:
            # در Python 3.14+ این policy ممکن است deprecated یا حذف شده باشد.
            # در این حالت به رفتار پیش‌فرض ویندوز (که Proactor است) تکیه می‌کنیم.
            pass


@shared_task(queue="booker", time_limit=3600)
def run_attempt_task(attempt_id):
    attempt = ReservationAttempt.objects.select_related(
        "reservation__order__passenger"
    ).get(id=attempt_id)
    reservation = attempt.reservation

    # تبدیل تاریخ میلادی دیتابیس به شمسی برای ربات
    travel_date_jalali = jdatetime.date.fromgregorian(
        date=reservation.order.travel_date
    ).strftime("%Y-%m-%d")

    birth_date_jalali = jdatetime.date.fromgregorian(
        date=reservation.order.passenger.birth_date
    ).strftime("%Y/%m/%d")

    to_date = (
        reservation.order.to_date
        if reservation.order.trip_type == "outbound_and_return"
        else None
    )
    to_date_jalali = None
    if to_date:
        to_date_jalali = jdatetime.date.fromgregorian(date=to_date).strftime("%Y-%m-%d")

    # آماده‌سازی اطلاعات مسافران
    passengers_data = [
        {
            "first_name": reservation.order.passenger.first_name,
            "last_name": reservation.order.passenger.last_name,
            "national_id": reservation.order.passenger.national_id,
            "gender": reservation.order.passenger.gender,
            "birth_date": birth_date_jalali,
            "is_adult": True,
        }
    ]

    booker = RajaBooker(
        account_id=reservation.raja_account_id,
        origin=reservation.order.origin,
        destination=reservation.order.destination,
        travel_date=travel_date_jalali,
        passengers=passengers_data,
        headless=False,  # در سرور True شود
        attempt_id=attempt.id,
        travel_phone=reservation.order.passenger.phone,
        is_want_and_return=reservation.order.trip_type == "outbound_and_return",
        to_date=to_date_jalali,
        passenger_type=reservation.order.passenger_type,
        coupe_filter=reservation.coupe_type,
        order_by_filter=reservation.order_by,
    )

    # تنظیم Event Loop مناسب قبل از اجرای کد async
    _configure_event_loop_for_platform()

    return asyncio.run(booker.start())


@shared_task(queue="qu")
def process_reservation_task(reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        return "رزرو پیدا نشد"

    attempt = ReservationAttempt.objects.create(reservation_id=reservation.id)
    task = run_attempt_task.delay(attempt.id)

    attempt.celery_task_id = task.id
    attempt.save(update_fields=["celery_task_id", "updated_at"])

    return f"attempts started {reservation_id}"


@shared_task(queue="restitution")
def run_restitution_task(restitution_id):
    try:
        obj = Restitution.objects.get(id=restitution_id)
    except Reservation.DoesNotExist:
        return "استرداد پیدا نشد"

    # تنظیم Event Loop مناسب قبل از اجرای کد async
    # for windows
    _configure_event_loop_for_platform()

    restitution_ticket = RestitutionTicket(
        serial=obj.serial_number,
        phone=obj.phone,
        hall_number=obj.hall_number,
        account_id=obj.raja_account_id,
        restitution_id=obj.id,
        train_number=obj.train_number,
    )
    return asyncio.run(restitution_ticket.start())
