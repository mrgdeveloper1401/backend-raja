# apps/ticket/services.py
from apps.ticket.models import Passenger


async def create_passenger_selector(data: dict) -> Passenger:
    passenger = await Passenger.objects.acreate(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        national_id=data.get("national_id"),
        gender=data.get("gender"),
        birth_date=data.get("birth_date"),
        phone=data.get("phone"),
    )
    return passenger
