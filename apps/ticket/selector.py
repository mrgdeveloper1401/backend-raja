from django.db.models import Count, Q

from apps.ticket.models import Reservation


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
    queryset = (
        Reservation.objects
        .select_related("order__passenger")
        .order_by("-id")
    )

    results = []
    async for reservation in queryset:
        order = reservation.order
        passenger = order.passenger
        results.append({
            "id": reservation.id,
            "passenger_first_name": passenger.first_name,
            "passenger_last_name": passenger.last_name,
            "passenger_phone": passenger.phone,
            "origin": order.origin,
            "destination": order.destination,
            "travel_date": order.travel_date,
            "status": reservation.status,
            "status_label": reservation.get_status_display(),
        })
        if len(results) == 5:
            break

    return results


async def get_paginated_orders_selector(
    tab: str = "all",
    search: str = "",
    date: str = None,
    page: int = 1,
    page_size: int = 20
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
            Q(id__icontains=search) |
            Q(order__passenger__first_name=search) |
            Q(order__passenger__last_name=search) |
            Q(order__origin=search) |
            Q(order__destination=search)
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
    async for res in queryset[offset:offset+page_size]:
        items.append({
            "id": res.id,
            "status": res.status,
            "passenger_name": f"{res.order.passenger.first_name} {res.order.passenger.last_name}",
            "passenger_phone": res.order.passenger.phone,
            "origin": res.order.origin,
            "destination": res.order.destination,
            "travel_date": res.order.travel_date,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
