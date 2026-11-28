# apps/ticket/signals.py
from functools import partial

import jdatetime
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from fake_useragent import UserAgent

from core.utils.trains import sync_create_rj_search_trains
from .models import Reservation, ReservationAttempt, ReservationStatus
from .tasks import process_reservation_task, login_user_task, check_raja_api_key
from ..core.models import Station


def _build_reservation_search_url(reservation, *, using):
    order = reservation.order
    stations = Station.objects.using(using)

    origin = stations.get(name=order.origin)
    destination = stations.get(name=order.destination)

    return sync_create_rj_search_trains(
        origin=origin.code,
        destination=destination.code,
        passengers=reservation.adult_number + reservation.baby_number,
        d=jdatetime.date.fromgregorian(date=order.travel_date).strftime("%Y-%m-%d"),
        ticket_type=order.passenger_type,
    )


def _sync_reservation_attempt(reservation_id, *, created, using):
    reservation = (
        Reservation.objects.using(using)
        .select_related("order")
        .filter(pk=reservation_id)
        .first()
    )
    if reservation is None:
        return

    attempts = ReservationAttempt.objects.using(using).filter(
        reservation_id=reservation_id,
    )

    if created or attempts.exists():
        decrypt_url = _build_reservation_search_url(reservation, using=using)

        if created:
            attempts.create(
                reservation_id=reservation_id,
                user_agent=UserAgent().chrome,
                decrypt_url=decrypt_url,
            )
        else:
            attempts.update(decrypt_url=decrypt_url)

    login_user_task.delay(reservation.raja_account_id)
    check_raja_api_key.delay()


@receiver(post_save, sender=Reservation)
def trigger_reservation_task(sender, instance, created, using, raw=False, **kwargs):
    if raw:
        return

    transaction.on_commit(
        partial(
            _sync_reservation_attempt,
            instance.pk,
            created=created,
            using=using,
        ),
        using=using,
    )


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
