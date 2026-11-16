# apps/ticket/services.py
from asgiref.sync import sync_to_async
from django.db import transaction
from django_bolt.exceptions import HTTPException
from django_bolt.status_codes import HTTP_404_NOT_FOUND

from apps.ticket.models import (
    Passenger,
    Reservation,
    Order,
    ReservationAttempt,
    OrderPassenger, ReservationStatus,
)


async def create_passenger_selector(data: dict) -> Passenger:
    passenger = await Passenger.objects.acreate(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        national_id=data.get("national_id"),
        birth_date=data.get("birth_date"),
    )
    return passenger


async def create_order_with_reservation_selector(data: dict):
    @sync_to_async
    def _create():
        with transaction.atomic():
            # . ساخت سفارش
            order = Order.objects.create(
                origin=data["origin"],
                destination=data["destination"],
                travel_date=data["travel_date"],
                trip_type=data.get("trip_type", "outbound"),
                to_date=data.get("to_date", None),
                passenger_type=data.get("passenger_type", "normal"),
            )

            # چگ گردن مسافر
            passengers = data.get("passengers", [])
            for p in passengers:
                passenger = Passenger.objects.filter(national_id=p.national_id).first()

                if not passenger:
                    passenger = Passenger.objects.create(
                        national_id=p.national_id,
                        first_name=p.first_name,
                        last_name=p.last_name,
                        birth_date=p.birth_date,
                    )

                # ایجاد سفارش هر کاربر
                OrderPassenger.objects.create(
                    order_id=order.id, passenger_id=passenger.id
                )

            # ۳. ساخت رزرو
            reservation = Reservation.objects.create(
                order_id=order.id,
                raja_account_id=data["raja_account_id"],
                coupe_type=data["coupe_type"],
                is_exclusive=data["is_exclusive"],
                departure_time_from=data["departure_time_from"],
                departure_time_to=data["departure_time_to"],
                from_price=data["from_price"],
                to_price=data["to_price"],
                train_number=data["train_number"],
                adult_number=data.get("adult_number"),
                baby_number=data.get("baby_number"),
                phone=data.get("phone"),
            )

            return order, reservation

    return await _create()


async def create_restitution(data: dict) -> Reservation:
    restitution = await Restitution.objects.acreate(**data)
    return restitution


async def delete_order_services(order_id: int):
    try:
        order = await ReservationAttempt.objects.aget(id=order_id)
    except ReservationAttempt.DoesNotExist:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND)
    await order.adelete()


async def update_order_and_restart_selector(order_id: int, data: dict):
    @sync_to_async
    def _update():
        with transaction.atomic():
            attempt = (
                ReservationAttempt.objects.filter(reservation_id=order_id)
                .select_related("reservation__order")
                .last()
            )
            if not attempt:
                raise HTTPException(status_code=404, detail="reservation not found")

            reservation = attempt.reservation
            order = reservation.order

            # --- آپدیت فیلدهای سفارش ---
            if "origin" in data:
                order.origin = data["origin"]
            if "destination" in data:
                order.destination = data["destination"]
            if "travel_date" in data:
                order.travel_date = data["travel_date"]
            if "to_date" in data:
                order.to_date = data["to_date"]
            if "passenger_type" in data:
                order.passenger_type = data["passenger_type"]
            if "trip_type" in data:
                order.trip_type = data["trip_type"]
            order.save()

            # --- آپدیت مسافران (اگر ارسال شده بودند) ---
            if "passengers" in data and data["passengers"] is not None:
                # ۱. حذف نرم ارتباط‌های قبلی
                OrderPassenger.objects.filter(order_id=order.id).delete()

                # ۲. ایجاد/اتصال مسافران جدید
                for p_data in data["passengers"]:
                    # اگر p_data آبجکت است، به دیکشنری تبدیل می‌کنیم
                    if not isinstance(p_data, dict):
                        p_dict = {
                            "first_name": p_data.first_name,
                            "last_name": p_data.last_name,
                            "national_id": p_data.national_id,
                            "birth_date": p_data.birth_date,
                        }
                    else:
                        p_dict = p_data

                    passenger = Passenger.objects.filter(
                        national_id=p_dict["national_id"]
                    ).first()
                    if not passenger:
                        passenger = Passenger.objects.create(
                            national_id=p_dict["national_id"],
                            first_name=p_dict["first_name"],
                            last_name=p_dict["last_name"],
                            birth_date=p_dict["birth_date"],
                        )
                    # ایجاد ارتباط جدید
                    OrderPassenger.objects.create(order=order, passenger=passenger)

            # --- آپدیت فیلدهای رزرو ---
            if "raja_account_id" in data:
                reservation.raja_account_id = data["raja_account_id"]
            if "coupe_type" in data:
                reservation.coupe_type = data["coupe_type"]
            if "is_exclusive" in data:
                reservation.is_exclusive = data["is_exclusive"]
            if "departure_time_from" in data:
                reservation.departure_time_from = data["departure_time_from"]
            if "departure_time_to" in data:
                reservation.departure_time_to = data["departure_time_to"]
            if "from_price" in data:
                reservation.from_price = data["from_price"]
            if "to_price" in data:
                reservation.to_price = data["to_price"]
            if "train_number" in data:
                reservation.train_number = data["train_number"]
            if "salon" in data:
                reservation.salon = data["salon"]
            if "phone" in data:
                reservation.phone = data["phone"]
            if "adult_number" in data:
                reservation.adult_number = data["adult_number"]
            if "baby_number" in data:
                reservation.baby_number = data["baby_number"]
            reservation.save()

            # --- تغییر وضعیت ---
            if data.get("status"):
                attempt.status = ReservationStatus.PENDING
                attempt.celery_task_id = None
                attempt.save()
                return attempt

            return attempt

    return await _update()
