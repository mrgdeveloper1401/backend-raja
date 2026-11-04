# apps/user/schema.py
from django_bolt.serializers import Serializer
from typing import Optional


class RajaAccountListSchema(Serializer):
    id: int
    username: str
    is_active: bool
    # password را اینجا نمی‌گذاریم تا در لیست به فرانت نرود


class RajaAccountCreateSchema(Serializer):
    username: str
    password: str
    is_active: Optional[bool] = True


class RajaAccountUpdateSchema(Serializer):
    username: Optional[str] = None
    password: Optional[str] = None  # اگر خالی باشد یعنی تغییر نمی‌کند
    is_active: Optional[bool] = None


class PaginatedRajaAccountsSchema(Serializer):
    items: list[RajaAccountListSchema]
    total: int
    page: int
    page_size: int
