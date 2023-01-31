"""Functions to convert timedeltas to strings, using a string format based on Go's Duration format."""
import datetime
import decimal

DISPLAY_UNITS = {
    "seconds": "s",
    "milliseconds": "ms",
    "microseconds": "us",
    "minutes": "m",
    "hours": "h",
}

PARSE_UNITS = {
    "s": datetime.timedelta(seconds=1),
    "ms": datetime.timedelta(milliseconds=1),
    "us": datetime.timedelta(microseconds=1),
    "m": datetime.timedelta(minutes=1),
    "h": datetime.timedelta(hours=1),
}


def _maybe_int(val: float):
    return int(val) if val.is_integer() else val


def format_duration(val: datetime.timedelta) -> str:
    if val == datetime.timedelta():
        return "0"

    parts = []
    if val < datetime.timedelta():
        parts.append("-")
        val = -val

    # For durations less than 1 second, return fractions of a single unit
    if val < datetime.timedelta(milliseconds=1):
        # smallest timedelta resolution is 1us
        parts.append(str(val.microseconds))
        parts.append(DISPLAY_UNITS["microseconds"])
    elif val < datetime.timedelta(seconds=1):
        milliseconds = val / datetime.timedelta(milliseconds=1)
        parts.append(str(_maybe_int(milliseconds)))
        parts.append(DISPLAY_UNITS["milliseconds"])
    else:
        int_hours = val // datetime.timedelta(hours=1)
        val %= datetime.timedelta(hours=1)
        if int_hours > 0:
            parts.append(str(int_hours))
            parts.append(DISPLAY_UNITS["hours"])
        int_minutes = val // datetime.timedelta(minutes=1)
        val %= datetime.timedelta(minutes=1)
        if int_minutes > 0:
            parts.append(str(int_minutes))
            parts.append(DISPLAY_UNITS["minutes"])
        if val > datetime.timedelta():
            parts.append(str(_maybe_int(val.total_seconds())))
            parts.append(DISPLAY_UNITS["seconds"])

    return "".join(parts)


def parse_duration(val: str) -> datetime.timedelta:
    sign = 1
    if val.startswith("-"):
        sign = -1
        val = val[1:]
    elif val.startswith("+"):
        val = val[1:]
    if len(val) == 0:
        raise ValueError("Empty duration string")
    if val == "0":
        return datetime.timedelta()

    accum = datetime.timedelta()
    while len(val) > 0:
        # try to get a number part
        numberpart = ""
        while len(val) > 0 and (val[0].isdigit() or val[0] == "."):
            numberpart += val[0]
            val = val[1:]
        if len(numberpart) == 0:
            raise ValueError("Invalid duration string; expected number")
        if not numberpart[0].isdigit():
            raise ValueError("Invalid duration string; expected leading digit")
        number = decimal.Decimal(numberpart)
        # try to get a unit
        if len(val) == 0:
            raise ValueError("Invalid duration string; expected unit")
        unit = None
        for unitstr in PARSE_UNITS.keys():
            if val.startswith(unitstr):
                unit = PARSE_UNITS[unitstr]
                val = val[len(unitstr) :]
                break
        if unit is None:
            raise ValueError("Invalid duration string; expected unit")

        intpart = number // 1
        fracpart = number % 1
        if intpart != 0:
            accum += sign * int(intpart) * unit
        if fracpart != 0:
            num, denom = fracpart.as_integer_ratio()
            accum += sign * num * unit / denom

    return accum
