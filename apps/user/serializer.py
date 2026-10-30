# apps/user/serializer
from datetime import datetime
from typing import Annotated

from django_bolt.serializers import Serializer, Email
from msgspec import Meta


class UserSerializer(Serializer):
    phone: Annotated[str, Meta(min_length=10, max_length=14)]
    username: Annotated[str, Meta(max_length=32)]
    email: Annotated[str, Email]
    password: Annotated[str, Meta(max_length=128)]


class LoginUserSerializer(Serializer):
    phone: Annotated[str, Meta(min_length=10, max_length=14)]
    password: Annotated[str, Meta(max_length=128)]


class RefreshTokenSerializer(Serializer):
    refresh_token: str


class UserInfoResponseSerializer(Serializer):
    email: str
    username: str
    is_staff: bool


class TokenInfoResponseSerializer(Serializer):
    access_token: str
    refresh_token: str
    access_token_expire_datetime: datetime
    refresh_token_expire_datetime: datetime


class UserResponseSerializer(Serializer):
    token: TokenInfoResponseSerializer
    user: UserInfoResponseSerializer


class RefreshTokenResponseSerializer(Serializer):
    access_token: str
    access_token_expire_datetime: datetime
