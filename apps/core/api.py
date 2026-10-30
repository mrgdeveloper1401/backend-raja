from typing import List

from django.core.cache import cache
from django_bolt import BoltAPI

from apps.core.selector import station_selector
from apps.core.serializers import StationSerializer

api = BoltAPI()


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
