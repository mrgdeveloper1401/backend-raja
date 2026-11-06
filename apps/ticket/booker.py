# apps/ticket/booker.py
import asyncio
import traceback
import random
from pathlib import Path

from decouple import config
from humanization import Humanization, HumanizationConfig
from patchright.async_api import async_playwright
from pypasser.antibot import arvancloud
from pypasser.captcha import arcaptcha

from apps.ticket.models import Reservation
from apps.user.models import RajaAccount

BASE_DIR = Path(__file__).resolve().parent.parent.parent

USE_DOCKER = config("USE_DOCKER", cast=bool, default=False)


class RajaBooker:
    def __init__(
        self,
        account_id,
        origin,
        destination,
        travel_date,
        passengers,
        headless=False,
        reservation_id=None,
        travel_phone=None,
    ):
        self.account_id = account_id
        self.origin = origin
        self.destination = destination
        self.travel_date = travel_date
        self.passengers = passengers
        self.headless = headless
        self.reservation_id = reservation_id
        self.travel_phone = travel_phone
        self.human = None
        self.page = None
        self.context = None

    async def _update_status(self, status, payment_url=None, error_message=None):
        if self.reservation_id:
            try:
                reservation = await Reservation.objects.aget(id=self.reservation_id)
                reservation.status = status
                if payment_url:
                    reservation.payment_url = payment_url
                if error_message:
                    reservation.error_message = error_message
                await reservation.asave()
                print(f"وضعیت رزرو به {status} تغییر یافت.")
            except Exception as e:
                print(f"خطا در آپدیت وضعیت دیتابیس: {e}")

    async def _handle_ar_capcha(self):
        try:
            result = arvancloud.solve("https://raja.ir/")
            if result.cookies and "__arcsjs" in result.cookies:
                await self.context.add_cookies([
                    {"name": "__arcsjs", "value": result.cookies["__arcsjs"], "domain": ".raja.ir", "path": "/"},
                    {"name": "__arcsjsc", "value": result.cookies["__arcsjsc"], "domain": ".raja.ir", "path": "/"},
                ])
                print("کوکی‌ها تزریق شدند.")
            else:
                print("کوکی دریافت نشد، ممکن است چالش فعال نباشد.")
        except Exception as e:
            print(f"خطا در حل چالش آروان‌کلاد: {e}. ادامه بدون کوکی...")

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)
            print("اطلاعات کاربر")
            data = {
                "origin": self.origin,
                "destination": self.destination,
                "travel_date": self.travel_date,
                "travel_phone": self.travel_phone,
                "passengers": self.passengers,
            }
            print(data)

            # ✅ تنظیمات Humanization
            config = HumanizationConfig(
                characters_per_minute=400,
                backspace_cpm=800,
                timeout=10000,
                humanize=True,
                stealth_mode=True,
            )

            async with async_playwright() as p:
                print("در حال راه‌اندازی مرورگر با Patchright (Humanized)...")

                # ✅ استفاده از Humanization برای راه‌اندازی مرورگر مخفی
                self.human = await Humanization.undetected_launch(
                    user_data_dir=str(BASE_DIR / "raja_user_data"),
                    config=config,
                    headless=self.headless,
                )
                self.page = self.human.page
                self.page.set_default_timeout(10000)

                await self._handle_ar_capcha()
                await self.page.goto("https://raja.ir/", wait_until="networkidle")

                # ✅ پاک کردن state سشن قبلی (بدون لمس کوکی‌های لاگین)
                await self.page.evaluate("""() => {
                    localStorage.clear();
                    sessionStorage.clear();
                }""")

                # ریلود تا سایت با storage پاک شروع کنه
                await self.page.goto("https://raja.ir/", wait_until="networkidle")

                # ۱. چک لاگین
                is_logged_in = await self._check_login()
                if not is_logged_in:
                    print("شروع لاگین...")
                    await self._do_login()
                    print("لاگین انجام شد.")

                # ۲. پر کردن فرم جستجو
                print("ورود موفق! شروع تنظیم فرم...")
                await self._fill_search_form()

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
            await self._update_status(
                Reservation.ReservationStatus.FAILED, error_message=str(e)
            )
        finally:
            if self.human:
                await self.human.page.context.close()

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
        # ✅ استفاده از click_at برای کلیک انسانی
        await self.human.click_at(self.page.locator("#dropdownForm1"))

        await self._human_delay()

        print("ورود نام کاربری...")
        # ✅ استفاده از type_at برای تایپ انسانی
        await self.human.type_at(self.page.locator("#UserName"), self.account.username)
        await self._human_delay()

        print("ورود رمز عبور...")
        await self.human.type_at(self.page.locator("#Password"), self.account.password)
        await self._human_delay()

        print("کلیک روی دکمه ورود سبز...")
        await self.human.click_at(self.page.locator("form.login button[type='submit']"))
        await self.page.wait_for_load_state("domcontentloaded")
        await self._human_delay()

    async def _fill_search_form(self):
        await self._human_delay()

        # انتخاب مبدا
        await self.human.click_at(self.page.locator(".ng-select-container").first)
        await self.page.locator(f".ng-option:has-text('{self.origin}')").first.wait_for(state="visible")
        await self.human.click_at(self.page.locator(f".ng-option:has-text('{self.origin}')").first)
        await self._human_delay()

        # انتخاب مقصد
        await self.human.click_at(self.page.locator(".ng-select-container").nth(1))
        await self.page.locator(f".ng-option:has-text('{self.destination}')").first.wait_for(state="visible")
        await self.human.click_at(self.page.locator(f".ng-option:has-text('{self.destination}')").first)
        await self._human_delay()

        # انتخاب تاریخ
        await self.human.click_at(self.page.locator("button.icon-calendar"))
        await self._human_delay()

        year, month, day = self.travel_date.split("-")
        date_locator = self.page.locator(f"div.ngb-dp-day:not(.disabled):has-text('{day}')").first
        await self.human.click_at(date_locator)
        await self._human_delay()

        # تعداد مسافران
        total_passengers = len(self.passengers)
        await self.human.click_at(self.page.locator("#dropdownPassenger"))
        await self._human_delay()

        plus_adult_btn = self.page.locator("button[title='plus-adult']")
        for _ in range(total_passengers - 1):
            await self.human.click_at(plus_adult_btn)
            await self._human_delay()
        await self.human.click_at(self.page.locator("body"))
        await self._human_delay()

        # جستجو
        await self.human.click_at(self.page.locator("#btnsearchticket"))
        await self._human_delay()

    async def _monitor_and_book(self):
        await self._update_status(Reservation.ReservationStatus.MONITORING)
        print("در حال رصد قطار...")

        while True:
            try:
                book_btn = self.page.locator("button.lock-btn:has-text('رزرو بلیت')").first

                if await book_btn.is_visible() and await book_btn.is_enabled():
                    print("ظرفیت پیدا شد! کلیک روی رزرو بلیت...")
                    await self.human.click_at(book_btn)
                    break
                else:
                    await self._human_delay()
            except Exception as e:
                await self._human_delay()

        await self.human.click_at(self.page.locator("button:has-text('ادامه خرید')"))
        await self._human_delay()

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
                    await self.human.type_at(input_locator, str(national_id))
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
                        await self.human.type_at(birth_input, str(birth_date))
                        print("تاریخ تولد پر شد.")
            except Exception as e:
                print(f"خطا در تاریخ تولد: {e}")

            try:
                await self._human_delay()
                first_name = passenger.get("first_name")
                if first_name:
                    name_input = block.locator("input[name='pName']")
                    if await name_input.count() > 0:
                        await self.human.type_at(name_input, str(first_name))
                        print("نام پر شد.")
            except Exception as e:
                print(f"خطا در نام: {e}")

            try:
                await self._human_delay()
                last_name = passenger.get("last_name")
                if last_name:
                    family_input = block.locator("input[name='pFamily']")
                    if await family_input.count() > 0:
                        await self.human.type_at(family_input, str(last_name))
                        print("نام خانوادگی پر شد.")
            except Exception as e:
                print(f"خطا در نام خانوادگی: {e}")

        print("عملیات پر کردن مشخصات مسافران به پایان رسید.")

    async def _go_to_payment(self):
        print("در حال تیک زدن قوانین و رفتن به پرداخت...")
        await self._human_delay()

        # تیک قوانین
        try:
            await self.human.click_at(
                self.page.locator("label.custom-control-label:has-text('صحت مشخصات')")
            )
            await self._human_delay()
        except:
            checkbox = self.page.locator("div.custom-control.custom-checkbox input[type='checkbox']").first
            await self.human.click_at(checkbox)
            await self._human_delay()

        # شماره موبایل
        try:
            phone_input = self.page.locator("input.phonenumber")
            await phone_input.wait_for(state="visible")
            if self.travel_phone and not await phone_input.input_value():
                await self.human.type_at(phone_input, self.travel_phone)
                await self._human_delay()
        except:
            pass

        await self._human_delay()

        print("کلیک روی دکمه پرداخت اولیه...")
        await self.human.click_at(self.page.locator("button.btn-success:has-text('پرداخت')"))
        await self._human_delay()

        # ✅ تلاش برای حل خودکار کپچا با PyPasser
        print("در حال تلاش برای حل خودکار کپچا...")
        try:
            result = await arcaptcha.asolve(
                page=self.page,
                site_key="t8xr2hpxue",
                domain="raja.ir"
            )

            if result.is_solved:
                print("کپچا با موفقیت حل شد.")
            else:
                print("حل خودکار ناموفق بود. نیاز به حل دستی.")
                await self._update_status(
                    Reservation.ReservationStatus.PENDING,
                    error_message="نیاز به حل دستی کپچا",
                )
                if not self.headless:
                    await self.page.pause()
        except Exception as e:
            print(f"خطا در حل کپچا: {e}")
            await self._update_status(
                Reservation.ReservationStatus.PENDING,
                error_message=f"خطای کپچا: {e}",
            )
            if not self.headless:
                await self.page.pause()

        payment_url = self.page.url
        print(f"لینک درگاه نهایی: {payment_url}")
        await self._update_status(
            Reservation.ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
        )
        print("به درگاه پرداخت رسیدیم. برای خارج شدن از مرورگر، فقط مرورگر را ببندید.")
        await self.page.pause()