# apps/ticket/booker.py
import asyncio
import re

import traceback
import random
from pathlib import Path


from patchright.async_api import async_playwright
from pypasser.captcha import arcaptcha

from apps.ticket.models import ReservationAttempt, ReservationStatus
from apps.user.models import RajaAccount
from core.settings import IS_WINDOWS

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def log_request(request):
    if request.resource_type in ["xhr", "fetch"]:
        print(f"--> {request.method} {request.url}")
        print("Headers", request.headers)
        if request.post_data:
            print("body", request.post_data)


def log_response(response):
    if response.request.resource_type in ["xhr", "fetch"]:
        print(f"<-- {response.status} {response.url}")
        print("response body", response.text)


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
        # reservation_id=None,
        attempt_id=None,
        travel_phone=None,
        browser=None,
        is_want_and_return=False,
        to_date=None,
        coupe_filter=None,
        order_by_filter=None,
    ):
        self.account_id = account_id
        self.origin = origin
        self.destination = destination
        self.travel_date = travel_date
        self.passengers = passengers
        self.headless = headless
        # self.reservation_id = reservation_id
        self.attempt_id = attempt_id
        self.travel_phone = travel_phone
        self.page = None
        self.context = None
        self.is_want_and_return = is_want_and_return
        self.to_date = to_date
        self.passenger_type = passenger_type
        self.coupe_filter = coupe_filter
        self.order_by_filter = order_by_filter

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            data = {
                "origin": self.origin,
                "destination": self.destination,
                "travel_date": self.travel_date,
                "to_date": self.to_date,
                "is_want_and_return": self.is_want_and_return,
                "travel_phone": self.travel_phone,
                "passengers": self.passengers,
            }
            print("اطلاعات کاربر", data)

            browser_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            async with async_playwright() as p:
                print("در حال راه‌اندازی مرورگر با Patchright...")

                self.context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(
                        BASE_DIR / "raja_user_data" / f"attempt_{self.attempt_id}"
                    ),
                    channel="chrome",
                    headless=self.headless,
                    no_viewport=True,
                    slow_mo=100,
                    args=browser_args,
                )
                if IS_WINDOWS:
                    self.context.executable_path = (
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    )
                    self.context.channel = None

                self.page = await self.context.new_page()
                self.page.set_default_timeout(20000)
                await self.page.goto("https://raja.ir/", wait_until="networkidle")

                # ✅ پاک کردن state سشن قبلی (بدون لمس کوکی‌های لاگین)
                await self.page.evaluate("""() => {
                    localStorage.clear();
                    sessionStorage.clear();
                }""")

                # ریلود تا سایت با storage پاک شروع کنه
                await self.page.goto("https://raja.ir/", wait_until="networkidle")

                # ۱. چک لاگین
                # is_logged_in = await self._check_login()
                # if not is_logged_in:
                print("شروع لاگین...")
                await self._do_login()
                print("لاگین انجام شد.")

                # ۲. پر کردن فرم جستجو
                print("ورود موفق! شروع تنظیم فرم...")
                await self._fill_search_form()

                # فیلتر کردن نتایج
                await self._filter_search_form()

                # ۳. رصد و رزرو
                print("شروع رصد...")
                await self._monitor_and_book()

                # ۴. پر کردن اطلاعات مسافران
                print("در حال پر کردن اطلاعات مسافران...")
                await self._fill_passenger_details()

                # ۵. پرداخت
                print("در حال رفتن به پرداخت...")
                await self._go_to_payment()

                print("به درگاه پرداخت رسیدیم. منتظر اقدام کاربر...")

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"خطای کلی در اجرای ربات:\n{error_trace}")
            await self._update_status(ReservationStatus.FAILED, error_message=str(e))
        finally:
            if self.context is not None:
                await self.context.close()
            print(f"خطا در بستن context: {e}")

    async def _update_status(
        self, status, payment_url=None, error_message=None, captcha_token=None
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
            await attempt.asave()

            # وضعیت کلی رزرو
            # reservation = attempt.reservation
            # if status == ReservationStatus.FAILED:
            #     # فقط اگر همه attemptها شکست خورده باشند، وضعیت رزرو را FAILED کن
            #     still_active = (
            #         await ReservationAttempt.objects.filter(
            #             reservation_id=reservation.id
            #         )
            #         .exclude(status=ReservationStatus.FAILED)
            #         .aexists()
            #     )
            #     if still_active:
            #         return
            # reservation.status = status
            # if payment_url and not attempt.payment_url:
            #     attempt.payment_url = payment_url  # ✅ اصلاح شد
            # await reservation.asave()
        except Exception as e:
            print(f"خطا در آپدیت وضعیت: {e}")

    async def _monitor_and_book(self):
        await self._update_status(ReservationStatus.MONITORING)
        print("در حال رصد قطار...")

        while True:
            try:
                book_btn = self.page.locator(
                    "button.lock-btn:has-text('رزرو بلیت')"
                ).first

                if await book_btn.is_visible() and await book_btn.is_enabled():
                    print("ظرفیت پیدا شد! کلیک روی رزرو بلیت...")

                    # ✅ استخراج شماره قطار
                    try:
                        train_num_element = self.page.locator(
                            ".train-result .train-number"
                        ).first

                        if await train_num_element.count() > 0:
                            text_content = await train_num_element.inner_text()
                            match = re.search(r"\d+", text_content)
                            if match:
                                train_number = match.group()
                                print(f"شماره قطار پیدا شده: {train_number}")

                                # ✅ آپدیت شماره قطار در Attempt (نه Reservation)
                                if self.attempt_id:
                                    await ReservationAttempt.objects.filter(
                                        id=self.attempt_id
                                    ).aupdate(find_train_number=train_number)
                    except Exception as e:
                        print(f"خطا در استخراج شماره قطار: {e}")

                    await book_btn.click()
                    break
                else:
                    await self._human_delay()
            except Exception as e:
                await self._human_delay()

        await self.page.locator("button:has-text('ادامه خرید')").click()
        await self._human_delay()

    # ====================== متدهای انسانی ======================

    async def _human_delay(self, min_ms=0.1, max_ms=0.9):
        """تأخیر تصادفی انسانی"""
        delay = random.uniform(min_ms, max_ms)
        print(f"⏸️ تأخیر انسانی: {delay:.1f} میلی‌ثانیه")
        await asyncio.sleep(delay)

    async def _check_login(self):
        try:
            user_element = self.page.locator("app-user")
            text_content = await user_element.inner_text()

            if "ورود / عضویت" in text_content or "ورود" in text_content.lower():
                print("دکمه ورود/عضویت در صفحه هست. لاگین نیستیم.")
                return False
            else:
                print(f"کاربر لاگین است. نام: {text_content.strip()}")
                return True
        except Exception as e:
            print(f"خطا در بررسی لاگین: {e}")
            return False

    async def _do_login(self):
        await self._human_delay()

        print("کلیک روی دکمه ورود/عضویت...")
        await self.page.locator("#dropdownForm1").click()

        await self._human_delay()

        print("ورود نام کاربری...")
        await self.page.locator("#UserName").type(self.account.username, delay=80)
        await self._human_delay()

        print("ورود رمز عبور...")
        await self.page.locator("#Password").type(self.account.password, delay=80)
        await self._human_delay()

        print("کلیک روی دکمه ورود سبز...")
        await self.page.locator("form.login button[type='submit']").click()
        await self.page.wait_for_load_state("domcontentloaded")
        await self._human_delay()

    async def _fill_search_form(self):
        await self._human_delay()

        # انتخاب مبدا
        await self.page.locator(".ng-select-container").first.click()
        await self.page.locator(f".ng-option:has-text('{self.origin}')").first.wait_for(
            state="visible"
        )
        await self.page.locator(f".ng-option:has-text('{self.origin}')").first.click()
        await self._human_delay()

        # انتخاب مقصد
        await self.page.locator(".ng-select-container").nth(1).click()
        await self.page.locator(
            f".ng-option:has-text('{self.destination}')"
        ).first.wait_for(state="visible")
        await self.page.locator(
            f".ng-option:has-text('{self.destination}')"
        ).first.click()
        await self._human_delay()

        # حالت رفت یا رفت و برگشت
        if self.is_want_and_return:
            # ۱. انتخاب حالت رفت و برگشت
            await self.page.locator("#twoTripticket").click()
            await self._human_delay()

            # ۲. باز کردن تقویم رفت و برگشت
            date_locator = self.page.locator(".round-trip button.icon-calendar").first
            await date_locator.click()
            await self._human_delay()

            # ۳. انتخاب تاریخ رفت (از self.travel_date که به شمسی است)
            year, month, day = self.travel_date.split("-")

            # اما اگر تاریخ‌ها نزدیک باشند، معمولاً در همان ماه باز می‌شود.
            go_day_locator = self.page.locator(
                f"div.ngb-dp-day:not(.disabled):has-text('{day}')"
            ).first
            await go_day_locator.click()
            await self._human_delay()

            # ۴. انتخاب تاریخ برگشت (از self.to_date)
            return_year, return_month, return_day = self.to_date.split("-")
            return_day_locator = self.page.locator(
                f"div.ngb-dp-day:not(.disabled):has-text('{return_day}')"
            ).first
            await return_day_locator.click()
            await self._human_delay()
        else:
            # حالت تک سفر
            await self.page.locator("button.icon-calendar").click()
            await self._human_delay()

            year, month, day = self.travel_date.split("-")
            date_locator = self.page.locator(
                f"div.ngb-dp-day:not(.disabled):has-text('{day}')"
            ).first
            await date_locator.click()
            await self._human_delay()

        # تعداد مسافران
        # total_passengers = len(self.passengers)
        # await self.page.locator("#dropdownPassenger").click()
        # await self._human_delay()

        # کلیک بر روی دکمه تعداد مسافران
        # plus_adult_btn = self.page.locator("button[title='plus-adult']")
        # for _ in range(total_passengers - 1):
        #     await plus_adult_btn.click()
        #     await self._human_delay()
        # await self.page.locator("body").click()
        # await self._human_delay()

        # انتخاب نوع مسافرین
        print(f"در حال انتخاب نوع بلیط: {self.passenger_type}")
        await self.page.locator("#dropdownTikcetType").click()
        await self._human_delay()
        type_map = {
            "normal": "مسافرین عادی",
            "man": "ویژه برادران",
            "woman": "ویژه خواهران",
        }
        target_text = type_map.get(self.passenger_type, "مسافرین عادی")
        option_locator = self.page.locator(
            f"label.type-passenger:has-text('{target_text}')"
        )
        await option_locator.click()
        await self._human_delay()
        print(f"نوع بلیط {target_text} انتخاب شد ")

        # جستجو
        await self.page.locator("#btnsearchticket").click()
        await self._human_delay()

    async def _filter_search_form(self):
        # ۱. فیلتر نوع کوپه (سالن)
        if self.coupe_filter:
            print(f"در حال اعمال فیلتر نوع کوپه: {self.coupe_filter}")

            # نگاشت مقادیر مدل به id چک‌باکس‌های سایت
            coupe_map = {
                "four": "default1-1",  # کوپه ای چهار تخته
                "six": "default1-2",  # کوپه ای شش تخته
                "for_row": "default1-3",  # سالنی 4 ردیفه
            }

            target_id = coupe_map.get(self.coupe_filter)
            if target_id:
                # پیدا کردن چک‌باکس با id و کلیک روی آن
                checkbox = self.page.locator(f"#{target_id}")
                await checkbox.click()
                await self._human_delay()
                print("فیلتر نوع کوپه اعمال شد.")

        # ۲. فیلتر مرتب‌سازی (Sort)
        if self.order_by_filter:
            print(f"در حال اعمال فیلتر مرتب‌سازی: {self.order_by_filter}")

            # نگاشت مقادیر مدل به متن دکمه‌های روی صفحه
            order_by_map = {
                "clock": "ساعت حرکت",
                "cheap": "ارزانترین",
                "expensive": "گرانترین",
                "owner": "مالک",
            }

            target_text = order_by_map.get(self.order_by_filter)
            if target_text:
                # پیدا کردن دکمه داخل کلاس sort که متن مورد نظر را دارد
                # از locator(".sort button", has_text=...) استفاده می‌کنیم تا دقیقاً دکمه‌های مرتب‌سازی را هدف بگیریم
                sort_button = self.page.locator(".sort button", has_text=target_text)

                # کلیک روی دکمه
                await sort_button.click()
                await self._human_delay()
                print(f"مرتب‌سازی بر اساس {target_text} اعمال شد.")

    async def _fill_passenger_details(self):
        await self._human_delay()
        print("در حال پر کردن مشخصات مسافران...")

        await self.page.get_by_text("کد ملی/شماره پاسپورت").first.wait_for(
            state="visible", timeout=15000
        )
        print("فرم مسافران با موفقیت لود شد.")

        await self._human_delay()

        passenger_blocks = self.page.locator(".passanger-registor").filter(
            has=self.page.get_by_text("کد ملی/شماره پاسپورت")
        )

        count = await passenger_blocks.count()
        print(f"تعداد بلوک‌های مسافر پیدا شده: {count}")

        for i, passenger in enumerate(self.passengers):
            if i >= count:
                print(f"هشدار: بلوک برای مسافر {i + 1} پیدا نشد.")
                break

            block = passenger_blocks.nth(i)
            print(f"--- در حال پردازش مسافر {i + 1} ---")

            try:
                await self._human_delay()
                national_id = passenger.get("national_id")
                if national_id:
                    input_locator = block.get_by_role("textbox").first
                    await input_locator.fill(str(national_id))
                    print("کد ملی پر شد.")
            except Exception as e:
                print(f"خطا در کد ملی: {e}")

            try:
                await self._human_delay()
                birth_date = passenger.get("birth_date")
                if birth_date:
                    birth_input = block.locator("input[title='روز/ماه/سال']")
                    if await birth_input.count() == 0:
                        birth_input = block.locator("input[tabindex='12']")
                    if await birth_input.count() > 0:
                        await birth_input.fill(str(birth_date))
                        print("تاریخ تولد پر شد.")
            except Exception as e:
                print(f"خطا در تاریخ تولد: {e}")

            try:
                await self._human_delay()
                first_name = passenger.get("first_name")
                if first_name:
                    name_input = block.locator("input[name='pName']")
                    if await name_input.count() > 0:
                        await name_input.fill(str(first_name))
                        print("نام پر شد.")
            except Exception as e:
                print(f"خطا در نام: {e}")

            try:
                await self._human_delay()
                last_name = passenger.get("last_name")
                if last_name:
                    family_input = block.locator("input[name='pFamily']")
                    if await family_input.count() > 0:
                        await family_input.fill(str(last_name))
                        print("نام خانوادگی پر شد.")
            except Exception as e:
                print(f"خطا در نام خانوادگی: {e}")

        print("عملیات پر کردن مشخصات مسافران به پایان رسید.")

    async def _go_to_payment(self):
        print("در حال تیک زدن قوانین و رفتن به پرداخت...")
        await self._human_delay()

        # تیک قوانین
        try:
            await self.page.locator(
                "label.custom-control-label:has-text('صحت مشخصات')"
            ).click()
            await self._human_delay()
        except:
            await self.page.locator(
                "div.custom-control.custom-checkbox input[type='checkbox']"
            ).first.check(force=True)
            await self._human_delay()

        # شماره موبایل
        try:
            phone_input = self.page.locator("input.phonenumber")
            await phone_input.wait_for(state="visible")
            if self.travel_phone and not await phone_input.input_value():
                await phone_input.type(self.travel_phone, delay=60)
                await self._human_delay()
        except:
            pass

        await self._human_delay()

        print("کلیک روی دکمه پرداخت اولیه...")
        await self.page.locator("button.btn-success:has-text('پرداخت')").click()
        await self._human_delay()

        print("در حال منتظر ماندن برای لود شدن کپچا...")
        # کلیک بر روی دکمه من ربات نیستم
        captcha_box = self.page.locator("#input-checkbox")
        await captcha_box.wait_for(state="visible", timeout=15000)
        await self._human_delay()

        await captcha_box.click()

        print("منتظر حل شدن کپچا...")
        await self._human_delay(1, 2)
        self.page.on("request", log_request)
        self.page.on("response", log_response)

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
            await self._human_delay()

        payment_url = self.page.url
        split_payment_url = payment_url.split("registerticket")
        split_payment_url.insert(1, "payment")
        new_payment_url = "".join(split_payment_url)
        print(f"لینک درگاه نهایی: {new_payment_url}")
        await self._update_status(
            ReservationStatus.REDIRECT_GATEWAY, payment_url=new_payment_url
        )
        print("به درگاه پرداخت رسیدیم برای خارج شدن از مرورگر فقط مرورگر رو ببندید")
        # await self.page.goto(new_payment_url, wait_until="networkidle")
        await self.page.pause()
