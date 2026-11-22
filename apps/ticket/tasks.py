# apps/ticket/tasks.py
import asyncio
from datetime import timedelta

import httpx
import jdatetime
from celery import shared_task
from django.utils import timezone
from fake_useragent import UserAgent

from .booker import RajaBooker
from .models import Reservation, ReservationAttempt
from ..core.models import RajaApiKey
from ..user.models import RajaAccount


TOKEN_REFRESH_MARGIN = timedelta(seconds=60)


# request into site
def login_user(username: str, password: str):
    user_agent = UserAgent().chrome
    url = "https://hostservice.raja.ir/token?ArCaptchaToken=undefined"
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.raja.ir",
    }
    data = {
        "username": username,
        "password": password,
        "grant_type": "password",
    }
    response = httpx.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()
    else:
        return None


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

    # raja api key
    raja_api_jey = RajaApiKey.objects.select_related("raja_account").last()

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
        adult=reservation.adult_number,
        child=reservation.baby_number,
        user_agent=attempt.user_agent,
        raja_api_key=raja_api_jey.api_key,
        access_token=raja_api_jey.raja_account.access_token,
        departure_time_slots=reservation.departure_time_slots,
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


@shared_task(queue="qu")
def login_user_task(raja_account_id):
    account = RajaAccount.objects.get(pk=raja_account_id)

    if (
        account.access_token
        and account.token_expires_at is not None
        and account.token_expires_at > timezone.now() + TOKEN_REFRESH_MARGIN
    ):
        return "skipped"

    res = login_user(account.username, account.password)
    received_at = timezone.now()

    if not res or not res.get("access_token"):
        raise ValueError("Raja login did not return an access token")

    expires_in = int(res["expires_in"])  # نام واقعی کلید در پاسخ API

    account.access_token = res["access_token"]
    account.expire_token = expires_in
    account.token_expires_at = received_at + timedelta(seconds=expires_in)
    account.save(update_fields=["access_token", "expire_token", "token_expires_at"])

    return "refreshed"
