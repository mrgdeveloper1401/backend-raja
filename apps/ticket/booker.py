import asyncio
import json
import time
from urllib import parse
# from urllib.parse import urlparse, parse_qs

import traceback
import random
from pathlib import Path

import httpx
from django.utils import timezone
from patchright.async_api import async_playwright
# from pypasser.captcha import arcaptcha

from apps.core.models import Station
from apps.ticket.models import ReservationAttempt, ReservationStatus
from apps.user.models import RajaAccount
from core.settings import TOKEN_REFRESH_MARGIN, RAJA_FRONT_API_KEY, RAJA_SITE
from core.utils.trains import create_rj_search_trains, TICKET_TYPE

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEPARTURE_SLOT_ENDS = {
    0: 6,
    6: 12,
    12: 18,
    18: 21,
    21: 24,
}


async def human_delay(min_ms=0.1, max_ms=0.2, default=None):
    if default:
        await asyncio.sleep(default)
        print(f"⏸️ تأخیر انسانی: {default:.1f} میلی‌ثانیه")
    else:
        delay = random.uniform(min_ms, max_ms)
        print(f"⏸️ تأخیر انسانی: {delay:.1f} میلی‌ثانیه")
        await asyncio.sleep(delay)


class RajaBooker:
    def __init__(
        self,
        account_id,
        origin,
        destination,
        travel_date,
        passengers,
        passenger_type,
        headless=False,
        attempt_id=None,
        is_exclusive=None,
        travel_phone=None,
        is_want_and_return=False,
        to_date=None,
        coupe_filter=None,
        from_price=None,
        to_price=None,
        train_number=None,
        departure_time_slots=None,
        adult=None,
        child=None,
        user_agent=None,
        raja_api_key=None,
        access_token=None,
        lg_uf=None
    ):
        self.account_id = account_id
        self.origin = origin
        self.destination = destination
        self.travel_date = travel_date
        self.passengers = passengers
        self.headless = headless
        self.attempt_id = attempt_id
        self.travel_phone = travel_phone
        self.page = None
        self.context = None
        self.is_want_and_return = is_want_and_return
        self.to_date = to_date
        self.passenger_type = passenger_type
        self.coupe_filter = coupe_filter
        self.is_exclusive = is_exclusive
        self.from_price = from_price
        self.to_price = to_price
        self.train_number = train_number
        self.departure_time_slots = departure_time_slots
        self.child = child
        self.adult = adult
        self.account = None
        self.api_q_param = None
        self.access_token = access_token
        self.expires_in = None
        self.lg_uf = lg_uf
        self.data = None
        self.accept_data = None
        self.user_agent = user_agent
        self.raja_api_key = raja_api_key
        self.selected_train = None  # ذخیره قطار انتخاب شده
        self.origin_code=None,
        self.destination_code=None,
        if self.raja_api_key is None:
            self.raja_api_key = RAJA_FRONT_API_KEY

    async def _update_status(
        self,
        status,
        payment_url=None,
        error_message=None,
        captcha_token=None,
        access_token=None,
        user_agent=None,
        accept_data=None,
        matching_trains=None,
        find_trains=None,
    ):
        if not self.attempt_id:
            return
        try:
            attempt = await ReservationAttempt.objects.select_related(
                "reservation"
            ).aget(id=self.attempt_id)
            attempt.status = status
            if payment_url:
                attempt.payment_url = payment_url
            if error_message:
                attempt.error_message = error_message
            if captcha_token:
                attempt.captcha_token = captcha_token
            if access_token:
                attempt.access_token = access_token
            if user_agent:
                attempt.user_agent = user_agent
            if accept_data:
                attempt.accept_data = accept_data
            if matching_trains:
                attempt.matching_trains = matching_trains
            if find_trains:
                attempt.find_trains = find_trains
            await attempt.asave()

        except Exception as e:
            print(f"خطا در آپدیت وضعیت: {e}")

    # async def _capture_api_params(self, response):
    #     if "TrainListEqWithCaptcha" in response.url:
    #         try:
    #             parsed_url = urlparse(response.url)
    #             query_params = parse_qs(parsed_url.query)
    #             if "q" in query_params:
    #                 self.api_q_param = query_params["q"][0]
    #                 print(f"✅ پارامتر q استخراج شد (طول: {len(self.api_q_param)})")
    #         except Exception as e:
    #             print(f"خطا در استخراج q: {e}")

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            async with async_playwright() as p:
                self.context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(
                        BASE_DIR / "raja_user_data" / f"attempt_{self.attempt_id}"
                    ),
                    channel="chrome",
                    headless=self.headless,
                    no_viewport=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                self.page = await self.context.new_page()
                print("رفتن به صفحه اصلی رجا...")
                await self.page.goto(
                    "https://www.raja.ir/", wait_until="domcontentloaded"
                )
                # await asyncio.sleep(2)

                # self.page.on("response", self._capture_api_params)

                check = (
                    self.access_token
                    and self.account.token_expires_at is not None
                    and self.account.token_expires_at
                    > timezone.now() + TOKEN_REFRESH_MARGIN
                )
                if not check:
                    await self._login()
                await self._set_local_storage()

                # create q
                await self._create_q()

                print("fill params ...")
                await self._fill_params()

                print("شروع رصد...")
                await self._monitor_and_book()

                # بعد از اینکه قطار پیدا شد و کلیک انجام شد، ادامه کارها
                print("در حال پر کردن اطلاعات مسافران...")
                await self._fill_passenger_details()

                print("در حال رفتن به پرداخت...")
                await self._go_to_payment()

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"خطای کلی در اجرای ربات:\n{error_trace}")
            await self._update_status(ReservationStatus.FAILED, error_message=str(e))

    async def _check_local_storage(self):
        access_token = await self.page.local_storage.get_item("Access_Token")
        if not access_token:
            print("اکسس توکن موجود نیست لاگین میکنیم")
            await self._login()
        print("اکسس توکن موجود هست", access_token)

    async def _login(self):
        url = "https://hostservice.raja.ir/token?ArCaptchaToken=undefined"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": RAJA_SITE,
            "Referer": RAJA_SITE,
        }
        data = {
            "username": self.account.username,
            "password": self.account.password,
            "grant_type": "password",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, data=data)
            if response.status_code == 200:
                data = response.json()
                # get data
                self.access_token = data.get("access_token")  # set access_token
                self.expires_in = data.get("expires_in")

                # save access_token in raja account
                self.account.access_token = self.access_token
                await self.account.asave(update_fields=["access_token", "updated_at"])

                await self._get_information()  # get information
                await human_delay(default=0.1)
                await self._set_local_storage()  # save into local storage browser
                await human_delay(default=0.1)
                print("لاگین با موفقیت انجام شد")
                return True
            elif response.status_code == 429:
                print("محدودیت درخواست ۳ ثانیه صبر میکنیم")
                await asyncio.sleep(3)
                return False
            else:
                print(f"❌ خطا در لاگین: {response.status_code}")
                print(f"پاسخ سرور: {response.text}")
                return False

    async def _create_q(self):
        # create q
        print(TICKET_TYPE[self.passenger_type])
        print("ساخت پارامتر q با استفاده از raja-mcp ...")
        res = await create_rj_search_trains(
            origin={'Code': self.origin_code},
            destination={'Code': self.destination_code},
            d=self.travel_date,
            passengers=len(self.passengers),
            ticket_type=TICKET_TYPE[self.passenger_type],
        )
        print(f"res {res}")
        return res

    async def _set_local_storage(self):
        if not self.access_token:
            print("⚠️ توکن موجود نیست. ابتدا لاگین میکنیم.")
            await self._login()
            await human_delay(default=0.1)

        token_with_bearer = f"bearer {self.access_token}"
        expiry_time = int((time.time() + 315360000) * 1000)
        ams_value = json.dumps({"_expired": expiry_time, "_value": "1"})

        try:
            await self.page.local_storage.set_item("Access_Token", token_with_bearer)
            await self.page.local_storage.set_item("LgUF", self.lg_uf)
            await self.page.local_storage.set_item("AMS", ams_value)
            print("✅ توکن و مقادیر مورد نیاز در Local Storage مرورگر ذخیره شد.")
            all_item = await self.page.local_storage.items()
            print("all item", all_item)

            # save local storage
            self.account.local_storage = all_item
            await self.account.asave(update_fields=["updated_at", "local_storage"])

        except Exception as e:
            print(f"خطا در ذخیره در Local Storage: {e}")

    async def _get_information(self):
        url = "https://hostservice.raja.ir/Api/ServiceProvider/GetInformation"
        headers = {
            "accept": "application/json",
            "api-key": self.raja_api_key,
            "Authorization": f"bearer {self.access_token}",
            "content-type": "application/json",
            "Origin": RAJA_SITE,
            "Referer": RAJA_SITE,
            "user-agent": self.user_agent,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    self.lg_uf = response.json()
                    print(f"✅ اطلاعات کاربر با موفقیت دریافت شد: {self.lg_uf}")
                    return True
                elif response.status_code == 429:
                    print("محدودیت درخواست رسیدیم ۳ثانیه صبر میکنیم")
                    await asyncio.sleep(3)
                    return False
                else:
                    print(
                        f"❌ خطا در دریافت اطلاعات کاربر: {response.status_code} - {response.text}"
                    )
                    print("لاگین مجدد")
                    await self._login()
                    return False

        except Exception as e:
            print(f"❌ خطا در اتصال: {e}")
            return False

    async def _fill_params(self):
        print("در حال ساخت URL و انتقال مستقیم به صفحه نتایج...")
        godate = self.travel_date.replace("-", "")
        returndate = self.to_date.replace("-", "") if self.to_date else ""

        ticket_type_map = {
            "normal": "Family",
            "man": "Male",
            "woman": "Famale",
        }
        tickettype = ticket_type_map.get(self.passenger_type, "Family")

        movetype = 2 if self.is_want_and_return else 1

        adult = self.adult if self.adult is not None else 1
        child = self.child if self.child is not None else 0
        infant = 0
        numberpassenger = adult + child + infant

        ischarter = "true" if self.is_exclusive else "false"

        origin = self.origin
        destination = self.destination
        get_origin = await Station.objects.filter(name=origin).afirst()
        get_destination = await Station.objects.filter(name=destination).afirst()
        or_code = get_origin.code
        self.origin_code = or_code
        des_code = get_destination.code
        self.destination_code = des_code

        desctravel_text = f"قطار {self.origin} به {self.destination}"
        desctravel = parse.quote(desctravel_text)

        url = (
            f"https://www.raja.ir/search?"
            f"adult={adult}&"
            f"child={child}&"
            f"infant={infant}&"
            f"movetype={movetype}&"
            f"ischarter={ischarter}&"
            f"fs={or_code}&"
            f"ts={des_code}&"
            f"godate={godate}&"
            f"tickettype={tickettype}&"
            f"returndate={returndate}&"
            f"numberpassenger={numberpassenger}&"
            f"mode=Train&"
            f"desctravel={desctravel}"
        )
        print("url", url)
        await self.page.goto(url, wait_until="networkidle")
        await human_delay(default=0.1)

    async def _monitor_and_book(self):
        await self._update_status(ReservationStatus.MONITORING)
        print(
            f"attempt={self.attempt_id} "
            f"departure_time_slots={self.departure_time_slots!r} "
            f"departure_time_slots={self.departure_time_slots!r}"
        )
        headers = {
            "Api-Key": self.raja_api_key,
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Origin": RAJA_SITE,
            "Referer": RAJA_SITE,
        }
        poll_interval = 0.5

        while True:
            try:
                if not self.context or not self.page or self.page.is_closed():
                    print("⚠️ مرورگر بسته شده است. خروج...")
                    await self._update_status(
                        ReservationStatus.FAILED, error_message="مرورگر بسته شد."
                    )
                    return

                # if not self.api_q_param:
                #     print("🔄 در حال دریافت q جدید از مرورگر...")
                #     self.api_q_param = None
                #     await self.page.reload(wait_until="domcontentloaded")
                #     for _ in range(20):
                #         if self.api_q_param:
                #             break
                #         await asyncio.sleep(0.1)
                #     if not self.api_q_param:
                #         print("⚠️ q استخراج نشد. تلاش مجدد...")
                #         await asyncio.sleep(0.1)
                #         continue

                # url = f"https://hostservice.raja.ir/Api/ServiceProvider/TrainListEqWithCaptcha?q={self.api_q_param}"
                url = await self._create_q()
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        response = await client.get(url, headers=headers)

                        if response.status_code == 200:
                            data = response.json()
                            trains = data.get("GoTrains", [])
                            matching_trains = []

                            for train in trains:
                                # فیلترها (شماره قطار، نوع کوپه، قیمت، زمان، ظرفیت)

                                # train number
                                print(self.train_number)
                                print(f"server train_number {train.get('TrainNumber')}")
                                if (
                                    self.train_number
                                    and str(train.get("TrainNumber"))
                                    not in self.train_number
                                ):
                                    continue

                                # coupe filter
                                if self.coupe_filter:
                                    wagon_name = train.get("WagonName", "")
                                    coupe_keywords = {
                                        "four": [
                                            "4 تخته",
                                            "4تخته",
                                            "چهار تخته",
                                            "چهارتخته",
                                            "4 ستاره",
                                            "4ستاره",
                                            "چهار ستاره",
                                            "چهارستاره",
                                        ],
                                        "five": [
                                            "5 ستاره",
                                            "5ستاره",
                                            "پنج ستاره",
                                            "پنجستاره",
                                        ],
                                        "three": [
                                            "6 تخته",
                                            "6تخته",
                                            "شش تخته",
                                            "ششتخته",
                                            "3 ستاره",
                                            "3ستاره",
                                            "سه ستاره",
                                            "سهستاره",
                                        ],
                                        "salon": ["سالنی", "سالن", "اتوبوسي"],
                                    }
                                    if self.coupe_filter == "four":
                                        if (
                                            "سالنی" in wagon_name
                                            or "سالن" in wagon_name
                                            or "اتوبوسي" in wagon_name
                                        ):
                                            continue
                                    keywords = coupe_keywords.get(self.coupe_filter, [])
                                    if keywords and not any(
                                        kw in wagon_name for kw in keywords
                                    ):
                                        continue

                                # price
                                cost = train.get("Cost", 0)
                                print(f"cost {cost}")
                                if self.from_price and cost < (
                                    int(self.from_price) * 10
                                ):
                                    continue
                                if self.to_price and cost > (int(self.to_price) * 10):
                                    continue

                                # move time
                                if self.departure_time_slots:
                                    try:
                                        hour_str, minute_str = (
                                            train["ExitTime"].strip().split(":")
                                        )
                                        exit_hour = int(hour_str)
                                        exit_minute = int(minute_str)
                                    except KeyError, AttributeError, ValueError:
                                        continue

                                    if not (
                                        0 <= exit_hour < 24 and 0 <= exit_minute < 60
                                    ):
                                        continue

                                    if not any(
                                        start_hour
                                        <= exit_hour
                                        < DEPARTURE_SLOT_ENDS[start_hour]
                                        for start_hour in self.departure_time_slots
                                        if start_hour in DEPARTURE_SLOT_ENDS
                                    ):
                                        continue
                                if (
                                    train.get("IsDisabled", True)
                                    or train.get("Counting", 0) <= 0
                                ):
                                    continue

                                # کوپه دربست
                                available_seats = train.get("Counting")
                                if self.is_exclusive:
                                    if (
                                        self.coupe_filter == "four"
                                        and available_seats < 4
                                    ):
                                        continue
                                    if (
                                        self.coupe_filter == "three"
                                        and available_seats < 6
                                    ):
                                        continue

                                matching_trains.append(train)

                            print(
                                f"🎯 {len(matching_trains)} قطار با فیلترهای شما مطابقت دارند."
                            )

                            if matching_trains:
                                selected_train = matching_trains[0]
                                self.selected_train = selected_train
                                print(
                                    f"attempt={self.attempt_id} "
                                    f"selected_train={selected_train.get('TrainNumber')!r} "
                                    f"exit_time={selected_train.get('ExitTime')!r}"
                                )

                                await self._update_status(
                                    status=ReservationStatus.MATCH_TRAIN,
                                    matching_trains=matching_trains,
                                    find_trains=selected_train,
                                )

                                # ⭐️ مرحله جدید: کلیک روی قطار در مرورگر
                                success = await self._click_train_button(selected_train)
                                if success:
                                    print(
                                        "🎉 کلیک روی دکمه رزرو انجام شد. رفتن به مرحله بعد..."
                                    )
                                    return  # خروج از حلقه رصد، ادامه در start()
                                else:
                                    print("⚠️ کلیک ناموفق بود. بازگشت به رصد...")
                                    await asyncio.sleep(1)
                                    continue
                            else:
                                print(
                                    "⏳ قطاری با فیلترهای شما پیدا نشد. در حال انتظار..."
                                )

                        elif response.status_code == 400:
                            print("⚠️ q منقضی شده است. دریافت q جدید...")
                            self.api_q_param = None
                            continue
                        elif response.status_code == 429:
                            print("⚠️ خطای 429. 5 ثانیه صبر...")
                            await asyncio.sleep(5)
                        else:
                            print(
                                f"❌ خطای API: {response.status_code} - {response.text[:200]}"
                            )

                except httpx.TimeoutException:
                    print("⚠️ تایم‌اوت در اتصال به API.")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️ خطا در درخواست API: {e}")
                    await asyncio.sleep(2)

                await asyncio.sleep(poll_interval)

            except Exception as e:
                error_msg = str(e)
                if (
                    "Target page, context or browser has been closed" in error_msg
                    or "has been closed" in error_msg
                ):
                    print("⚠️ خطای بسته شدن مرورگر در حلقه رصد. خروج...")
                    await self._update_status(
                        ReservationStatus.FAILED, error_message="مرورگر بسته شد."
                    )
                    return
                print(f"خطا در حلقه رصد: {e}")
                await asyncio.sleep(poll_interval)

    async def _click_train_button(self, train):
        """پیدا کردن قطار در DOM و کلیک روی دکمه رزرو آن"""
        try:
            print("🔄 رفرش صفحه برای دیدن قطار...")
            print(f"train number found {train}")
            await self.page.reload(wait_until="networkidle")

            # پیدا کردن کارت قطار بر اساس شماره قطار و نوع واگن
            train_number = train["TrainNumber"]
            wagon_name = train["WagonName"]

            # جستجو برای کارتی که شامل شماره قطار و نام سالن باشد
            card = self.page.locator(
                f".train-result:has-text('{train_number}'):has-text('{wagon_name}')"
            ).first
            if await card.count() == 0:
                print(f"⚠️ کارت قطار {train_number} در DOM پیدا نشد.")
                return False

            # پیدا کردن دکمه رزرو درون کارت
            book_btn = card.locator("button.lock-btn:has-text('رزرو بلیت')").first

            if await book_btn.count() > 0 and await book_btn.is_enabled():
                print(f"✅ کلیک روی دکمه رزرو برای قطار {train_number}...")
                await book_btn.click()
                await human_delay(default=0.1)

                # ⭐️ صبر می‌کنیم تا دکمه "ادامه خرید" در صفحه ظاهر شود
                print("منتظر ظاهر شدن دکمه ادامه خرید...")
                continue_btn = self.page.locator(
                    "button.btn-success:has-text('ادامه خرید')"
                ).first
                await human_delay(default=0.1)

                # حداکثر 10 ثانیه صبر می‌کنیم تا دکمه ظاهر شود
                try:
                    await continue_btn.wait_for(state="visible", timeout=10000)
                    print("✅ دکمه ادامه خرید پیدا شد. کلیک می‌کنیم...")
                    await continue_btn.click()
                    await human_delay(default=0.1)
                except Exception as e:
                    print(f"⚠️ دکمه ادامه خرید پیدا نشد: {e}")
                    # اگر پیدا نشد، ممکن است سایت مستقیم به صفحه بعد رفته باشد
                    pass

                # منتظر می‌مانیم تا به صفحه بعد برود
                await self.page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
                return True
            else:
                print(f"⚠️ دکمه رزرو برای قطار {train_number} غیرفعال است.")
                return False

        except Exception as e:
            print(f"خطا در کلیک روی دکمه رزرو: {e}")
            return False

    async def _fill_passenger_details(self):
        await human_delay(default=0.1)
        print("در حال پر کردن مشخصات مسافران...")

        # منتظر می‌مانیم تا فرم مسافران لود شود
        try:
            await self.page.get_by_text("کد ملی/شماره پاسپورت").first.wait_for(
                state="visible", timeout=25000
            )
            print("فرم مسافران با موفقیت لود شد.")
        except Exception as e:
            print(f"خطا در لود فرم مسافران {e}")
            print("ادامه برنامه")

        await human_delay(default=0.1)

        # پیدا کردن همه بلوک‌های مسافر
        passenger_blocks = self.page.locator(".passanger-registor").filter(
            has=self.page.get_by_text("کد ملی/شماره پاسپورت")
        )

        count = await passenger_blocks.count()
        print(f"تعداد بلوک‌های مسافر پیدا شده: {count}")

        # حلقه روی مسافران (بر اساس لیست passengers که از دیتابیس آمده)
        for i, passenger in enumerate(self.passengers):
            if i >= count:
                print(f"هشدار: بلوک برای مسافر {i + 1} پیدا نشد.")
                break

            block = passenger_blocks.nth(i)
            print(f"--- در حال پردازش مسافر {i + 1} ---")

            # ۱. پر کردن کد ملی
            try:
                await human_delay(default=0.1)
                national_id = passenger.get("national_id")
                if national_id:
                    # پیدا کردن اینپوت کد ملی در این بلوک
                    # در HTML شما، اینپوت کد ملی بعد از لیبل "کد ملی/شماره پاسپورت" قرار دارد
                    input_locator = block.locator("input[type='text']").first
                    await input_locator.fill(str(national_id))
                    print(f"کد ملی مسافر {i + 1} پر شد: {national_id}")
            except Exception as e:
                print(f"خطا در پر کردن کد ملی مسافر {i + 1}: {e}")
                print("ادامه برنامه")

            # ۲. پر کردن تاریخ تولد
            try:
                await human_delay(default=0.1)
                birth_date = passenger.get("birth_date")
                if birth_date:
                    # در HTML شما، اینپوت تاریخ تولد دارای title="روز/ماه/سال" است
                    birth_input = block.locator("input[title='روز/ماه/سال']")
                    if await birth_input.count() > 0:
                        await birth_input.fill(str(birth_date))
                        print(f"تاریخ تولد مسافر {i + 1} پر شد: {birth_date}")
                    else:
                        # اگر title پیدا نشد، از tabindex استفاده می‌کنیم (به عنوان fallback)
                        # tabindex برای مسافر اول 12، دوم 22، سوم 32 است
                        tab_index = 12 + (i * 10)
                        birth_input = block.locator(f"input[tabindex='{tab_index}']")
                        if await birth_input.count() > 0:
                            await birth_input.fill(str(birth_date))
                            print(
                                f"تاریخ تولد مسافر {i + 1} (با tabindex) پر شد: {birth_date}"
                            )
            except Exception as e:
                print(f"خطا در پر کردن تاریخ تولد مسافر {i + 1}: {e}")
                print("ادامه برنامه")

            # ۳. پر کردن نام (اگر فیلد قابل ویرایش وجود داشت)
            try:
                await human_delay(default=0.1)
                first_name = passenger.get("first_name")
                if first_name:
                    # در HTML شما نام به صورت input دیده نمی‌شود،
                    # اما اگر وجود داشت، سعی می‌کنیم پر کنیم
                    name_input = block.locator("input[name='pName']")
                    if await name_input.count() > 0:
                        await name_input.fill(str(first_name))
                        print(f"نام مسافر {i + 1} پر شد: {first_name}")
            except Exception as e:
                print(f"خطا در لود فیلد نام {e}")
                print("ادامه برنامه")

            # ۴. پر کردن نام خانوادگی (اگر فیلد قابل ویرایش وجود داشت)
            try:
                await human_delay(default=0.1)
                last_name = passenger.get("last_name")
                if last_name:
                    family_input = block.locator("input[name='pFamily']")
                    if await family_input.count() > 0:
                        await family_input.fill(str(last_name))
                        print(f"نام خانوادگی مسافر {i + 1} پر شد: {last_name}")
            except Exception as e:
                print(f"خطا در لود فیلد نام خوانوادگی {e}")
                print("ادامه برنامه")

            # ۵. انتخاب نوع مسافر (بزرگسال / خردسال)
            # try:
            #     await human_delay(default=0.1)
            #     is_adult = passenger.get("is_adult", True)
            #     # پیدا کردن سلکت نوع مسافر در این بلوک
            #     type_select = block.locator("select").first
            #     if await type_select.count() > 0:
            #         # مقدار 1 برای بزرگسال، 2 برای خردسال
            #         value = "1" if is_adult else "2"
            #         await type_select.select_option(value=value)
            #         print(f"نوع مسافر {i + 1} انتخاب شد: {'بزرگسال' if is_adult else 'خردسال'}")
            # except Exception as e:
            #     print(f"خطا در انتخاب نوع مسافر {i + 1}: {e}")

        print("عملیات پر کردن مشخصات مسافران به پایان رسید.")

    async def _go_to_payment(self):
        print("در حال تیک زدن قوانین و رفتن به پرداخت...")
        await human_delay(default=0.1)

        # تیک قوانین
        try:
            await self.page.locator(
                "label.custom-control-label:has-text('صحت مشخصات')"
            ).click()
            await human_delay(default=0.1)
        except Exception as e:
            print(f"خطا {e}")
            print("ادامه برنامه")
            await human_delay(default=0.1)

        # شماره موبایل
        try:
            phone_input = self.page.locator("input.phonenumber")
            await phone_input.wait_for(state="visible")
            if self.travel_phone and not await phone_input.input_value():
                await phone_input.type(self.travel_phone, delay=60)
                await human_delay(default=0.1)
        except Exception as e:
            print(f"خطا در وارد کردن موبایل {e}")
            print("ادامه برنامه")

        await human_delay(default=0.1)

        # print("کلیک روی دکمه پرداخت اولیه...")
        # await self.page.locator("button.btn-success:has-text('پرداخت')").click()
        # await human_delay(default=0.1)

        # print("در حال منتظر ماندن برای لود شدن کپچا...")
        # کلیک بر روی دکمه من ربات نیستم
        # captcha_box = self.page.locator("#input-checkbox")
        # await captcha_box.wait_for(state="visible", timeout=25000)
        # await human_delay(default=0.1)

        # await captcha_box.click()

        # print("منتظر حل شدن کپچا...")
        # await human_delay(1, 2)

        # حل کپچا
        # result = await arcaptcha.asolve(
        #     page=self.page, site="t8xr2hpxue", domain="www.raja.ir"
        # )
        # if result.is_solved:
        #     token = result.response_token
        #     print("Token:", token)
        #     await self._update_status(
        #         captcha_token=result.response_token, status=ReservationStatus.CAPTCHA
        #     )
        #
        #     # تزریق توکن به فیلد مخفی
        #     await self.page.evaluate(f"""
        #         () => {{
        #             let input = document.querySelector('input[name="arcaptcha-token"]');
        #             if (!input) {{
        #                 input = document.createElement('input');
        #                 input.type = 'hidden';
        #                 input.name = 'arcaptcha-token';
        #                 document.querySelector('form')?.appendChild(input);
        #             }}
        #             input.value = '{token}';
        #         }}
        #     """)
        #     print("کپچا با موفقیت حل شد")
        #     await human_delay(default=0.1)

        payment_url = self.page.url
        print(f"لینک درگاه نهایی: {payment_url}")
        await self._update_status(
            ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
        )
        print("به درگاه پرداخت رسیدیم برای خارج شدن از مرورگر فقط مرورگر رو ببندید")
        await self.page.pause()
