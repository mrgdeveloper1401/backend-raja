# apps/ticket/booker.py
import asyncio
import re
from urllib import parse

import traceback
import random
from pathlib import Path


from patchright.async_api import async_playwright
from pypasser.captcha import arcaptcha

from apps.core.models import Station
from apps.ticket.models import ReservationAttempt, ReservationStatus
from apps.user.models import RajaAccount

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

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            data = {
                "account_id": self.account_id,
                "origin": self.origin,
                "destination": self.destination,
                "travel_date": self.travel_date,
                "to_date": self.to_date,
                "is_want_and_return": self.is_want_and_return,
                "travel_phone": self.travel_phone,
                "passengers": self.passengers,
                "passenger_type": self.passenger_type,
                "headless": self.headless,
                "attempt_id": self.attempt_id,
                "is_exclusive": self.is_exclusive,
                "coupe_filter": self.coupe_filter,
                "from_price": self.from_price,
                "to_price": self.to_price,
                "train_number": self.train_number,
                "departure_time_from": self.departure_time_from,
                "departure_time_to": self.departure_time_to,
                "adult": self.adult,
                "child": self.child,
            }
            print("اطلاعات کاربر", data)

            browser_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            async with async_playwright() as p:
                print("در حال راه اندازی مرورگر")

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

                # ۱. لاگین
                print("شروع لاگین...")
                await self._do_login()
                print("لاگین انجام شد.")

                # ۲. پر کردن فرم جستجو
                print("fill params ...")
                await self._fill_params()
                # print("ورود موفق! شروع تنظیم فرم...")
                # await self._fill_search_form()

                # فیلتر کردن نتایج
                await self._filter_search_form()

                # فیلتر قیمت
                await self._filter_by_price()

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

        except Exception as e:
            print(f"خطا در آپدیت وضعیت: {e}")

    async def _filter_by_time(self):
        print("در حال اعمال فیلترهای زمانی...")

        def get_time_range(from_h, to_h):
            if from_h is None and to_h is None:
                return None
            f = from_h if from_h is not None else 0
            t = to_h if to_h is not None else 24

            if f >= 18 and t <= 24:
                return "t18_24"
            if f >= 12 and t <= 18:
                return "t12_18"
            if f >= 6 and t <= 12:
                return "t6_12"
            if f >= 0 and t <= 6:
                return "t0_6"
            if f == 0 and t == 24:
                return "t0_24"

            if f >= 18:
                return "t18_24"
            if f >= 12:
                return "t12_18"
            if f >= 6:
                return "t6_12"
            return "t0_6"

        dep_range = get_time_range(self.departure_time_from, self.departure_time_to)
        if dep_range:
            try:
                btn = self.page.locator(f"div[name='GoMoveTime'] i.{dep_range}")
                await btn.click(force=True)
                await self._human_delay()
                print(f"فیلتر زمان حرکت ({dep_range}) اعمال شد.")
            except Exception as e:
                print(f"خطا در اعمال فیلتر زمان حرکت: {e}")

    async def _monitor_and_book(self):
        await self._update_status(ReservationStatus.MONITORING)

        poll_interval = 0.2
        reload_interval = 1.0
        reload_jitter = 1.0
        last_reload = asyncio.get_event_loop().time()

        salon_map = {
            "four": "4 ستاره 4 تخته",
            "four_five": "4 ستاره 5 تخته",
            "five": "5 ستاره",
            "three": "3 ستاره 6 تخته",
            "salon": "سالنی",
        }
        target_salon_text = (
            salon_map.get(self.coupe_filter, "") if self.coupe_filter else ""
        )

        while True:
            # ✅ بررسی بسته شدن مرورگر
            if not self.context or not self.page or self.page.is_closed():
                print("⚠️ مرورگر بسته شده است. خروج از حلقه رصد...")
                await self._update_status(
                    ReservationStatus.FAILED,
                    error_message="مرورگر به صورت دستی بسته شد.",
                )
                return

            try:
                # پیدا کردن همه کارت‌های قطار در صفحه
                train_cards = self.page.locator(".train-result")
                count = await train_cards.count()

                if count > 0:
                    for i in range(count):
                        card = train_cards.nth(i)

                        # ۱. استخراج شماره قطار
                        train_num_element = card.locator(".train-number")
                        if await train_num_element.count() == 0:
                            continue

                        text_content = await train_num_element.inner_text()
                        match = re.search(r"\d+", text_content)
                        current_train_num = match.group() if match else None

                        # ۲. بررسی تطابق با شماره قطار
                        if self.train_number and str(current_train_num) != str(
                            self.train_number
                        ):
                            continue

                        # ۳. استخراج نوع کوپه
                        if target_salon_text:
                            salon_element = card.locator(".train-name")
                            if await salon_element.count() > 0:
                                salon_text = await salon_element.inner_text()
                                if target_salon_text not in salon_text:
                                    continue

                        # ۴. بررسی وجود دکمه رزرو
                        book_btn = card.locator(
                            "button.lock-btn:has-text('رزرو بلیت')"
                        ).first

                        try:
                            visible = await book_btn.is_visible(timeout=1000)
                        except Exception:
                            visible = False

                        if visible and await book_btn.is_enabled():
                            print(
                                f"✅ ظرفیت برای قطار {current_train_num} پیدا شد! کلیک روی رزرو بلیت..."
                            )

                            await book_btn.click()

                            await self.page.locator(
                                "button:has-text('ادامه خرید')"
                            ).click()
                            await self._human_delay()
                            return
                        else:
                            if self.train_number and str(current_train_num) == str(
                                self.train_number
                            ):
                                print(
                                    f"⏳ قطار {current_train_num} پیدا شد اما ظرفیت ندارد. در حال انتظار..."
                                )

                # ⏰ رفرش صفحه
                now = asyncio.get_event_loop().time()
                if now - last_reload >= reload_interval + random.uniform(
                    -reload_jitter, reload_jitter
                ):
                    print("🔄 رفرش صفحه برای دیدن ظرفیت جدید...")
                    try:
                        await self.page.reload(wait_until="domcontentloaded")
                        await self.page.wait_for_timeout(500)

                        try:
                            await self._filter_search_form()
                            await self._filter_by_price()
                            await self._filter_by_time()
                        except Exception as e:
                            print(f"خطا در اعمال دوباره فیلتر بعد از reload: {e}")

                    except Exception as e:
                        print(f"خطا در reload: {e}")

                    last_reload = asyncio.get_event_loop().time()

                await asyncio.sleep(poll_interval)

            except Exception as e:
                # ✅ اگر خطای مربوط به بسته شدن مرورگر بود، از حلقه خارج شو
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

    async def _filter_by_price(self):
        if not self.from_price and not self.to_price:
            return

        print(
            f"در حال اعمال فیلتر قیمت: از {self.from_price} تا {self.to_price} (هزار تومان)"
        )

        # چون کاربر قیمت را به هزار تومان وارد کرده، نیازی به تقسیم نیست
        target_min = int(self.from_price) if self.from_price else 0
        target_max = int(self.to_price) if self.to_price else 10000

        try:
            # استفاده از جاوااسکریپت برای شبیه‌سازی حرکت دستگیره‌ها
            # این روش از لایه‌های مزاحم (interceptors) عبور می‌کند
            script = f"""
                () => {{
                    const minHandle = document.querySelector('.ng5-slider-pointer-min');
                    const maxHandle = document.querySelector('.ng5-slider-pointer-max');

                    if (minHandle && maxHandle) {{
                        // شبیه‌سازی رویداد mousedown روی دستگیره حداقل
                        if ({target_min} > 0) {{
                            const rect = minHandle.getBoundingClientRect();
                            const mousedownEvent = new MouseEvent('mousedown', {{
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            }});
                            minHandle.dispatchEvent(mousedownEvent);

                            // شبیه‌سازی حرکت ماوس به سمت راست (مقدار جدید)
                            // ما مستقیماً مقدار aria-valuenow را تغییر می‌دهیم و رویداد input را صدا می‌زنیم
                            minHandle.setAttribute('aria-valuenow', '{target_min}');
                            minHandle.setAttribute('aria-valuetext', '{target_min}');

                            // برای انگولار، رویداد input و change ضروری است
                            minHandle.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            minHandle.dispatchEvent(new Event('change', {{ bubbles: true }}));

                            // شبیه‌سازی mouseup
                            const mouseupEvent = new MouseEvent('mouseup', {{ bubbles: true }});
                            minHandle.dispatchEvent(mouseupEvent);
                        }}

                        // شبیه‌سازی رویداد mousedown روی دستگیره حداکثر
                        if ({target_max} < 10000) {{
                            const rect = maxHandle.getBoundingClientRect();
                            const mousedownEvent = new MouseEvent('mousedown', {{
                                bubbles: true,
                                cancelable: true,
                                view: window,
                                clientX: rect.left + rect.width / 2,
                                clientY: rect.top + rect.height / 2
                            }});
                            maxHandle.dispatchEvent(mousedownEvent);

                            maxHandle.setAttribute('aria-valuenow', '{target_max}');
                            maxHandle.setAttribute('aria-valuetext', '{target_max}');

                            maxHandle.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            maxHandle.dispatchEvent(new Event('change', {{ bubbles: true }}));

                            const mouseupEvent = new MouseEvent('mouseup', {{ bubbles: true }});
                            maxHandle.dispatchEvent(mouseupEvent);
                        }}
                    }}
                }}
            """
            await self.page.evaluate(script)

            # صبر می‌کنیم تا انگولار تغییرات را پردازش کند و لیست نتایج آپدیت شود
            await asyncio.sleep(1.5)

            print("فیلتر قیمت با شبیه‌سازی رویدادها اعمال شد.")
            await self._human_delay()

        except Exception as e:
            print(f"خطا در اعمال فیلتر قیمت: {e}")

        # ۳. فیلتر بازه قیمت
        await self._filter_by_price()

    # ====================== متدهای انسانی ======================

    async def _human_delay(self, min_ms=0.1, max_ms=0.2):
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
        await self.page.wait_for_load_state("networkidle")
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

        # انتخاب نوع مسافرین
        print(f"در حال انتخاب نوع بلیط: {self.passenger_type}")
        await self.page.locator("#dropdownTikcetType").click()
        await self._human_delay()
        type_map = {
            "family": "مسافرین عادی",
            "male": "ویژه برادران",
            "famale": "ویژه خواهران",
        }
        target_text = type_map.get(self.passenger_type, "مسافرین عادی")
        option_locator = self.page.locator(
            f"label.type-passenger:has-text('{target_text}')"
        )
        await option_locator.click()
        await self._human_delay()
        print(f"نوع بلیط {target_text} انتخاب شد ")

        # اگر کوپه دربت باشه
        if self.is_exclusive:
            exclusive_label = self.page.locator(
                "label.custom-control-label", has_text="کوپه دربست باشد"
            )
            await exclusive_label.click()
            await self._human_delay()
            print("کوپه دربست انتخاب شد")

        # جستجو
        await self.page.locator("#btnsearchticket").click()
        await self._human_delay()

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
        await self._human_delay()

        await self._filter_search_form()

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
                label = self.page.locator(f"label[for='{target_id}']")
                await label.wait_for(state="visible", timeout=10000)
                await label.scroll_into_view_if_needed()
                await label.click()
                await self._human_delay()
                print("فیلتر نوع کوپه اعمال شد.")

        # فیلتر قسمت
        await self._filter_by_price()

        # فیلتر زمانی
        await self._filter_by_time()

    async def _fill_passenger_details(self):
        await self._human_delay()
        print("در حال پر کردن مشخصات مسافران...")

        # منتظر می‌مانیم تا فرم مسافران لود شود
        await self.page.get_by_text("کد ملی/شماره پاسپورت").first.wait_for(
            state="visible", timeout=15000
        )
        print("فرم مسافران با موفقیت لود شد.")

        await self._human_delay()

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
                await self._human_delay()
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
                await self._human_delay()
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
                            print(f"تاریخ تولد مسافر {i + 1} (با tabindex) پر شد: {birth_date}")
            except Exception as e:
                print(f"خطا در پر کردن تاریخ تولد مسافر {i + 1}: {e}")

            # ۳. پر کردن نام (اگر فیلد قابل ویرایش وجود داشت)
            try:
                await self._human_delay()
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
                await self._human_delay()
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
            #     await self._human_delay()
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
        print(f"لینک درگاه نهایی: {payment_url}")
        await self._update_status(
            ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
        )
        print("به درگاه پرداخت رسیدیم برای خارج شدن از مرورگر فقط مرورگر رو ببندید")
        await self.page.pause()
