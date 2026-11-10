from enum import Enum
from typing import Optional, List, Literal, Union

from django_bolt.serializers import Serializer
from datetime import date


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


class ReservationListSchema(Serializer):
    id: int
    passenger_first_name: str
    passenger_last_name: str
    passenger_phone: str
    origin: str
    destination: str
    travel_date: date


class OrderListSchema(Serializer):
    id: int
    passenger_name: str
    passenger_phone: str
    origin: str
    destination: str
    travel_date: date
    to_date: Union[date, None]
    passenger_type: PassengerTypeEnum
    trip_type: TripTypeEnum


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


class PassengerCreateSchema(Serializer):
    first_name: str
    last_name: str
    national_id: str
    gender: str
    birth_date: Optional[date]
    phone: str


class PassengerDetailSchema(Serializer):
    id: int
    first_name: str
    last_name: str
    national_id: str
    gender: str
    birth_date: Optional[date]
    phone: str


class PassengerUpdateSchema(Serializer):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    phone: Optional[str] = None


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
    gender: str
    birth_date: Optional[date]
    phone: str
    orders: List[PassengerOrderSchema] = []


class OrderCreateSchema(Serializer):
    # اطلاعات مسافر (اگر مسافر جدید است)
    first_name: str
    last_name: str
    national_id: str
    gender: Literal["male", "female"]
    phone: str
    birth_date: str

    # اطلاعات سفر
    origin: str
    destination: str
    travel_date: str
    to_date: Optional[str]
    passenger_type: Literal["normal", "woman", "man"]
    trip_type: TripTypeEnum
    passenger_type: PassengerTypeEnum
    coupe_type: CoupeTypeEnum
    order_by: OrderByEnum

    # اکانت رجا
    raja_account_id: Union[str, int]


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
