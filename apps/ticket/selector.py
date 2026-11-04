from django.db.models import Count, Q, OuterRef, Subquery, Prefetch

from apps.ticket.models import Reservation, Passenger, Order


async def dashboard_status_selector():
    stats = await Reservation.objects.aaggregate(
        failed_count=Count("id", filter=Q(status=Reservation.ReservationStatus.FAILED)),
        success_count=Count(
            "id", filter=Q(status=Reservation.ReservationStatus.SUCCESS)
        ),
        active_orders_count=Count(
            "id",
            filter=Q(
                status__in=[
                    Reservation.ReservationStatus.PENDING,
                    Reservation.ReservationStatus.MONITORING,
                    Reservation.ReservationStatus.BOOKING,
                    Reservation.ReservationStatus.REDIRECT_GATEWAY,
                ]
            ),
        ),
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
                "status": reservation.status,
                "status_label": reservation.get_status_display(),
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
    queryset = Reservation.objects.select_related("order__passenger").all()

    # ۱. فیلتر تب‌ها
    if tab == "active":
        queryset = queryset.filter(
            status__in=[
                Reservation.ReservationStatus.PENDING,
                Reservation.ReservationStatus.MONITORING,
                Reservation.ReservationStatus.BOOKING,
                Reservation.ReservationStatus.REDIRECT_GATEWAY,
            ]
        )
    elif tab == "success":
        queryset = queryset.filter(status=Reservation.ReservationStatus.SUCCESS)
    elif tab == "failed":
        queryset = queryset.filter(status=Reservation.ReservationStatus.FAILED)

    # ۲. فیلتر جستجو (بر اساس کد سفارش، نام مسافر، مبدا، مقصد)
    if search:
        queryset = queryset.filter(
            Q(id__icontains=search)
            | Q(order__passenger__first_name=search)
            | Q(order__passenger__last_name=search)
            | Q(order__origin=search)
            | Q(order__destination=search)
        )

    # ۳. فیلتر تاریخ
    if date:
        queryset = queryset.filter(order__travel_date=date)

    # ۴. مرتب‌سازی
    queryset = queryset.order_by("-id")

    # ۵. شمارش کل برای صفحه‌بندی
    total = await queryset.acount()

    # ۶. صفحه‌بندی
    offset = (page - 1) * page_size
    # استفاده از async for برای واکشی محدود
    items = []
    async for res in queryset[offset : offset + page_size]:
        items.append(
            {
                "id": res.id,
                "status": res.status,
                "passenger_name": f"{res.order.passenger.first_name} {res.order.passenger.last_name}",
                "passenger_phone": res.order.passenger.phone,
                "origin": res.order.origin,
                "destination": res.order.destination,
                "travel_date": res.order.travel_date,
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
