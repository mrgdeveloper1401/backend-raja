# apps/ticket/tasks.py
import asyncio

import jdatetime
from celery import shared_task, group
from .booker import RajaBooker
from .models import Reservation, ReservationAttempt


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
        headless=False,  # در سرور True بشه
        attempt_id=attempt.id,
        # reservation_id=reservation.id,  # آیدی رزرو رو پاس می‌دیم تا وضعیتش رو آپدیت کنه
        travel_phone=reservation.order.passenger.phone,
        is_want_and_return=reservation.order.trip_type == "outbound_and_return",
        to_date=to_date_jalali,
        passenger_type=reservation.order.passenger_type,
        coupe_filter=reservation.coupe_type,
        order_by_filter=reservation.order_by,
    )

    return asyncio.run(booker.start())


@shared_task(queue="qu")
def process_reservation_task(reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        return "رزرو پیدا نشد"

    # reservation attempt
    # count = reservation.number_reservation
    attempt = ReservationAttempt.objects.create(reservation_id=reservation.id)
    # ارسال تسک به صف booker
    task = run_attempt_task.delay(attempt.id)

    # ذخیره شناسه تسک در دیتابیس
    attempt.celery_task_id = task.id
    attempt.save(update_fields=["celery_task_id", "updated_at"])

    return f"attempts started {reservation_id}"
