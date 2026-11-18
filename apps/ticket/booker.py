# apps/ticket/booker.py
import asyncio
import json
import time
from urllib.parse import urlparse, parse_qs
from urllib import parse

import traceback
import random
from pathlib import Path

import httpx
from patchright.async_api import async_playwright
from pypasser.captcha import arcaptcha

from apps.core.models import Station
from apps.ticket.models import ReservationAttempt, ReservationStatus
from apps.user.models import RajaAccount

BASE_DIR = Path(__file__).resolve().parent.parent.parent


async def human_delay(min_ms=0.1, max_ms=0.2, default=None):
    """تأخیر تصادفی انسانی"""
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
        departure_time_from=None,
        departure_time_to=None,
        adult=None,
        child=None,
        user_agent=None,
        raja_api_key=None,
        access_token=None,
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
        self.departure_time_from = departure_time_from
        self.departure_time_to = departure_time_to
        self.child = child
        self.adult = adult
        self.account = None
        self.api_q_param = None
        self.access_token = access_token
        self.expires_in = None
        self.lg_uf = None
        self.data = None
        self.accept_data = None
        self.user_agent = user_agent
        self.raja_api_key = raja_api_key

    async def _capture_api_params(self, response):
        """لیسنر برای استخراج پارامتر q از پاسخ API"""
        if "TrainListEqWithCaptcha" in response.url:
            try:
                parsed_url = urlparse(response.url)
                query_params = parse_qs(parsed_url.query)
                if "q" in query_params:
                    self.api_q_param = query_params["q"][0]
                    print(f"✅ پارامتر q استخراج شد (طول: {len(self.api_q_param)})")
            except Exception as e:
                print(f"خطا در استخراج q: {e}")

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            browser_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            async with async_playwright() as p:
                print("در حال راه اندازی ")

                self.context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(
                        BASE_DIR / "raja_user_data" / f"attempt_{self.attempt_id}"
                    ),
                    channel="chrome",
                    headless=self.headless,
                    no_viewport=True,
                    args=browser_args,
                )

                self.page = await self.context.new_page()

                # ✅ ثبت لیسنر قبل از هر کاری
                self.page.on("response", self._capture_api_params)

                # check login
                if not self.access_token:
                    # login user
                    print("در حال لاگین")
                    await self._login()

                # user info
                await self._get_information()

                # پر کردن فرم جستجو
                print("fill params ...")
                await self._fill_params()

                # ۳. رصد و رزرو
                print("شروع رصد...")
                await self._monitor_and_book()

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"خطای کلی در اجرای ربات:\n{error_trace}")
            await self._update_status(ReservationStatus.FAILED, error_message=str(e))
        # finally:
        #     if self.context is not None:
        #         try:
        #             if self.page and not self.page.is_closed():
        #                 await self.context.close()
        #                 print("مرورگر با موفقیت بسته شد.")
        #         except Exception as close_error:
        #             print(f"مرورگر از قبل بسته شده بود یا خطا در بستن: {close_error}")

    async def _get_information(self):
        url = "https://hostservice.raja.ir/Api/ServiceProvider/GetInformation"
        headers = {
            "accept": "application/json",
            "api-key": self.raja_api_key,
            "Authorization": f"bearer {self.access_token}",
            "content-type": "application/json",
            "origin": "https://www.raja.ir",
            "user-agent": self.user_agent,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    self.lg_uf = response.json()
                    print(f"✅ اطلاعات کاربر با موفقیت دریافت شد: {self.lg_uf}")
                    return True
                else:
                    print(
                        f"❌ خطا در دریافت اطلاعات کاربر: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            print(f"❌ خطا در اتصال: {e}")
            return False

    async def _set_local_storage(self):
        if not self.access_token:
            print("⚠️ توکن موجود نیست. ابتدا لاگین کنید.")
            return

        token_with_bearer = f"bearer {self.access_token}"
        expiry_time = int((time.time() + 315360000) * 1000)
        ams_value = json.dumps({"_expired": expiry_time, "_value": "1"})

        script = f"""
            () => {{
                // ذخیره Access_Token
                localStorage.setItem('Access_Token', '{token_with_bearer}');

                // ذخیره AMS (برای جلوگیری از خطای انقضا در انگولار)
                localStorage.setItem('AMS', '{ams_value}');

                // ذخیره LgUF (نام کاربری برای نمایش در هدر)
                localStorage.setItem('LgUF', '{self.lg_uf}');

                console.log('Local Storage با موفقیت تنظیم شد.');
            }}
        """

        try:
            await self.page.evaluate(script)
            print("✅ توکن و مقادیر مورد نیاز در Local Storage مرورگر ذخیره شد.")
        except Exception as e:
            print(f"خطا در ذخیره در Local Storage: {e}")

    async def _login(self):
        url = "https://hostservice.raja.ir/token?ArCaptchaToken=undefined"
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.raja.ir",
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
                self.access_token = data.get("access_token")
                await self._update_status(
                    access_token=self.access_token, status=ReservationStatus.PENDING
                )
                self.expires_in = data.get("expires_in")
                await self._set_local_storage()
                print("لاگین با موفقیت انجام شد")
                await self._get_information()
                return True
            else:
                print(f"❌ خطا در لاگین: {response.status_code}")
                print(f"پاسخ سرور: {response.text}")
                return False

    async def _update_status(
        self,
        status,
        payment_url=None,
        error_message=None,
        captcha_token=None,
        access_token=None,
        user_agent=None,
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
            await attempt.asave()

        except Exception as e:
            print(f"خطا در آپدیت وضعیت: {e}")

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
        des_code = get_destination.code

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
        await human_delay()

    async def _monitor_and_book(self):
        await self._update_status(ReservationStatus.MONITORING)

        api_key = self.raja_api_key
        headers = {
            "Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        poll_interval = 2  # check api

        while True:
            try:
                # ۱. بررسی بسته شدن مرورگر
                if not self.context or not self.page or self.page.is_closed():
                    print("⚠️ مرورگر بسته شده است. خروج...")
                    await self._update_status(
                        ReservationStatus.FAILED, error_message="مرورگر بسته شد."
                    )
                    return

                # ۲. اگر q نداریم یا منقضی شده، از مرورگر بگیر
                if not self.api_q_param:
                    print("🔄 در حال دریافت q جدید از مرورگر...")
                    self.api_q_param = None  # ریست کردن برای دریافت مجدد
                    await self.page.reload(wait_until="domcontentloaded")

                    for _ in range(20):
                        if self.api_q_param:
                            break
                        await asyncio.sleep(0.1)

                    if not self.api_q_param:
                        print("⚠️ q استخراج نشد. تلاش مجدد...")
                        await asyncio.sleep(0.5)
                        continue

                # ۳. درخواست به API
                url = f"https://hostservice.raja.ir/Api/ServiceProvider/TrainListEqWithCaptcha?q={self.api_q_param}"

                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        response = await client.get(url, headers=headers)

                        if response.status_code == 200:
                            data = response.json()
                            trains = data.get("GoTrains", [])
                            print(
                                f"📡 {len(trains)} قطار دریافت شد. در حال بررسی فیلترها..."
                            )

                            # ۴. اعمال فیلترها
                            matching_trains = []
                            for train in trains:
                                # فیلتر شماره قطار
                                if self.train_number and str(
                                    train.get("TrainNumber")
                                ) != str(self.train_number):
                                    continue

                                # فیلتر نوع کوپه (بر اساس WagonName)
                                if self.coupe_filter:
                                    wagon_name = train.get("WagonName", "")
                                    # نگاشت مقادیر به کلمات کلیدی موجود در WagonName
                                    coupe_keywords = {
                                        "four": "4 تخته",
                                        "four_five": "5 تخته",
                                        "five": "5 ستاره",
                                        "three": "3 ستاره",
                                        "salon": "سالنی",
                                    }
                                    keyword = coupe_keywords.get(self.coupe_filter, "")
                                    if keyword and keyword not in wagon_name:
                                        continue

                                # فیلتر قیمت (Cost به ریال است)
                                cost = train.get("Cost", 0)
                                # کاربر قیمت را به هزار تومان وارد کرده (مثلا 1500 = 1,500,000 تومان = 15,000,000 ریال)
                                if self.from_price and cost < (self.from_price * 10000):
                                    continue
                                if self.to_price and cost > (self.to_price * 10000):
                                    continue

                                # فیلتر زمان حرکت (ExitTime به فرمت "HH:MM")
                                exit_time_str = train.get("ExitTime", "")
                                if (
                                    self.departure_time_from is not None
                                    or self.departure_time_to is not None
                                ):
                                    try:
                                        exit_hour = int(exit_time_str.split(":")[0])
                                        if (
                                            self.departure_time_from is not None
                                            and exit_hour < self.departure_time_from
                                        ):
                                            continue
                                        if (
                                            self.departure_time_to is not None
                                            and exit_hour > self.departure_time_to
                                        ):
                                            continue
                                    except:
                                        pass

                                # بررسی ظرفیت (باید بلیط موجود باشد)
                                if (
                                    train.get("IsDisabled", True)
                                    or train.get("Counting", 0) <= 0
                                ):
                                    continue

                                matching_trains.append(train)

                            print(
                                f"🎯 {len(matching_trains)} قطار با فیلترهای شما مطابقت دارند."
                            )

                            if matching_trains:
                                # انتخاب اولین قطار مناسب
                                selected_train = matching_trains[0]
                                print(
                                    f"✅ قطار انتخاب شد: {selected_train['TrainNumber']} - {selected_train['WagonName']} - قیمت: {selected_train['CostDisplay']}"
                                )

                                # ۵. آماده‌سازی داده برای رزرو
                                # تبدیل تاریخ ShamsiMoveDate به فرمت میلادی برای API
                                # در اینجا از ExitDateTime استفاده می‌کنیم که فرمت ISO دارد
                                move_date_iso = selected_train.get("ExitDateTime", "")[
                                    :10
                                ]  # "2026-11-21"

                                accept_data = {
                                    "MoveType": "1"
                                    if self.is_exclusive
                                    else "2",  # 1 برای تک سفر، 2 برای رفت و برگشت
                                    "GoLockSeat": {
                                        "TrainNo": selected_train["TrainNumber"],
                                        "MoveDate": selected_train.get(
                                            "MoveDate", ""
                                        ),  # تاریخ میلادی
                                        "StartStation": selected_train["FromStation"],
                                        "ToStation": selected_train["ToStation"],
                                        "RationCode": selected_train.get(
                                            "RationCode", 2
                                        ),
                                        "WagonType": selected_train["WagonType"],
                                        "SexCode": selected_train.get("SexCode", 3),
                                        "SeatCount": "1",  # تعداد مسافران
                                        "Degree": selected_train.get("degree", 1),
                                        "SellMaster": 0,
                                        "CapacityCompartment": selected_train.get(
                                            "CompartmentCapicity", 4
                                        ),
                                        "AppCode": 2,
                                        "Checksum": "",
                                        "CircolarNumberSerial": selected_train.get(
                                            "CircularNumberSerial"
                                        ),
                                        "SoldCount": 0,
                                        "pIsExclusive": 0,
                                    },
                                }

                                # اگر تعداد مسافران بیشتر از 1 است، SeatCount را تغییر بده
                                total_passengers = len(self.passengers)
                                accept_data["GoLockSeat"]["SeatCount"] = str(
                                    total_passengers
                                )

                                self.accept_data = accept_data

                                # ۶. تلاش برای رزرو
                                print("🔒 در حال تلاش برای رزرو...")
                                success = await self._reservation_ticket()

                                if success:
                                    print("🎉 رزرو با موفقیت انجام شد!")
                                    # لینک پرداخت را از پاسخ بگیرید
                                    return
                                else:
                                    print("⚠️ رزرو ناموفق بود. تلاش مجدد...")
                                    await asyncio.sleep(0.5)
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
                            print(
                                "⚠️ خطای 429 در دریافت لیست قطارها. 3 ثانیه صبر می‌کنیم..."
                            )
                            await asyncio.sleep(3)
                        else:
                            print(
                                f"❌ خطای API: {response.status_code} - {response.text[:200]}"
                            )

                except httpx.TimeoutException:
                    print("⚠️ تایم‌اوت در اتصال به API. تلاش مجدد...")
                except Exception as e:
                    print(f"⚠️ خطا در درخواست API: {e}")

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

    async def _reservation_ticket(self):
        url = "https://hostservice.raja.ir/Api/ServiceProvider/LockSeat"
        headers = {
            "Api-Key": self.raja_api_key,
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            "Origin": "https://www.raja.ir",
            "Host": "hostservice.raja.ir",
            "Authorization": f"bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url, headers=headers, json=self.accept_data
                )

                if response.status_code == 200:
                    res_data = response.json()
                    print("✅ رزرو با موفقیت انجام شد.")
                    print(f"پاسخ سرور: {res_data}")

                    go_output = res_data.get("GoOutputLock", {})
                    if go_output:
                        sell_serial = go_output.get("SellSerial")
                        sell_master_id = go_output.get("SellMasterId")
                        print(
                            f"SellSerial: {sell_serial}, SellMasterId: {sell_master_id}"
                        )

                        # ساخت لینک ورود به لیست مسافران
                        # https://www.raja.ir/registerticket?saleId=33284837-401e-3410-f1e0-a44cb4c40809
                        # https://www.raja.ir/registerticket?saleId={SellMasterId}

                        # پس از رزرو موفق، مرورگر را به صفحه ثبت نام هدایت می‌کنیم
                        payment_url = f"https://www.raja.ir/registerticket?saleId={sell_master_id}"
                        print(f"لینک پرداخت: {payment_url}")

                        await self._update_status(
                            ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
                        )

                        # هدایت مرورگر به صفحه ثبت نام
                        await self.page.goto(payment_url, wait_until="networkidle")

                        await self.page.pause()

                        # ادامه کارها (پر کردن اطلاعات مسافران)
                        # ...
                        return True
                    else:
                        print("⚠️ پاسخ رزرو حاوی GoOutputLock نیست.")
                        return False
                elif response.status_code == 429:
                    print("⚠️ خطای 429: درخواست‌های زیاد. 3 ثانیه صبر می‌کنیم...")
                    await asyncio.sleep(3)
                else:
                    print(
                        f"❌ عدم موفقیت در رزرو: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            print(f"❌ خطا در درخواست رزرو: {e}")
            return False

    async def _fill_passenger_details(self):
        await human_delay()
        print("در حال پر کردن مشخصات مسافران...")

        # منتظر می‌مانیم تا فرم مسافران لود شود
        await self.page.get_by_text("کد ملی/شماره پاسپورت").first.wait_for(
            state="visible", timeout=15000
        )
        print("فرم مسافران با موفقیت لود شد.")

        await human_delay()

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
                await human_delay()
                national_id = passenger.get("national_id")
                if national_id:
                    # پیدا کردن اینپوت کد ملی در این بلوک
                    # در HTML شما، اینپوت کد ملی بعد از لیبل "کد ملی/شماره پاسپورت" قرار دارد
                    input_locator = block.locator("input[type='text']").first
                    await input_locator.fill(str(national_id))
                    print(f"کد ملی مسافر {i + 1} پر شد: {national_id}")
            except Exception as e:
                print(f"خطا در پر کردن کد ملی مسافر {i + 1}: {e}")

            # ۲. پر کردن تاریخ تولد
            try:
                await human_delay()
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

            # ۳. پر کردن نام (اگر فیلد قابل ویرایش وجود داشت)
            try:
                await human_delay()
                first_name = passenger.get("first_name")
                if first_name:
                    # در HTML شما نام به صورت input دیده نمی‌شود،
                    # اما اگر وجود داشت، سعی می‌کنیم پر کنیم
                    name_input = block.locator("input[name='pName']")
                    if await name_input.count() > 0:
                        await name_input.fill(str(first_name))
                        print(f"نام مسافر {i + 1} پر شد: {first_name}")
            except Exception as e:
                # اگر فیلد نام وجود نداشت، خطا را نادیده می‌گیریم
                pass

            # ۴. پر کردن نام خانوادگی (اگر فیلد قابل ویرایش وجود داشت)
            try:
                await human_delay()
                last_name = passenger.get("last_name")
                if last_name:
                    family_input = block.locator("input[name='pFamily']")
                    if await family_input.count() > 0:
                        await family_input.fill(str(last_name))
                        print(f"نام خانوادگی مسافر {i + 1} پر شد: {last_name}")
            except Exception as e:
                # اگر فیلد نام خانوادگی وجود نداشت، خطا را نادیده می‌گیریم
                pass

            # ۵. انتخاب نوع مسافر (بزرگسال / خردسال)
            # try:
            #     await human_delay()
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
        await human_delay()

        # تیک قوانین
        try:
            await self.page.locator(
                "label.custom-control-label:has-text('صحت مشخصات')"
            ).click()
            await human_delay()
        except:
            await self.page.locator(
                "div.custom-control.custom-checkbox input[type='checkbox']"
            ).first.check(force=True)
            await human_delay()

        # شماره موبایل
        try:
            phone_input = self.page.locator("input.phonenumber")
            await phone_input.wait_for(state="visible")
            if self.travel_phone and not await phone_input.input_value():
                await phone_input.type(self.travel_phone, delay=60)
                await human_delay()
        except:
            pass

        await human_delay()

        print("کلیک روی دکمه پرداخت اولیه...")
        await self.page.locator("button.btn-success:has-text('پرداخت')").click()
        await human_delay()

        print("در حال منتظر ماندن برای لود شدن کپچا...")
        # کلیک بر روی دکمه من ربات نیستم
        captcha_box = self.page.locator("#input-checkbox")
        await captcha_box.wait_for(state="visible", timeout=15000)
        await human_delay()

        await captcha_box.click()

        print("منتظر حل شدن کپچا...")
        await human_delay(1, 2)

        # حل کپچا
        result = await arcaptcha.asolve(
            page=self.page, site_key="t8xr2hpxue", domain="www.raja.ir"
        )
        if result.is_solved:
            token = result.response_token
            print("Token:", token)
            await self._update_status(
                captcha_token=result.response_token, status=ReservationStatus.CAPTCHA
            )

            # تزریق توکن به فیلد مخفی
            await self.page.evaluate(f"""
                () => {{
                    let input = document.querySelector('input[name="arcaptcha-token"]');
                    if (!input) {{
                        input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'arcaptcha-token';
                        document.querySelector('form')?.appendChild(input);
                    }}
                    input.value = '{token}';
                }}
            """)
            print("کپچا با موفقیت حل شد")
            await human_delay()

        payment_url = self.page.url
        print(f"لینک درگاه نهایی: {payment_url}")
        await self._update_status(
            ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
        )
        print("به درگاه پرداخت رسیدیم برای خارج شدن از مرورگر فقط مرورگر رو ببندید")
        await self.page.pause()
