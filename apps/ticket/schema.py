from decimal import Decimal
from enum import Enum
from typing import Optional, List, Literal, Union

from django_bolt import PageNumberPagination
from django_bolt.serializers import Serializer
from datetime import date, datetime, time


class TripTypeEnum(Enum):
    OUT_BOUND = "outbound"
    OUT_BOUND_AND_RETURN = "outbound_and_return"


class PassengerTypeEnum(Enum):
    MAN = "male"
    WOMAN = "famale"
    NORMAL = "family"


class DashboardStatusSchema(Serializer):
    failed_count: int
    success_count: int
    active_orders_count: int
    solve_captcha: int


class ReservationListSchema(Serializer):
    id: int
    origin: str
    destination: str
    travel_date: date
    phone: str | None


class OrderListSchema(Serializer):
    id: int
    order_id: int
    phone: str | None
    origin: str
    destination: str
    travel_date: date
    to_date: Union[date, None]
    passenger_type: PassengerTypeEnum
    trip_type: TripTypeEnum
    status: Union[str, None]
    is_exclusive: bool
    adult_number: int
    baby_number: int
    departure_time_slots: list[int] | None = None
    raja_account_id: int | None = None
    to_date: Optional[date] = None
    from_price: Decimal | None = None
    to_price: Decimal | None = None
    train_number: list[str] | None = None
    coupe_type: Optional[str] = None


class PaginatedOrdersSchema(Serializer):
    items: list[OrderListSchema]
    total: int
    page: int
    page_size: int


class PassengerListSchema(Serializer):
    id: int
    full_name: str
    orders_count: int
    is_adult: bool
    national_id: str | None
    last_order_date: Optional[date] = None


class PaginatedPassengersSchema(Serializer):
    items: list[PassengerListSchema]
    total: int
    page: int
    page_size: int


class PassengerCreateSchema(Serializer):
    first_name: str
    last_name: str
    national_id: str
    birth_date: Optional[date]


class PassengerDetailSchema(Serializer):
    id: int
    first_name: str
    last_name: str
    national_id: str
    birth_date: Optional[date]
    is_adult: bool


class OrderDetailSchema(Serializer):
    id: int
    order_id: int
    status: str
    is_exclusive: bool
    phone: Optional[str]
    origin: str
    destination: str
    travel_date: date
    to_date: Optional[date]
    passenger_type: str  # یا Literal
    trip_type: str  # یا Literal
    to_price: Optional[Decimal]
    from_price: Optional[Decimal]
    train_number: Optional[list[str]]
    adult_number: int
    baby_number: int
    passengers: list[PassengerDetailSchema]
    coupe_type: Optional[str] = None
    departure_time_slots: list[int] | None = None
    raja_account_id: int | None = None


class PassengerUpdateSchema(Serializer):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None

    birth_date: Optional[date] = None


class PassengerOrderSchema(Serializer):
    id: int
    origin: str
    destination: str
    travel_date: date
    passenger_type: str


class PassengerNewDetailSchema(Serializer):
    id: int
    first_name: str
    last_name: str
    national_id: str
    birth_date: Optional[date]
    orders: List[PassengerOrderSchema] = []


class OrderCreatePassengerSchema(Serializer):
    first_name: str
    last_name: str
    national_id: str
    birth_date: str


class OrderCreateSchema(Serializer):
    origin: str
    destination: str
    trip_type: Literal["outbound", "outbound_and_return"]
    travel_date: str
    passenger_type: Literal["family", "famale", "male"]
    passengers: List[OrderCreatePassengerSchema]
    raja_account_id: int | str
    is_exclusive: bool
    adult_number: int
    baby_number: int
    phone: str
    to_date: Union[str, None] = None
    from_price: Decimal | None = None
    to_price: Decimal | None = None
    train_number: list[str] | None = None
    coupe_type: Optional[str] = None
    departure_time_slots: List[int] | None = None


class RajaAccountOptionSchema(Serializer):
    id: int
    username: str


class DashboardChartStatusSchema(Serializer):
    pending_count: int
    monitoring_count: int
    booking_count: int
    redirect_gateway_count: int
    failed_count: int
    active_orders_count: int  # مجموع وضعیت‌های فعال
    solve_captcha: int


class RestitutionSchema(Serializer):
    serial_number: str
    phone: str
    train_number: list[str]
    hall_number: str
    raja_account_id: int
    status: Literal["success", "failed", "pending"] = "pending"


class RestitutionResponseSchema(Serializer):
    id: int
    serial_number: str
    phone: str
    train_number: list[str]
    hall_number: str
    created_at: datetime
    updated_at: datetime
    raja_account_id: int
    status: Literal["success", "failed", "pending"]


class RestitutionPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"


# در schema.py
class OrderUpdatePassengerSchema(Serializer):
    first_name: str
    last_name: str
    national_id: str
    birth_date: str


class OrderUpdateSchema(Serializer):
    departure_time_slots: list[int] | None = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[date] = None
    to_date: Optional[date] = None
    passenger_type: Optional[PassengerTypeEnum] = None
    trip_type: Optional[TripTypeEnum] = None
    raja_account_id: Optional[int] = None
    coupe_type: Optional[str] = None
    is_exclusive: Optional[bool] = None
    from_price: Optional[Decimal] = None
    to_price: Optional[Decimal] = None
    train_number: Optional[list[str]] = None
    salon: Optional[str] = None
    phone: Optional[str] = None
    adult_number: Optional[int] = None
    baby_number: Optional[int] = None
    passengers: Optional[List[OrderUpdatePassengerSchema]] = None
    status: Optional[str] = None
