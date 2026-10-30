from django.contrib.auth import aauthenticate
from django.contrib.auth.base_user import AbstractBaseUser

from django_bolt.exceptions import Unauthorized, NotFound

from apps.user.models import User


async def login_user_selector(data) -> AbstractBaseUser:
    phone = data.get("phone")
    password = data.get("password")
    user = await aauthenticate(phone=phone, password=password)
    if user:
        return user
    else:
        raise Unauthorized(detail="Invalid credentials")


async def get_user_by_id_selector(user_id: int) -> User:
    try:
        user = await User.objects.aget(id=user_id)
        return user
    except User.DoesNotExist:
        raise NotFound(detail="user not found")
