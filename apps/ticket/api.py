from typing import List

from django_bolt import BoltAPI, JWTAuthentication, IsAuthenticated

from apps.ticket.schema import DashboardStatusSchema, ReservationListSchema, PaginatedOrdersSchema
from apps.ticket.selector import (
    dashboard_status_selector,
    five_last_reservations_selector,
    get_paginated_orders_selector
)

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
    '/five_reservation',
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
        tab=tab,
        search=search,
        date=date,
        page=page,
        page_size=20
    )
    return res
