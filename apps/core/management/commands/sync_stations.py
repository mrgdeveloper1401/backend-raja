import httpx
from django.core.management.base import BaseCommand
from django.db import transaction

# مدل خودت را ایمپورت کن
from apps.core.models import Station

RAJA_STATIONS_URL = "https://www.raja.ir/assets/File/station.json"


class Command(BaseCommand):
    help = "Fetch stations from Raja and sync into database"

    def handle(self, *args, **options):
        self.stdout.write("در حال دریافت اطلاعات ایستگاه‌ها از رجا...")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            response = httpx.get(RAJA_STATIONS_URL, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"خطا در دریافت اطلاعات: {e}"))
            return

        if not isinstance(data, list):
            self.stderr.write(self.style.ERROR("فرمت دیتای دریافتی لیست نیست!"))
            return

        # تبدیل دیکشنری‌ها به آبجکت‌های مدل
        station_instances = []
        seen_codes = set()

        for item in data:
            code = item.get("Code")
            # جلوگیری از کدهای تکراری درون خود فایل رجا
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)

            station_instances.append(
                Station(
                    code=code,
                    name=(item.get("Name") or "").strip(),
                    english_name=(item.get("EnglishName") or "").strip(),
                    tel_code=(item.get("TelCode") or "").strip(),
                    group=(item.get("Group") or "").strip(),
                    is_car_ticket=bool(item.get("IsCarTicket", False)),
                    is_exclusion=bool(item.get("IsExclusion", False)),
                )
            )

        # ذخیره با بالاترین سرعت و جلوگیری از خطای duplicate key
        with transaction.atomic():
            Station.objects.bulk_create(
                station_instances,
                update_conflicts=True,
                update_fields=[
                    "name",
                    "english_name",
                    "tel_code",
                    "group",
                    "is_car_ticket",
                    "is_exclusion",
                ],
                unique_fields=["code"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"تعداد {len(station_instances)} ایستگاه با موفقیت در دیتابیس ثبت/به‌روزرسانی شد."
            )
        )
