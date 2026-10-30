from datetime import timedelta
from typing import Union

import jwt
from django.contrib.auth.base_user import AbstractBaseUser
from django.utils import timezone
from django_bolt import create_jwt_for_user
from django_bolt.exceptions import Conflict, Unauthorized

from apps.user.models import User
from apps.user.selector import get_user_by_id_selector
from core import settings
from core.settings import ACCESS_TOKEN_EXPIRE, REFRESH_TOKEN_EXPIRE


async def create_user_services(data) -> User:
    # check
    phone = data.get("phone")
    username = data.get("username")

    if await User.objects.filter(phone=phone).aexists():
        raise Conflict(detail="phone already exists")

    if await User.objects.filter(username=username).aexists():
        raise Conflict(detail="username already exists")

    # create user
    new_user = await User.objects.acreate_user(**data)
    return new_user


async def generate_token_services(user: Union[User, AbstractBaseUser]) -> dict:
    access_token = create_jwt_for_user(
        user, expires_in=ACCESS_TOKEN_EXPIRE, extra_claims={"token_type": "access"}
    )
    refresh_token = create_jwt_for_user(
        user, expires_in=REFRESH_TOKEN_EXPIRE, extra_claims={"token_type": "refresh"}
    )
    access_token_expire_datetime = timezone.now() + timedelta(
        seconds=ACCESS_TOKEN_EXPIRE
    )
    refresh_token_expire_datetime = timezone.now() + timedelta(
        seconds=REFRESH_TOKEN_EXPIRE
    )

    res_data = {
        "token": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_token_expire_datetime": access_token_expire_datetime,
            "refresh_token_expire_datetime": refresh_token_expire_datetime,
        },
        "user": {
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
        },
    }
    return res_data


async def generate_access_token_by_refresh(refresh_token: str) -> dict:
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise Unauthorized(detail="Refresh token has expired")
    except jwt.InvalidTokenError:
        raise Unauthorized(detail="Invalid refresh token")

    if payload.get("token_type") != "refresh":
        raise Unauthorized(detail="Invalid token type, refresh token expected")

    user_id = payload.get("sub")
    if not user_id:
        raise Unauthorized(detail="Invalid token payload")

    user = await get_user_by_id_selector(user_id=user_id)

    new_access_token = create_jwt_for_user(
        user, expires_in=ACCESS_TOKEN_EXPIRE, extra_claims={"token_type": "access"}
    )
    access_token_expire_datetime = timezone.now() + timedelta(
        seconds=ACCESS_TOKEN_EXPIRE
    )

    return {
        "access_token": new_access_token,
        "access_token_expire_datetime": access_token_expire_datetime,
    }
