# apps/ticket/tasks.py
import asyncio
import jdatetime
from celery import shared_task
from .booker import RajaBooker
from .models import Reservation


@shared_task(queue="booker", time_limit=36000)
def process_reservation_task(reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        return "رزرو پیدا نشد"

    # تبدیل تاریخ میلادی دیتابیس به شمسی برای ربات
    travel_date_jalali = jdatetime.date.fromgregorian(
        date=reservation.order.travel_date
    ).strftime("%Y-%m-%d")
    birth_date_jalali = jdatetime.date.fromgregorian(
        date=reservation.order.passenger.birth_date
    ).strftime("%Y/%m/%d")

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
        reservation_id=reservation.id,  # آیدی رزرو رو پاس می‌دیم تا وضعیتش رو آپدیت کنه
        travel_phone=reservation.order.passenger.phone,
    )

    # چون سلری سینک هست، یه لوپ جدید می‌سازیم
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(booker.start())
    finally:
        loop.close()
