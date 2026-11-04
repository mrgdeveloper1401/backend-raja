from typing import List

from django_bolt import BoltAPI, JWTAuthentication, IsAuthenticated
from django_bolt.exceptions import HTTPException

from apps.ticket.models import Passenger
from apps.ticket.schema import (
    DashboardStatusSchema,
    ReservationListSchema,
    PaginatedOrdersSchema,
    PaginatedPassengersSchema,
    PassengerDetailSchema,
    PassengerCreateSchema, PassengerUpdateSchema, PassengerNewDetailSchema,
)
from apps.ticket.selector import (
    dashboard_status_selector,
    five_last_reservations_selector,
    get_paginated_orders_selector,
    get_paginated_passengers_selector, update_passenger_selector, delete_passenger_selector,
    get_passenger_detail_selector,
)
from apps.ticket.services import create_passenger_selector

api = BoltAPI(prefix="/api/v1/admin")


@api.get(
    "/status",
    status_code=200,
    summary="dashboard status",
    response_model=DashboardStatusSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def dashboard_status():
    res = await dashboard_status_selector()
    return res


@api.get(
    "/five_reservation",
    status_code=200,
    summary="dashboard status five reservation",
    response_model=List[ReservationListSchema],
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def five_reservation():
    res = await five_last_reservations_selector()
    return res


@api.get(
    "/orders",
    status_code=200,
    response_model=PaginatedOrdersSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def list_orders(
    tab: str = "all",
    search: str = "",
    date: str | None = None,
    page: int = 1,
):
    res = await get_paginated_orders_selector(
        tab=tab, search=search, date=date, page=page, page_size=20
    )
    return res


@api.get(
    "/passengers",
    status_code=200,
    response_model=PaginatedPassengersSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def list_passengers(
    search: str = "",
    page: int = 1,
):
    res = await get_paginated_passengers_selector(
        search=search, page=page, page_size=20
    )
    return res


@api.post(
    "/passengers",
    status_code=201,
    response_model=PassengerDetailSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def create_passenger(payload: PassengerCreateSchema):
    # ۱. اعتبارسنجی اضافی (مثلا یکتا بودن کد ملی)
    exists = await Passenger.objects.filter(national_id=payload.national_id).aexists()
    if exists:
        raise HTTPException(
            status_code=400, detail="مسافری با این کد ملی قبلا ثبت شده است."
        )

    # ۲. ذخیره در دیتابیس
    passenger = await create_passenger_selector(payload.to_dict())

    # ۳. بازگرداندن اطلاعات ذخیره شده
    return passenger


@api.get(
    "/passengers/{passenger_id}",
    response_model=PassengerNewDetailSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def get_passenger(passenger_id: int):
    res = await get_passenger_detail_selector(passenger_id)
    if not res:
        raise HTTPException(status_code=404, detail="مسافر یافت نشد")
    return res

# ۲. ویرایش
@api.patch(
    "/passengers/{passenger_id}",
    response_model=PassengerDetailSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def update_passenger(passenger_id: int, payload: PassengerUpdateSchema):
    res = await update_passenger_selector(passenger_id, payload.to_dict())
    if not res:
        raise HTTPException(status_code=404, detail="مسافر یافت نشد")
    return res

# ۳. حذف
@api.delete(
    "/passengers/{passenger_id}",
    status_code=204,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def delete_passenger(passenger_id: int):
    success = await delete_passenger_selector(passenger_id)
    if not success:
        raise HTTPException(status_code=404, detail="مسافر یافت نشد")
    return None

