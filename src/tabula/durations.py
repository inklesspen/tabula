"""Functions to convert timedeltas to strings, using a string format based on Go's Duration format."""
import datetime
import decimal

from .util import maybe_int

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


def format_duration(val: datetime.timedelta) -> str:
    if val == datetime.timedelta():
        return "0"

    parts = []
    if val < datetime.timedelta():
        parts.append("-")
        val = -val

    # For durations less than 1 second, return fractions of a single unit
    if val < PARSE_UNITS["ms"]:
        # smallest timedelta resolution is 1us
        parts.append(str(val.microseconds))
        parts.append(DISPLAY_UNITS["microseconds"])
    elif val < PARSE_UNITS["s"]:
        milliseconds = val / PARSE_UNITS["ms"]
        parts.append(str(maybe_int(milliseconds)))
        parts.append(DISPLAY_UNITS["milliseconds"])
    else:
        int_hours = val // PARSE_UNITS["h"]
        val %= PARSE_UNITS["h"]
        if int_hours > 0:
            parts.append(str(int_hours))
            parts.append(DISPLAY_UNITS["hours"])
        int_minutes = val // PARSE_UNITS["m"]
        val %= PARSE_UNITS["m"]
        if int_minutes > 0:
            parts.append(str(int_minutes))
            parts.append(DISPLAY_UNITS["minutes"])
        if val > datetime.timedelta():
            parts.append(str(maybe_int(val.total_seconds())))
            parts.append(DISPLAY_UNITS["seconds"])

    return "".join(parts)


def timer_display(val: datetime.timedelta) -> str:
    # clamp to non-negative values and whole seconds
    val = datetime.timedelta(seconds=int(abs(val.total_seconds())))
    if val == datetime.timedelta():
        return "00:00"
    parts = []
    int_hours = val // PARSE_UNITS["h"]
    if int_hours > 9:
        raise ValueError("timer display requires single-digit hours")
    val %= PARSE_UNITS["h"]
    if int_hours > 0:
        parts.append(str(int_hours))
    int_minutes = val // PARSE_UNITS["m"]
    val %= PARSE_UNITS["m"]
    parts.append("{:02}".format(int_minutes))
    parts.append("{:02}".format(maybe_int(val.total_seconds())))
    return ":".join(parts)


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
