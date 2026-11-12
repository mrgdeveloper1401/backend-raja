from asgiref.sync import sync_to_async
from django.db.models import Count, Q, OuterRef, Subquery, Prefetch

from apps.ticket.models import (
    Reservation,
    Passenger,
    Order,
    ReservationStatus,
    ReservationAttempt,
    Restitution,
)
from apps.user.models import RajaAccount


async def dashboard_status_selector():
    stats = await ReservationAttempt.objects.aaggregate(
        failed_count=Count("id", filter=Q(status=ReservationStatus.FAILED)),
        success_count=Count(
            "id",
            filter=Q(
                status__in=[
                    ReservationStatus.SUCCESS,
                    ReservationStatus.REDIRECT_GATEWAY,
                ]
            ),
        ),
        active_orders_count=Count(
            "id",
            filter=Q(
                status__in=[
                    ReservationStatus.PENDING,
                    ReservationStatus.MONITORING,
                    ReservationStatus.BOOKING,
                ]
            ),
        ),
        solve_captcha=Count("id", filter=Q(status=ReservationStatus.CAPTCHA)),
    )
    return stats


async def five_last_reservations_selector():
    queryset = Reservation.objects.select_related("order__passenger").order_by("-id")

    results = []
    async for reservation in queryset:
        order = reservation.order
        passenger = order.passenger
        results.append(
            {
                "id": reservation.id,
                "passenger_first_name": passenger.first_name,
                "passenger_last_name": passenger.last_name,
                "passenger_phone": passenger.phone,
                "origin": order.origin,
                "destination": order.destination,
                "travel_date": order.travel_date,
            }
        )
        if len(results) == 5:
            break

    return results


