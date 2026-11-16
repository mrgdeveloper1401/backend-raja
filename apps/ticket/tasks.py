# apps/ticket/tasks.py
import asyncio

import jdatetime
from celery import shared_task

from .booker import RajaBooker
from .models import Reservation, ReservationAttempt


@shared_task(queue="booker", time_limit=3600)
def run_attempt_task(attempt_id):
    attempt = (
        ReservationAttempt.objects.select_related(
            "reservation",
            "reservation__order",
            "reservation__raja_account",
        )
        .prefetch_related(
            "reservation__order__order_passenger__passenger",
        )
        .get(id=attempt_id)
    )

    # get reservation
    reservation = attempt.reservation

    # تبدیل تاریخ میلادی دیتابیس به شمسی برای ربات
    travel_date_jalali = jdatetime.date.fromgregorian(
        date=reservation.order.travel_date
    ).strftime("%Y-%m-%d")

    to_date = (
        reservation.order.to_date
        if reservation.order.trip_type == "outbound_and_return"
        else None
    )
    to_date_jalali = None
    if to_date:
        to_date_jalali = jdatetime.date.fromgregorian(date=to_date).strftime("%Y-%m-%d")

    # آماده‌سازی اطلاعات مسافران
    passengers_data = []
    for link in reservation.order.order_passenger.all():
        passenger = link.passenger
        birth = None
        if passenger.birth_date:
            birth = jdatetime.date.fromgregorian(date=passenger.birth_date).strftime(
                "%Y/%m/%d"
            )
        passengers_data.append(
            {
                "first_name": passenger.first_name,
                "last_name": passenger.last_name,
                "national_id": passenger.national_id,
                "birth_date": birth,
                "is_adult": passenger.is_adult,
            }
        )

    booker = RajaBooker(
        account_id=reservation.raja_account_id,
        origin=reservation.order.origin,
        destination=reservation.order.destination,
        travel_date=travel_date_jalali,
        passengers=passengers_data,
        headless=False,  # در سرور True شود
        attempt_id=attempt.id,
        travel_phone=reservation.phone,
        is_want_and_return=reservation.order.trip_type == "outbound_and_return",
        is_exclusive=reservation.is_exclusive,
        to_date=to_date_jalali,
        passenger_type=reservation.order.passenger_type,
        coupe_filter=reservation.coupe_type,
        from_price=reservation.from_price,
        to_price=reservation.to_price,
        train_number=reservation.train_number,
    )

    return asyncio.run(booker.start())


@shared_task(queue="qu")
def process_reservation_task(reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        return "رزرو پیدا نشد"

    attempt = ReservationAttempt.objects.filter(reservation_id=reservation.id).last()
    task = run_attempt_task.delay(attempt.id)
    attempt.celery_task_id = task.id
    attempt.save(update_fields=["celery_task_id", "updated_at"])

    return f"attempts started {reservation_id}"
