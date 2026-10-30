# apps/user/apis.py
from django_bolt import BoltAPI

from apps.user.selector import login_user_selector
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
