# apps/user/apis.py
from django_bolt import BoltAPI, JWTAuthentication, IsAuthenticated
from django_bolt.exceptions import HTTPException

from apps.ticket.schema import RajaAccountOptionSchema
from apps.ticket.selector import get_raja_account_options_selector
from apps.user.schema import (
    RajaAccountCreateSchema,
    RajaAccountUpdateSchema,
    PaginatedRajaAccountsSchema,
)
from apps.user.selector import (
    login_user_selector,
    create_raja_account_selector,
    update_raja_account_selector,
    get_paginated_raja_accounts_selector,
    delete_raja_account_selector,
)
from apps.user.serializer import (
    UserResponseSerializer,
    LoginUserSerializer,
    RefreshTokenSerializer,
    RefreshTokenResponseSerializer,
)
from apps.user.services import generate_token_services, generate_access_token_by_refresh

api = BoltAPI(prefix="/api/v1/auth")


@api.post("/login", tags=["v1_user"], response_model=UserResponseSerializer)
async def login_user(data: LoginUserSerializer):
    res = await login_user_selector(data.dump())
    res_data = await generate_token_services(res)
    return res_data


@api.post("/refresh", tags=["v1_user"], response_model=RefreshTokenResponseSerializer)
async def refresh(data: RefreshTokenSerializer):
    res_data = await generate_access_token_by_refresh(data.refresh_token)
    return res_data


@api.get(
    "/raja-accounts",
    response_model=PaginatedRajaAccountsSchema,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def list_raja_accounts(search: str = "", page: int = 1):
    return await get_paginated_raja_accounts_selector(search, page)


@api.post(
    "/raja-accounts",
    status_code=201,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
    response_model=RajaAccountCreateSchema,
)
async def create_raja_account(payload: RajaAccountCreateSchema):
    # چک کردن تکراری نبودن یوزرنیم
    from apps.ticket.models import RajaAccount

    exists = await RajaAccount.objects.filter(username=payload.username).aexists()
    if exists:
        raise HTTPException(status_code=400, detail="این شماره همراه قبلا ثبت شده است.")

    return await create_raja_account_selector(payload.to_dict())


@api.patch(
    "/raja-accounts/{account_id}",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
    response_model=RajaAccountUpdateSchema,
)
async def update_raja_account(account_id: int, payload: RajaAccountUpdateSchema):
    res = await update_raja_account_selector(account_id, payload.to_dict())
    if not res:
        raise HTTPException(status_code=404, detail="اکانت یافت نشد")
    return res


@api.delete(
    "/raja-accounts/{account_id}",
    status_code=204,
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def delete_raja_account(account_id: int):
    success = await delete_raja_account_selector(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="اکانت یافت نشد")
    return None


@api.get(
    "/raja-accounts/options",
    response_model=list[RajaAccountOptionSchema],
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def raja_account_options():
    return await get_raja_account_options_selector()