async def get_paginated_orders_selector(
    tab: str = "all",
    search: str = "",
    date: str = None,
    page: int = 1,
    page_size: int = 20,
):
    # واکشی اولیه با روابط (برای جلوگیری از N+1)
    queryset = ReservationAttempt.objects.select_related(
        "reservation__order__passenger"
    ).all()

    # ۱. فیلتر تب‌ها
    if tab == "active":
        queryset = queryset.filter(
            status__in=[
                ReservationStatus.PENDING,
                ReservationStatus.MONITORING,
                ReservationStatus.BOOKING,
            ]
        )
    elif tab == "success":
        queryset = queryset.filter(
            status__in=[ReservationStatus.SUCCESS, ReservationStatus.REDIRECT_GATEWAY]
        )
    elif tab == "failed":
        queryset = queryset.filter(status=ReservationStatus.FAILED)

    # ۲. فیلتر جستجو (بر اساس کد سفارش، نام مسافر، مبدا، مقصد)
    # if search:
    #     queryset = queryset.filter(reservation__order__phone=search)

    # ۳. فیلتر تاریخ
    # if date:
    #     queryset = queryset.filter(reservation__order__travel_date=date)

    # ۴. مرتب‌سازی
    queryset = queryset.order_by("-id")

    # ۵. شمارش کل برای صفحه‌بندی
    total = await queryset.acount()

    # ۶. صفحه‌بندی
    # TODO, optimize
    offset = (page - 1) * page_size
    # استفاده از async for برای واکشی محدود
    items = []
    async for res in queryset[offset : offset + page_size]:
        items.append(
            {
                "id": res.reservation_id,
                "status": res.status,
                "passenger_name": f"{res.reservation.order.passenger.first_name} {res.reservation.order.passenger.last_name}",
                "passenger_phone": res.reservation.order.passenger.phone,
                "origin": res.reservation.order.origin,
                "destination": res.reservation.order.destination,
                "travel_date": res.reservation.order.travel_date,
                "to_date": res.reservation.order.to_date,
                "passenger_type": res.reservation.order.passenger_type,
                "trip_type": res.reservation.order.trip_type,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_paginated_passengers_selector(
    search: str = "", page: int = 1, page_size: int = 20
):
    # واکشی همه مسافران
    queryset = Passenger.objects.all()

    # ۱. فیلتر جستجو (نام، نام خانوادگی، یا شماره موبایل)
    if search:
        queryset = queryset.filter(
            Q(first_name=search) | Q(last_name=search) | Q(phone=search)
        )

    # ۲. انوتیشن (محاسبه تعداد سفارشات و آخرین تاریخ سفر)
    # برای بهینه بودن، فقط تاریخ سفر را از سفارشات می‌گیریم
    last_order_subquery = (
        Order.objects.filter(passenger=OuterRef("pk"))
        .order_by("-travel_date")
        .values("travel_date")[:1]
    )

    queryset = queryset.annotate(
        orders_count=Count("passenger_orders"),
        last_order_date=Subquery(last_order_subquery),
    ).order_by("-id")  # مرتب‌سازی بر اساس جدیدترین مسافران

    # ۳. شمارش کل
    total = await queryset.acount()

    # ۴. صفحه‌بندی
    offset = (page - 1) * page_size
    items = []

    # واکشی محدود
    async for passenger in queryset[offset : offset + page_size]:
        items.append(
            {
                "id": passenger.id,
                "full_name": f"{passenger.first_name} {passenger.last_name}".strip(),
                "phone": passenger.phone,
                "orders_count": passenger.orders_count,
                "last_order_date": passenger.last_order_date,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_passenger_detail_selector(passenger_id: int):
    # استفاده از prefetch_related برای گرفتن سفارشات در یک کوئری جداگانه (بهینه)
    passenger = (
        await Passenger.objects.filter(id=passenger_id)
        .prefetch_related(
            Prefetch(
                "passenger_orders", queryset=Order.objects.order_by("-travel_date")
            )
        )
        .afirst()
    )

    if not passenger:
        return None

    return {
        "id": passenger.id,
        "first_name": passenger.first_name,
        "last_name": passenger.last_name,
        "national_id": passenger.national_id,
        "gender": passenger.gender,
        "birth_date": passenger.birth_date,
        "phone": passenger.phone,
        "orders": [
            {
                "id": o.id,
                "origin": o.origin,
                "destination": o.destination,
                "travel_date": o.travel_date,
                "passenger_type": o.passenger_type,
            }
            for o in passenger.passenger_orders.all()
        ],
    }


async def update_passenger_selector(passenger_id: int, data: dict):
    # فیلتر کردن مقادیر None (فقط فیلدهایی که فرستاده شدند آپدیت شوند)
    update_data = {k: v for k, v in data.items() if v is not None}

    # آپدیت در دیتابیس
    updated_count = await Passenger.objects.filter(id=passenger_id).aupdate(
        **update_data
    )
    if not updated_count:
        return None

    return await Passenger.objects.aget(id=passenger_id)


async def delete_passenger_selector(passenger_id: int):
    # حذف نرم (Soft Delete) - اگر مدل شما فیلد is_deleted دارد
    # passenger = await Passenger.objects.filter(id=passenger_id).aupdate(is_deleted=True)

    # یا حذف فیزیکی (با توجه به SoftDeleteMixin در مدل شما، احتمالا به صورت خودکار نرم حذف می‌شود)
    deleted_count, _ = await Passenger.objects.filter(id=passenger_id).adelete()
    return deleted_count > 0


async def get_raja_account_options_selector():
    accounts = RajaAccount.objects.filter(is_active=True).order_by("-id")
    options = []
    async for acc in accounts:
        options.append({"id": acc.id, "username": acc.username})
    return options


async def dashboard_chart_status_selector():
    stats = await ReservationAttempt.objects.aaggregate(
        pending_count=Count("id", filter=Q(status=ReservationStatus.PENDING)),
        monitoring_count=Count("id", filter=Q(status=ReservationStatus.MONITORING)),
        booking_count=Count("id", filter=Q(status=ReservationStatus.BOOKING)),
        redirect_gateway_count=Count(
            "id", filter=Q(status=ReservationStatus.REDIRECT_GATEWAY)
        ),
        solve_captcha=Count("id", filter=Q(status=ReservationStatus.CAPTCHA)),
        failed_count=Count("id", filter=Q(status=ReservationStatus.FAILED)),
        active_orders_count=Count(
            "id",
            filter=Q(
                status__in=[
                    ReservationStatus.PENDING,
                    ReservationStatus.MONITORING,
                    ReservationStatus.BOOKING,
                    ReservationStatus.REDIRECT_GATEWAY,
                ]
            ),
        ),
    )
    return stats


async def restitution_list_selector():
    # return [item async for item in Restitution.objects.order_by('id')]
    return Restitution.objects.order_by('-id')
