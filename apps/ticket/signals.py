# apps/ticket/signals.py
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Reservation
from .tasks import process_reservation_task


@receiver(post_save, sender=Reservation)
def trigger_reservation_task(sender, instance, created, **kwargs):
    def _process_reservation_task():
        result = process_reservation_task.delay(instance.id)
        Reservation.objects.filter(id=instance.id).update(celery_task_id=result.id)

    if created:
        transaction.on_commit(_process_reservation_task)
