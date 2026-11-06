# apps/ticket/services.py
from asgiref.sync import sync_to_async
from django.db import transaction

from apps.ticket.models import Passenger, Reservation, Order


async def create_passenger_selector(data: dict) -> Passenger:
    passenger = await Passenger.objects.acreate(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        national_id=data.get("national_id"),
        gender=data.get("gender"),
        birth_date=data.get("birth_date"),
        phone=data.get("phone"),
    )
    return passenger


async def create_order_with_reservation_selector(data: dict):
    @sync_to_async
    def _create():
        with transaction.atomic():
            # ۱. پیدا کردن یا ساختن مسافر بر اساس کد ملی
            passenger = Passenger.objects.filter(
                national_id=data.get("national_id")
            ).first()

            # اگر مسافر نبود یکی ان را میسازیم
            if not passenger:
                passenger = Passenger.objects.create(
                    national_id=data.get("national_id"),
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                    phone=data.get("phone"),
                    gender=data.get("gender"),
                    birth_date=data.get("birth_date"),
                )

            # ۲. ساخت سفارش
            order = Order.objects.create(
                passenger_id=passenger.id,
                origin=data["origin"],
                destination=data["destination"],
                travel_date=data["travel_date"],
                passenger_type=data.get("passenger_type", "normal"),
            )

            # ۳. ساخت رزرو
            reservation = Reservation.objects.create(
                order_id=order.id,
                raja_account_id=data["raja_account_id"],
                status=Reservation.ReservationStatus.PENDING,
            )

            return order, reservation

    return await _create()
