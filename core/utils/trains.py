# core/utils/trains.py
import base64
import os
import re
from datetime import date

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from apps.core.models import RajaConfig
from core.settings import RAJA_API


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
TICKET_TYPE = {"family": "Family", "male": "Male", "female": "Famale"}


def encrypt(text: str, key: str) -> str:
    """The site's CryptoJS encryptForServer: base64(salt16 + iv16 + AES-256-CBC(PBKDF2-SHA1(key, salt, 100)))."""
    salt, iv = os.urandom(16), os.urandom(16)
    k = PBKDF2HMAC(
        algorithm=hashes.SHA1(), length=32, salt=salt, iterations=100
    ).derive(key.encode())
    pad = padding.PKCS7(128).padder()
    enc = Cipher(algorithms.AES(k), modes.CBC(iv)).encryptor()
    return base64.b64encode(
        salt
        + iv
        + enc.update(pad.update(text.encode()) + pad.finalize())
        + enc.finalize()
    ).decode()


def _gregorian(jy: int, jm: int, jd: int) -> date:
    """Jalali to Gregorian: walk forward from a Gregorian guess (the Jalali year starts around 21 March)."""
    g = date(jy + 621, 3, 18)
    for step in range(0, 400):
        t = date.fromordinal(g.toordinal() + step)
        if _jalali(t.year, t.month, t.day) == (jy, jm, jd):
            return t
    raise ValueError("no such date")


def _jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Gregorian to Jalali date (the common 33-year-cycle arithmetic)."""
    g = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        + gd
        + g[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm, jd = (
        (1 + days // 31, 1 + days % 31)
        if days < 186
        else (7 + (days - 186) // 30, 1 + (days - 186) % 30)
    )
    return jy, jm, jd


def _parse_date(s: str) -> tuple[str, str, date]:
    """Jalali (1405/08/30) or Gregorian (2026-11-21) text to ('14050830', '1405/08/30', gregorian date)."""
    parts = re.split(r"[/\-.]", s.translate(DIGITS).strip())
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(
            "Date must look like 1405/08/30 (Jalali) or 2026-11-21 (Gregorian)."
        )
    y, m, d = map(int, parts)
    try:
        if y >= 1700:
            g = date(y, m, d)
            y, m, d = _jalali(y, m, d)
        elif not (1 <= m <= 12 and 1 <= d <= 31):
            raise ValueError
        else:
            g = _gregorian(y, m, d)
    except ValueError:
        raise ValueError(f"{s!r} is not a valid date.") from None
    return f"{y:04d}{m:02d}{d:02d}", f"{y:04d}/{m:02d}/{d:02d}", g


async def get_public_key():
    obj = await RajaConfig.objects.alast()
    key = obj.raja_config.get("Key")
    return key


async def create_rj_search_trains(
    origin, destination, d, passengers, ticket_type, include_sold_out=True, limit=40
):
    a, b = origin, destination
    day, shown, _ = _parse_date(d)
    q = f"{a['Code']}-{b['Code']}-{ticket_type}-1-{day}-{day}-{passengers}-false-0-0-L1"
    public_key = await get_public_key()
    encrypt_q = encrypt(q, public_key)
    res = f"{RAJA_API}/TrainListEqWithCaptcha?q={encrypt_q}"
    return res
