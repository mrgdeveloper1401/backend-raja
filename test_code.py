import re
from datetime import date

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


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


date_today = date.today()
day, shown, _ = _parse_date(str(date_today))
print(day)
print(shown)
print(_)
