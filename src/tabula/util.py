from __future__ import annotations

import collections.abc
import datetime
import enum
import inspect
import math
import typing

import outcome
import trio
from dateutil.tz import tzlocal

if typing.TYPE_CHECKING:
    from _cffi_backend import FFI as FFIType

    from .app import Tabula


TABULA: trio.lowlevel.RunVar["Tabula"] = trio.lowlevel.RunVar("tabula_app_instance")

AwaitableCallback = collections.abc.Callable[[], collections.abc.Awaitable[None]]


def _nameprefix(*names: str):
    "Given multiple identifiers (such as those used for enums), return the longest common prefix, or the empty string if no such prefix is found."
    if not names:
        return ""
    names = sorted(set(names))
    if len(names) == 1:
        return names[0]
    first = names[0]
    last = names[-1]
    for i, ch in enumerate(first):
        if ch != last[i]:  # first differing character
            return first[:i]  # so return everything up to that point
    # if we fall off the end of the for loop, then the first string is a substring of the last string, which seems weird but is possible.
    return first


E = typing.TypeVar("E", bound=type[enum.IntEnum], covariant=True)


def check_c_enum(ffi: FFIType, enum_t: str, strip_prefix: str | None = None, allow_omitting_c_members: bool = False, **extras: int):
    """Checks an IntEnum for consistency with a C enum.

    For example, given this C enum type:
        typedef enum {
            STOP,
            CAUTION,
            GO
        } traffic_light_states_t ;

    You can define this IntEnum:
        @check_c_enum(ffi, 'traffic_light_states_t')
        class TrafficLightState(enum.IntEnum):
            STOP = 0
            CAUTION = 1
            GO = 2

    Raises KeyError if either enum has a name not found in the other, or ValueError if a name has different values in the two enums.

    Many C enums have a common prefix, such as SOMELIBRARY_VALUE_A and SOMELIBRARY_VALUE_B. By default, check_c_enum detects and strips
    this common prefix, so it will look for members named A and B on the Python-side enum. To turn off this detection, set strip_prefix
    to a string value, or (to not strip anything) the empty string.

    Set allow_omitting_c_members=True to allow the Python-side enum to omit one or more members from the C-side enum.

    Any additional values defined in the Python-side enum may be specified as extra keyword arguments; this can be handy for defining aliases.
    """
    ctype = ffi.typeof(enum_t)
    if strip_prefix is None:
        strip_prefix = _nameprefix(*ctype.relements.keys())
    values: dict[str, int] = {k.removeprefix(strip_prefix): v for v, k in sorted(ctype.elements.items())}
    values.update(extras)

    def checker(cls: E):
        for name, value in cls.__members__.items():
            if name not in values:
                raise KeyError(name)
            if values.pop(name) != value:
                raise ValueError(name)
        if not allow_omitting_c_members:
            for name in values:
                if name not in cls.__members__:
                    raise KeyError(name)
        return cls

    return checker


async def invoke_if_present(obj: typing.Any, method_name: str, **provided_kwargs):
    if not hasattr(obj, method_name):
        return None
    c = getattr(obj, method_name)
    if not callable(c):
        return None
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


V = typing.TypeVar("V")


class Future(typing.Generic[V]):
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


GOLDEN_RATIO = (math.sqrt(5) + 1) / 2


def golden_section_search(eval_func: collections.abc.Callable[[float], float], lower_bound: float, upper_bound: float, tolerance=1e-5):
    while abs(upper_bound - lower_bound) > tolerance:
        candidate_from_upper = upper_bound - (upper_bound - lower_bound) / GOLDEN_RATIO
        candidate_from_lower = lower_bound + (upper_bound - lower_bound) / GOLDEN_RATIO
        if eval_func(candidate_from_upper) < eval_func(candidate_from_lower):  # f(c) > f(d) to find the maximum
            upper_bound = candidate_from_lower
        else:
            lower_bound = candidate_from_upper

    return (upper_bound + lower_bound) / 2
