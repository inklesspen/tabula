import enum
import collections.abc
import datetime
import inspect
import typing
from os.path import commonprefix

from dateutil.tz import tzlocal
import trio
import trio_util
import tricycle

if typing.TYPE_CHECKING:
    from _cffi_backend import FFI as FFIType


# TODO: consider defining the enum entries in Python and _verifying_ against ffi.
# possibly a class decorator?
def make_c_enum(
    ffi: "FFIType", enum_t: str, python_name: str, **extras: int
) -> typing.Type[enum.IntEnum]:
    ctype = ffi.typeof(enum_t)
    prefix = commonprefix(tuple(ctype.relements.keys()))
    values: dict[str, int] = {
        k.removeprefix(prefix): v for v, k in sorted(ctype.elements.items())
    }
    values.update(extras)
    return enum.IntEnum(python_name, values)


async def checkpoint():
    await trio.sleep(0)


def invoke(c: typing.Callable, **provided_kwargs):
    sig = inspect.signature(c)
    used_kwargs = {k: v for k, v in provided_kwargs.items() if k in sig.parameters}
    return c(**used_kwargs)


V = typing.TypeVar("V")


def set_into(list: list[typing.Optional[V]], index: int, item: V):
    while index >= len(list):
        list.append(None)
    list[index] = item


def maybe_int(val: float):
    return int(val) if val.is_integer() else val


def now():
    return datetime.datetime.now(tzlocal())


def humanized_delta(delta: datetime.timedelta, allow_future: bool = False):
    seconds = int(delta.total_seconds())
    if seconds == 0:
        return "now"
    relative_template = "in {}" if allow_future and seconds > 0 else "{} ago"

    seconds = abs(seconds)

    if seconds < 60:
        return relative_template.format("less than a minute")
    minutes = seconds // 60
    if minutes <= 4:
        return relative_template.format("a few minutes")
    if minutes <= 7:
        return relative_template.format("about five minutes")
    if minutes <= 12:
        return relative_template.format("about ten minutes")
    if minutes <= 18:
        return relative_template.format("about fifteen minutes")
    if minutes <= 22:
        return relative_template.format("about twenty minutes")
    if minutes <= 28:
        return relative_template.format("about twenty-five minutes")
    if minutes <= 38:
        return relative_template.format("about half an hour")
    if minutes <= 48:
        return relative_template.format("about forty-five minutes")
    hours = minutes // 60
    hour_change = minutes % 60
    if hours == 0:
        return relative_template.format("almost an hour")
    if hours == 1 and hour_change <= 15:
        return relative_template.format("about an hour")
    if hours == 1 and hour_change <= 45:
        return relative_template.format("about ninety minutes")
    if hours == 1 or (hours == 2 and hour_change <= 30):
        return relative_template.format("about two hours")
    if hours == 2 or (hours == 3 and hour_change <= 30):
        return relative_template.format("about three hours")
    if hours == 3 or (hours == 4 and hour_change <= 30):
        return relative_template.format("about four hours")
    if hours == 4 or (hours == 5 and hour_change <= 30):
        return relative_template.format("about five hours")
    if hours == 5 or (hours == 6 and hour_change <= 30):
        return relative_template.format("about six hours")
    days = hours // 24
    if days == 0:
        return relative_template.format("several hours")
    if days == 1:
        return relative_template.format("a day")
    if days == 2:
        return relative_template.format("two days")
    if days < 5:
        return relative_template.format("a few days")
    if days < 9:
        return relative_template.format("several days")
    return relative_template.format("a good long while")


class TickCaller(tricycle.BackgroundObject, daemon=True):
    def __init__(
        self,
        period_length: int,
        callback: collections.abc.Callable[[], collections.abc.Awaitable[None]],
    ):
        self.length = period_length
        self.callback = callback

    async def __open__(self) -> None:
        self.nursery.start_soon(self.ticker, trio_util.periodic(self.length))

    async def ticker(self, trigger):
        async for _ in trigger:
            await self.callback()
