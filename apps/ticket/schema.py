from django_bolt.serializers import Serializer
from datetime import date


class DashboardStatusSchema(Serializer):
    failed_count: int
    success_count: int
    active_orders_count: int


class ReservationListSchema(Serializer):
    id: int
    passenger_first_name: str
    passenger_last_name: str
    passenger_phone: str
    origin: str
    destination: str
    travel_date: date
    status: str
