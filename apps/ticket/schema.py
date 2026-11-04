from typing import Optional

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


class OrderListSchema(Serializer):
    id: int
    status: str
    passenger_name: str
    passenger_phone: str
    origin: str
    destination: str
    travel_date: date


class PaginatedOrdersSchema(Serializer):
    items: list[OrderListSchema]
    total: int
    page: int
    page_size: int


class PassengerListSchema(Serializer):
    id: int
    full_name: str
    phone: str
    orders_count: int
    last_order_date: Optional[date] = None


class PaginatedPassengersSchema(Serializer):
    items: list[PassengerListSchema]
    total: int
    page: int
    page_size: int
