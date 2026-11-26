# apps/ticket/signals.py
import jdatetime
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from fake_useragent import UserAgent

from core.utils.trains import sync_create_rj_search_trains
from .models import Reservation, ReservationAttempt, ReservationStatus, Order
from .tasks import process_reservation_task, login_user_task, check_raja_api_key
from ..core.models import Station


@receiver(post_save, sender=Reservation)
def trigger_reservation_task(sender, instance, created, **kwargs):
    def _process_reservation_task():
        ua = UserAgent().chrome

        origin_code = get_object_or_404(Station, name=instance.order.origin)
        dest_code = get_object_or_404(Station, name=instance.order.destination)
        len_passenger = instance.adult_number + instance.baby_number
        d = jdatetime.date.fromgregorian(date=instance.order.travel_date).strftime(
            "%Y-%m-%d"
        )
        ticket_type = instance.order.passenger_type
        decrypt_url = sync_create_rj_search_trains(
            origin=origin_code.code,
            destination=dest_code.code,
            passengers=len_passenger,
            d=d,
            ticket_type=ticket_type,
        )

        ReservationAttempt.objects.create(
            reservation_id=instance.id, user_agent=ua, decrypt_url=decrypt_url
        )

    if created:
        transaction.on_commit(_process_reservation_task)

    login_user_task.delay(instance.raja_account_id)
    check_raja_api_key.delay()


@receiver(pre_save, sender=ReservationAttempt)
def remember_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = (
        ReservationAttempt.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save, sender=ReservationAttempt)
def start_reservation(sender, instance, created, **kwargs):
    became_pending = (
        instance.status == ReservationStatus.PENDING
        and getattr(instance, "_previous_status", None) != ReservationStatus.PENDING
    )
    if not became_pending:
        return

    def enqueue():
        process_reservation_task.delay(instance.reservation_id)

    transaction.on_commit(enqueue)
