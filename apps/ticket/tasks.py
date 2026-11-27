# apps/ticket/tasks.py
import asyncio
from datetime import timedelta

import httpx
import jdatetime
from celery import shared_task
from django.utils import timezone
from fake_useragent import UserAgent

from core.settings import (
    TOKEN_REFRESH_MARGIN,
    RAJA_CONFIG_URL,
    RAJA_SITE,
    RAJA_FRONT_API_KEY,
)
from .booker import RajaBooker
from .models import Reservation, ReservationAttempt
from ..core.models import RajaConfig
from ..user.models import RajaAccount


# request into site
def login_user(username: str, password: str):
    url = "https://hostservice.raja.ir/token?ArCaptchaToken=undefined"
    headers = {
        "Accept": "application/json",
        "User-Agent": UserAgent().chrome,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": RAJA_SITE,
        "Referer": RAJA_SITE,
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


# request into site
def get_information(raja_api_key, access_token):
    url = "https://hostservice.raja.ir/Api/ServiceProvider/GetInformation"
    headers = {
        "accept": "application/json",
        "api-key": raja_api_key,
        "Authorization": f"bearer {access_token}",
        "content-type": "application/json",
        "Origin": RAJA_SITE,
        "Referer": RAJA_SITE,
        "user-agent": UserAgent().chrome,
    }
    response = httpx.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def get_raja_config():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": RAJA_SITE,
        "Referer": RAJA_SITE,
    }
    res = httpx.get(RAJA_CONFIG_URL, headers=headers, timeout=30)
    res.raise_for_status()
    return res.json()


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
    raja_account = attempt.reservation.raja_account

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
        headless=False,
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
        access_token=raja_account.access_token,
        lg_uf=raja_account.user_information,
        departure_time_slots=reservation.departure_time_slots,
        decrypt_url=attempt.decrypt_url,
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
    """task for login before reservation"""
    account = RajaAccount.objects.get(pk=raja_account_id)

    # check expire access_token
    if (
        account.access_token
        and account.token_expires_at is not None
        and account.token_expires_at > timezone.now() + TOKEN_REFRESH_MARGIN
    ):
        return "skipped"

    # new request
    res = login_user(account.username, account.password)

    received_at = timezone.now()

    if not res or not res.get("access_token"):
        raise ValueError(
            "Raja login did not return an access token, please reright this logic"
        )

    expires_in = int(res["expires_in"])

    account.access_token = res["access_token"]
    account.expire_token = expires_in
    account.token_expires_at = received_at + timedelta(seconds=expires_in)

    user_info = get_information(
        access_token=res["access_token"], raja_api_key=RAJA_FRONT_API_KEY
    )
    account.user_information = user_info

    account.save()

    return "refreshed"


@shared_task(queue="qu")
def check_raja_api_key():
    obj = RajaConfig.objects.last()
    res_data = get_raja_config()
    if obj:
        if obj.raja_config.get("Key") == res_data.get("key"):
            return "skipped"
        else:
            obj.raja_config = res_data
            obj.save()
            return "refreshed config raja"
    else:
        RajaConfig.objects.create(raja_config=res_data)
        return "create new config raja"
