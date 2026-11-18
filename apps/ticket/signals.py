# apps/ticket/signals.py
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from fake_useragent import UserAgent

from .models import Reservation, ReservationAttempt, ReservationStatus
from .tasks import process_reservation_task


@receiver(post_save, sender=Reservation)
def trigger_reservation_task(sender, instance, created, **kwargs):
    def _process_reservation_task():
        ua = UserAgent().chrome
        ReservationAttempt.objects.create(reservation_id=instance.id, user_agent=ua)

    if created:
        transaction.on_commit(_process_reservation_task)


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
        and not instance.celery_task_id
    )
    if not became_pending:
        return

    def enqueue():
        task = process_reservation_task.delay(instance.reservation_id)
        ReservationAttempt.objects.filter(pk=instance.pk).update(celery_task_id=task.id)

    transaction.on_commit(enqueue)
