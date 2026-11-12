# apps/core/auth.py (یا در همان api.py)
from django_bolt import JWTAuthentication
from django_bolt.types import Request


class QueryParamJWTAuthentication(JWTAuthentication):
    """
    احراز هویت JWT که توکن را از Query String (?token=...) می‌خواند.
    مناسب برای EventSource (SSE) که نمی‌تواند هدر سفارشی بفرستد.
    """

    async def authenticate(self, request: Request):
        # ۱. ابتدا سعی کن از هدر Authorization بخوان (روش پیش‌فرض)
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            return await super().authenticate(request)

        # ۲. اگر هدر نبود، از Query String بخوان
        token = request.query_params.get("token")
        if not token:
            return None

        # ۳. اعتبارسنجی توکن با استفاده از منطق والد
        # (باید توکن را به شکل مورد انتظار والد برسانیم)
        # در django-bolt، متد authenticate والد انتظار دارد توکن در هدر باشد.
        # بنابراین یک هدر مصنوعی می‌سازیم.
        # راه ساده‌تر: مستقیماً از منطق داخلی استفاده کنیم.
        # اما چون به جزئیات پیاده‌سازی دسترسی نداریم،
        # بهترین کار این است که توکن را به شکل یک هدر موقت به والد بدهیم.
        # (این بخش ممکن است بسته به نسخه django-bolt نیاز به تنظیم داشته باشد)

        # روش جایگزین: خودمان توکن را decode کنیم (اگر منطق را می‌دانیم)
        # فعلاً فرض می‌کنیم والد متدی برای validate دارد.
        # ساده‌ترین راه: یک درخواست جعلی با هدر بسازیم.
        # اما این کار بهینه نیست.

        # راه‌حل عملی: از متد داخلی والد استفاده کنیم با تغییر request
        # (در django-bolt، request.headers یک دیکشنری است)
        original_auth = request.headers.get("authorization")
        request.headers["authorization"] = f"Bearer {token}"
        try:
            result = await super().authenticate(request)
        finally:
            # بازگرداندن هدر اصلی (اگر وجود داشت)
            if original_auth:
                request.headers["authorization"] = original_auth
            else:
                request.headers.pop("authorization", None)
        return result
