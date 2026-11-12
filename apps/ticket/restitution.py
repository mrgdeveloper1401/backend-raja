# apps/ticket/restitution.py
import asyncio

import traceback
import random
from pathlib import Path

import ddddocr
from patchright.async_api import async_playwright

from apps.ticket.models import Restitution, RestitutionEnum
from apps.user.models import RajaAccount
from core.settings import IS_WINDOWS

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class RestitutionTicket:
    def __init__(
        self, serial, phone, train_number, hall_number, account_id, restitution_id
    ):
        self.serial = serial
        self.phone = phone
        self.train_number = train_number
        self.hall_number = hall_number
        self.account_id = account_id
        self.restitution_id = restitution_id
        self.account = None
        self.context = None
        self.headless = False
        self.page = None

    async def start(self):
        try:
            self.account = await RajaAccount.objects.aget(id=self.account_id)

            data = {
                "serial": self.serial,
                "phone": self.phone,
                "train_number": self.train_number,
                "hall_number": self.hall_number,
            }
            print("اطلاعات استرداد", data)

            browser_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            async with async_playwright() as p:
                print("در حال راه‌اندازی مرورگر با Patchright...")

                self.context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(
                        BASE_DIR / "raja_user_data" / f"restitution_ticket_{self.restitution_id}"
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
                await self.page.goto("https://raja.ir/", wait_until="domcontentloaded")

                # ✅ پاک کردن state سشن قبلی (بدون لمس کوکی‌های لاگین)
                await self.page.evaluate("""() => {
                    localStorage.clear();
                    sessionStorage.clear();
                }""")

                # ریلود تا سایت با storage پاک شروع کنه
                await self.page.goto("https://raja.ir/", wait_until="domcontentloaded")

                #  لاگین
                print("شروع لاگین...")
                await self._do_login()
                print("لاگین انجام شد.")

                # ۲. پر کردن فرم جستجو
                print("ورود موفق! شروع تنظیم فرم...")
                await self._fill_search_form()

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"خطای کلی در اجرای ربات:\n{error_trace}")
            await self._update_status(RestitutionEnum.FAILED, error_message=str(e))
        finally:
            if self.context is not None:
                await self.context.close()
            print(f"خطا در بستن context: {e}")

    async def _update_status(self, status, error_message=None):
        try:
            return await Restitution.objects.filter(id=self.restitution_id).aupdate(
                status=status,
                error_message=error_message if error_message else None
            )
        except Exception as e:
            print(f"خطا در آپدیت وضعیت: {e}")

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

    async def _human_delay(self, min_ms=0.1, max_ms=0.9):
        """تأخیر تصادفی انسانی"""
        delay = random.uniform(min_ms, max_ms)
        print(f"⏸️ تأخیر انسانی: {delay:.1f} میلی‌ثانیه")
        await asyncio.sleep(delay)

    async def _fill_search_form(self):
        print('در حال رفتن به تب استرداد...')
        # کلیک روی تب استرداد
        await self.page.locator("#t5").click()
        await self._human_delay()

        print('منتظر لود شدن فرم استرداد...')
        # صبر می‌کنیم تا فرم (که با Vue.js رندر می‌شود) ظاهر شود
        await self.page.locator("app-searchrefund").wait_for(state="visible", timeout=10000)
        await self._human_delay()

        print("در حال پر کردن اطلاعات استرداد...")

        # چون تمام inputها name یکسانی دارند، از ترتیب (nth) استفاده می‌کنیم
        # ۱. سریال بلیت
        serial_input = self.page.locator("app-searchrefund input[type='text']").nth(0)
        await serial_input.fill(str(self.serial))
        await self._human_delay()

        # ۲. شماره موبایل
        phone_input = self.page.locator("app-searchrefund input[type='text']").nth(1)
        await phone_input.fill(str(self.phone))
        await self._human_delay()

        # ۳. شماره قطار
        train_input = self.page.locator("app-searchrefund input[type='text']").nth(2)
        await train_input.fill(str(self.train_number))
        await self._human_delay()

        # ۴. شماره سالن
        hall_input = self.page.locator("app-searchrefund input[type='text']").nth(3)
        await hall_input.fill(str(self.hall_number))
        await self._human_delay()

        # ۵. تیک زدن چک‌باکس خسارت (در صورت نیاز)
        # نام این چک‌باکس chkDamge است. اگر می‌خواهید تیک بزنید، این خط را از کامنت خارج کنید
        # await self.page.locator("input[name='chkDamge']").check(force=True)
        # await self._human_delay()

        print("اطلاعات فرم پر شد. در حال کلیک روی دکمه استرداد...")

        # ۶. کلیک روی دکمه استرداد
        await self.page.locator("#btnsearchticket").click()
        await self._human_delay()

        print("درخواست استرداد ارسال شد. منتظر بارگذاری مرحله بعد ...")

        # ۷. تیک زدن قوانین و مقررات
        print("تیک زدن قوانین و مقررات...")
        try:
            # روش اول: استفاده از force=True روی خود input (مطمئن‌ترین روش)
            await self.page.locator("#acceptRules").check(force=True)
            print("چک‌باکس قوانین تیک زده شد.")
        except Exception as e:
            print(f"خطا در تیک زدن چک‌باکس با روش اول: {e}")
            # روش دوم (پشتیبان): کلیک روی لیبل متنی
            try:
                await self.page.locator("label[for='acceptRules']").click()
                print("چک‌باکس قوانین با کلیک روی لیبل تیک زده شد.")
            except Exception as e2:
                print(f"خطا در تیک زدن چک‌باکس با روش دوم: {e2}")
        await self._human_delay()

        # ۸. حل کپچا
        print("در حال استخراج تصویر کپچا...")
        captcha_img_locator = self.page.locator("#imgcpatcha")
        await captcha_img_locator.wait_for(state="visible")
        img_bytes = await captcha_img_locator.screenshot()

        print("در حال حل کپچا با OCR...")
        ocr = ddddocr.DdddOcr(show_ad=False)
        captcha_text = ocr.classification(img_bytes)
        print(f"متن استخراج شده از کپچا: {captcha_text}")

        if not captcha_text:
            print("خطا: کپچا خوانده نشد!")
            await self._update_status(RestitutionEnum.FAILED)
            return

        # وارد کردن متن کپچا
        await self.page.locator("input[name='CaptchaAnswer']").fill(captcha_text)
        await self._human_delay()

        # ۹. کلیک روی دکمه درخواست کد استرداد
        print("کلیک روی دکمه درخواست کد استرداد...")
        await self.page.locator("#btnRequestRefundCode").click()
        await self._human_delay()

        await self.page.pause()
