import httpx
import re

url = "https://www.raja.ir/search?adult=1&child=0&infant=0&movetype=1&ischarter=false&fs=191&ts=55&godate=14050904&tickettype=Family&returndate=&numberpassenger=1&mode=Train&desctravel=%D9%82%D8%B7%D8%A7%D8%B1%20%D9%85%D8%B4%D9%87%D8%AF%20%D8%A8%D9%87%20%D8%AA%D8%A8%D8%B1%DB%8C%D8%B2"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

with httpx.Client() as client:
    response = client.get(url, headers=headers)
    html = response.text

    # جستجو برای پیدا کردن q در کدهای صفحه
    # معمولاً q در یک متغیر جاوا اسکریپت یا در یک لینک مخفی است
    match = re.search(r'TrainListEqWithCaptcha\?q=([^"\']+)', html)
    if match:
        print("پیدا شد!", match.group(1))
    else:
        print("در HTML پیدا نشد. شاید جاوا اسکریپت آن را می‌سازد.")
        # در این حالت باید فایل‌های JS را چک کنیم که پیچیده‌تر است.