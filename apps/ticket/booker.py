# apps/ticket/booker.py
import asyncio
import traceback
from pathlib import Path

from decouple import config
from patchright.async_api import async_playwright
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
        headless=False,  # ⚠️ حتماً باید False باشد
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

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            browser_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            if USE_DOCKER:
                browser_args.extend(
                    [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                )
            async with async_playwright() as p:
                print("در حال راه‌اندازی مرورگر با Patchright...")

                # استفاده از launch_persistent_context برای بهترین عملکرد ضد ربات
                self.context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(BASE_DIR / "raja_user_data"),
                    channel="chrome",  # استفاده از کروم واقعی
                    headless=self.headless,  # باید False باشد
                    no_viewport=True,
                    slow_mo=100,  # کمی کندتر برای شبیه شدن به انسان
                    args=browser_args,
                )

                # در persistent context، صفحه پیش‌فرض باز است
                self.page = (
                    self.context.pages[0]
                    if self.context.pages
                    else await self.context.new_page()
                )
                self.page.set_default_timeout(100000)

                await self.page.goto("https://raja.ir/", wait_until="domcontentloaded")

                # ۱. چک کردن لاگین
                is_logged_in = await self._check_login()
                if not is_logged_in:
                    print("سشن منقضی شده یا وجود ندارد. شروع لاگین...")
                    await self._do_login()
                    print("لاگین انجام شد.")

                # ۲. پر کردن فرم جستجو
                print("ورود موفق! شروع تنظیم فرم...")
                await self._fill_search_form()

                # ۳. رصد و انتخاب قطار
                print("شروع رصد...")
                await self._monitor_and_book()

                # ۴. پر کردن اطلاعات مسافران
                print("در حال پر کردن اطلاعات مسافران...")
                await self._fill_passenger_details()

                # ۵. رفتن به درگاه پرداخت و توقف
                print("در حال انتقال به درگاه پرداخت...")
                await self._go_to_payment()

                # ⛔️ اینجا ربات متوقف میشه تا کاربر پرداخت کنه
                print("به درگاه پرداخت رسیدیم. منتظر اقدام کاربر...")

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"خطای کلی در اجرای ربات:\n{error_trace}")
            await self._update_status(
                Reservation.ReservationStatus.FAILED, error_message=str(e)
            )
        finally:
            # بستن امن مرورگر در پایان کار (اگر کاربر قبلاً نبسته باشد)
            if self.context:
                await self.context.close()

    async def _check_login(self):
        # چک می‌کنیم که آیا نام کاربری در صفحه وجود دارد یا خیر
        try:
            # منتظر می‌مانیم تا المان app-user کاملاً لود شود
            await self.page.wait_for_selector("app-user", timeout=5000)

            # گرفتن متن داخل app-user
            user_element = self.page.locator("app-user")
            text_content = await user_element.inner_text()

            if "ورود / عضویت" in text_content:
                print("دکمه ورود/عضویت در صفحه هست. لاگین نیستیم.")
                return False
            else:
                print(f"کاربر لاگین است. نام: {text_content.strip()}")
                return True
        except Exception as e:
            print(f"خطا در بررسی لاگین: {e}")
            # در صورت خطا، فرض می‌کنیم لاگین نیستیم تا لاگین انجام شود
            return False

    async def _do_login(self):
        print("کلیک روی دکمه ورود/عضویت...")
        await self.page.locator("#dropdownForm1").click()
        await self.page.locator("#UserName").fill(self.account.username)
        await self.page.locator("#Password").fill(self.account.password)

        print("کلیک روی دکمه ورود سبز...")
        await self.page.locator("form.login button[type='submit']").click()
        await self.page.wait_for_load_state("domcontentloaded")

    async def _fill_search_form(self):
        print("در حال پر کردن فرم جستجو...")

        # ۱. انتخاب مبدا
        await self.page.locator(".ng-select-container").first.click()
        await self.page.locator(f".ng-option:has-text('{self.origin}')").first.wait_for(
            state="visible"
        )
        await self.page.locator(f".ng-option:has-text('{self.origin}')").first.click()

        # ۲. انتخاب مقصد
        await self.page.locator(".ng-select-container").nth(1).click()
        await self.page.locator(
            f".ng-option:has-text('{self.destination}')"
        ).first.wait_for(state="visible")
        await self.page.locator(
            f".ng-option:has-text('{self.destination}')"
        ).first.click()

        # ۳. انتخاب تاریخ
        await self.page.locator("button.icon-calendar").click()
        year, month, day = self.travel_date.split("-")
        day = int(day)

        date_locator = self.page.locator(
            f"div.ngb-dp-day:not(.disabled):has-text('{day}')"
        ).first
        await date_locator.click()

        # ۴. تعداد مسافران
        total_passengers = len(self.passengers)
        await self.page.locator("#dropdownPassenger").click()

        plus_adult_btn = self.page.locator("button[title='plus-adult']")
        for _ in range(total_passengers - 1):
            await plus_adult_btn.click()
        await self.page.locator("body").click()  # بستن منو

        # ۶. کلیک روی دکمه جستجو
        await self.page.locator("#btnsearchticket").click()

    async def _monitor_and_book(self):
        await self._update_status(Reservation.ReservationStatus.MONITORING)
        print("در حال رصد قطار...")

        while True:
            try:
                book_btn = self.page.locator(
                    "button.lock-btn:has-text('رزرو بلیت')"
                ).first

                if await book_btn.is_visible() and await book_btn.is_enabled():
                    print("ظرفیت پیدا شد! کلیک روی رزرو بلیت...")
                    await book_btn.click()
                    break
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"هنوز ظرفیتی پیدا نشد: {e}")
                await asyncio.sleep(3)

        await self.page.locator("button:has-text('ادامه خرید')").click()

    async def _fill_passenger_details(self):
        print("در حال پر کردن مشخصات مسافران...")

        await self.page.get_by_text("کد ملی/شماره پاسپورت").first.wait_for(
            state="visible", timeout=15000
        )
        print("فرم مسافران با موفقیت لود شد.")

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
                national_id = passenger.get("national_id")
                if national_id:
                    input_locator = block.get_by_role("textbox").first
                    await input_locator.fill(str(national_id))
                    print("کد ملی پر شد.")
            except Exception as e:
                print(f"خطا در کد ملی: {e}")

            try:
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
                first_name = passenger.get("first_name")
                if first_name:
                    name_input = block.locator("input[name='pName']")
                    if await name_input.count() > 0:
                        await name_input.fill(str(first_name))
                        print("نام پر شد.")
            except Exception as e:
                print(f"خطا در نام: {e}")

            try:
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

        try:
            label_locator = self.page.locator(
                "label.custom-control-label:has-text('صحت مشخصات')"
            )
            await label_locator.click()
            print("تیک تایید قوانین زده شد.")
        except Exception as e:
            print(f"خطا در کلیک روی لیبل قوانین: {e}")
            await self.page.locator(
                "div.custom-control.custom-checkbox input[type='checkbox']"
            ).first.check(force=True)

        try:
            phone_input = self.page.locator("input.phonenumber")
            await phone_input.wait_for(state="visible", timeout=15000)
            current_phone = await phone_input.input_value()
            if not current_phone and self.travel_phone:
                await phone_input.fill(self.travel_phone)
                print("شماره موبایل پر شد.")
        except Exception as e:
            print(f"خطا در پر کردن شماره موبایل: {e}")

        print("کلیک روی دکمه پرداخت اولیه...")
        payment_btn = self.page.locator("button.btn-success:has-text('پرداخت')")
        await payment_btn.click()

        # بررسی کپچا
        try:
            await self.page.wait_for_selector(
                "div[role='document'].modal-dialog", timeout=5000
            )
            print("کپچا ظاهر شد. نیاز به حل دستی توسط اپراتور.")
            await self._update_status(
                Reservation.ReservationStatus.PENDING,
                error_message="نیاز به حل دستی کپچا",
            )
            # ربات اینجا متوقف میشه تا شما کپچا رو حل کنید و روی Resume بزنید
            await self.page.pause()
        except:
            print("کپچا ظاهر نشد. ادامه...")

        print("در حال انتخاب بانک و رفتن به درگاه اصلی...")

        # تلاش برای پیدا کردن بانک (با ۳ بار تلاش مجدد)
        for attempt in range(3):
            try:
                bank_btn = self.page.locator("div.DivBank").first
                await bank_btn.wait_for(state="visible", timeout=10000)
                await bank_btn.click()
                print("بانک انتخاب شد.")
                break
            except Exception as e:
                print(f"تلاش {attempt + 1} برای پیدا کردن بانک ناموفق بود: {e}")
                await asyncio.sleep(2)

        # کلیک روی پرداخت نهایی
        try:
            final_payment_btn = self.page.locator(
                "button.btn-success:has-text('پرداخت')"
            )
            await final_payment_btn.wait_for(state="visible", timeout=10000)
            await final_payment_btn.click()
            print("کلیک روی پرداخت نهایی انجام شد.")
        except Exception as e:
            print(f"دکمه پرداخت نهایی پیدا نشد یا خطا داد: {e}")

        # صبر میکنیم تا URL تغییر کند (به درگاه بانک منتقل شود)
        # await asyncio.sleep(5)

        payment_url = self.page.url
        print(f"لینک درگاه نهایی: {payment_url}")
        await self._update_status(
            Reservation.ReservationStatus.REDIRECT_GATEWAY, payment_url=payment_url
        )

        # ⛔️ مهم‌ترین بخش: توقف نهایی!
        # اینجا ربات دوباره متوقف میشه. شما می‌تونید برید تو مرورگر، پرداخت رو انجام بدید یا هر کار دیگه‌ای بکنید.
        # مرورگر بسته نمیشه تا وقتی که شما پنجره رو ببندید یا روی Resume بزنید.
        print(
            "به درگاه بانک منتقل شدیم. ربات متوقف شد. برای بستن مرورگر یا ادامه، دستی اقدام کنید."
        )
        await self.page.pause()
