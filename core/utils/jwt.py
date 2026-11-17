from typing import Any

from django.contrib.auth import get_user_model
from django_bolt import JWTAuthentication
from django_bolt.exceptions import HTTPException

User = get_user_model()


class ActiveUserJWT(JWTAuthentication):
    async def get_user(
        self, user_id: str | None, auth_context: dict[str, Any]
    ) -> Any | None:
        # check user_id
        if not user_id:
            return None

        # check active user
        user = await User.objects.filter(pk=user_id).afirst()
        if not user.is_active:
            raise HTTPException(status_code=401, detail="Inactive user")

        return await super().get_user(user_id, auth_context)
