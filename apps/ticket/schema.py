from decimal import Decimal
from enum import Enum
from typing import Optional, List, Literal, Union, Annotated

from django_bolt import PageNumberPagination
from django_bolt.serializers import Serializer
from datetime import date, datetime, time


class TripTypeEnum(Enum):
    OUT_BOUND = "outbound"
    OUT_BOUND_AND_RETURN = "outbound_and_return"


class PassengerTypeEnum(Enum):
    MAN = "man"
    WOMAN = "woman"
    NORMAL = "normal"


class CoupeTypeEnum(Enum):
    FOUR = "four"
    SIX = "six"
    FOR_ROW = "for_row"


class OrderByEnum(Enum):
    CLOCK = "clock"
    CHEAP = "cheap"
    EXPENSIVE = "expensive"
    OWNER = "owner"


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
    departure_time_from: int | None = None
    departure_time_to: int | None = None
    to_date: str | None = None
    from_price: Decimal | None = None
    to_price: Decimal | None = None
    train_number: str | None = None


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
    train_number: Optional[str]
    departure_time_from: Optional[int]
    departure_time_to: Optional[int]
    adult_number: int
    baby_number: int
    passengers: list[PassengerDetailSchema]


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


import msgspec
from typing import Literal, Optional


class OrderCreateSchema(Serializer):
    first_name: str
    last_name: str
    national_id: str
    phone: str
    birth_date: str
    is_exclusive: bool
    origin: str
    destination: str
    travel_date: str
    passenger_type: Literal["normal", "woman", "man"]
    trip_type: Literal["outbound", "outbound_and_return"]
    raja_account_id: int
    to_date: Optional[str] = None
    departure_time_from: Optional[int] = None
    departure_time_to: Optional[int] = None
    arrival_time_from: Optional[int] = None
    arrival_time_to: Optional[int] = None
    from_price: Optional[float] = None
    to_price: Optional[float] = None
    train_number: Optional[str] = None
    salon: Optional[str] = None
    coupe_type: Optional[Literal["four", "six", "for_row"]] = None


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
    train_number: str
    hall_number: str
    raja_account_id: int
    status: Literal["success", "failed", "pending"] = "pending"


class RestitutionResponseSchema(Serializer):
    id: int
    serial_number: str
    phone: str
    train_number: str
    hall_number: str
    created_at: datetime
    updated_at: datetime
    raja_account_id: int
    status: Literal["success", "failed", "pending"]


class RestitutionPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
