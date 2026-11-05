# apps/core/api.py
import asyncio
from typing import List, AsyncGenerator

import redis
from django.core.cache import cache
from django.shortcuts import aget_object_or_404
from django_bolt import BoltAPI, EventSourceResponse

from apps.core.selector import station_selector
from apps.core.serializers import StationSerializer
from apps.ticket.models import Reservation
from core.settings import CELERY_RESULT_BACKEND

api = BoltAPI(prefix="/api/v1/core")


@api.get("/", tags=["v1_core"])
async def mission_control_status():
    return {"status": "operational", "message": "app Control Online"}


@api.get("/station", tags=["v1_core"], response_model=List[StationSerializer])
async def station():
    cache_key = "station_list"
    cache_value = await cache.aget(cache_key)
    if cache_value:
        return cache_value

    res = await station_selector()
    await cache.aset("station_list", res)
    return res


@api.get(
    "/reservations/{reservation_id}/logs",
    response_class=EventSourceResponse,
)
async def stream_reservation_logs(reservation_id: int) -> AsyncGenerator[dict, None]:
    reservation = await aget_object_or_404(Reservation, pk=reservation_id)

    task_id = reservation.celery_task_id
    if not task_id:
        yield {"log": "تسکی برای این رزرو ثبت نشده است."}
        return

    log_key = f"celery-task-log-{task_id}"
    r = redis.from_url(CELERY_RESULT_BACKEND)

    last_len = 0
    while True:
        try:
            current_len = r.llen(log_key)
            if current_len > last_len:
                new_logs = r.lrange(log_key, last_len, -1)
                for log in new_logs:
                    yield {"log": log.decode("utf-8")}
                last_len = current_len
        except Exception as e:
            yield {"log": f"خطا در خواندن لاگ: {e}"}
            break

        await asyncio.sleep(1)

