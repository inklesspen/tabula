import enum
import collections.abc
import datetime
import inspect
import typing
from os.path import commonprefix

from dateutil.tz import tzlocal
import outcome
import trio

if typing.TYPE_CHECKING:
    from _cffi_backend import FFI as FFIType
    from .app import Tabula


TABULA: trio.lowlevel.RunVar["Tabula"] = trio.lowlevel.RunVar("tabula_app_instance")

AwaitableCallback = collections.abc.Callable[[], collections.abc.Awaitable[None]]


def check_c_enum(ffi: "FFIType", enum_t: str, allow_skipped_c_values=False, **extras: int):
    ctype = ffi.typeof(enum_t)
    prefix = commonprefix(tuple(ctype.relements.keys()))
    values: dict[str, int] = {k.removeprefix(prefix): v for v, k in sorted(ctype.elements.items())}
    values.update(extras)

    def checker[E: typing.Type[enum.IntEnum]](cls: E):
        for name, value in cls.__members__.items():
            if name not in values:
                raise KeyError(name)
            if values[name] != value:
                raise ValueError(name)
        if not allow_skipped_c_values:
            for name in values:
                if name not in cls.__members__:
                    raise KeyError(name)
        return cls

    return checker


async def invoke_if_present(obj: typing.Any, method_name: str, **provided_kwargs):
    if not hasattr(obj, method_name):
        return
    c = getattr(obj, method_name)
    if not callable(c):
        return
    result = invoke(c, **provided_kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


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


def removing(tup: tuple[V], item: V):
    temp = list(tup)
    temp.remove(item)
    return tuple(temp)


def replacing_last(tup: tuple[V], item: V):
    temp = list(tup)
    temp[-1] = item
    return tuple(temp)


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


class Future[V]:
    _outcome: typing.Optional[outcome.Outcome]

    def __init__(self):
        self._event = trio.Event()
        self._outcome = None

    def finalize(self, result: V | outcome.Outcome[V]):
        if self._outcome is not None:
            raise Exception("already finalized")
        if isinstance(result, outcome.Outcome):
            self._outcome = result
        else:
            self._outcome = outcome.Value(result)
        self._event.set()

    async def wait(self) -> V:
        await self._event.wait()
        return self._outcome.unwrap()

    @property
    def is_final(self):
        return self._event.is_set()
