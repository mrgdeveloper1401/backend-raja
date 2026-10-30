from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

from apps.core.models import Station


@receiver(post_save, sender=Station)
async def clean_cache(sender, instance, **kwargs):
    await cache.adelete("station_list")
