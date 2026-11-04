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

