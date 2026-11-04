from django.contrib.auth import aauthenticate
from django.contrib.auth.base_user import AbstractBaseUser

from django_bolt.exceptions import Unauthorized, NotFound

from apps.user.models import User, RajaAccount


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


async def get_paginated_raja_accounts_selector(
    search: str = "", page: int = 1, page_size: int = 20
):
    queryset = RajaAccount.objects.all().order_by("-id")

    if search:
        queryset = queryset.filter(username__icontains=search)

    total = await queryset.acount()
    offset = (page - 1) * page_size

    items = []
    async for acc in queryset[offset : offset + page_size]:
        items.append(
            {
                "id": acc.id,
                "username": acc.username,
                "is_active": acc.is_active,
            }
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def create_raja_account_selector(data: dict):
    # (نکته امنیتی: در پروژه واقعی رمز را هش کنید، اما چون ربات باید لاگین کند، معمولا باید رمز خام ذخیره شود)
    return await RajaAccount.objects.acreate(
        username=data.get("username"),
        password=data.get("password"),
        is_active=data.get("is_active", True),
    )


async def update_raja_account_selector(account_id: int, data: dict):
    # فقط فیلدهایی که مقدار دارند را آپدیت می‌کنیم
    update_data = {}
    if data.get("username"):
        update_data["username"] = data["username"]
    if data.get("password"):
        update_data["password"] = data["password"]  # فقط اگر رمز جدید فرستاده شد
    if data.get("is_active") is not None:
        update_data["is_active"] = data["is_active"]

    updated_count = await RajaAccount.objects.filter(id=account_id).aupdate(
        **update_data
    )
    if not updated_count:
        return None

    return await RajaAccount.objects.aget(id=account_id)


async def delete_raja_account_selector(account_id: int):
    deleted_count, _ = await RajaAccount.objects.filter(id=account_id).adelete()
    return deleted_count > 0
