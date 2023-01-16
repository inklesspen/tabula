import inspect
import typing

import msgspec
import trio


async def checkpoint():
    await trio.sleep(0)


def evolve(obj: msgspec.Struct, **changes):
    cls = obj.__class__
    for field_name in cls.__struct_fields__:
        if field_name not in changes:
            changes[field_name] = getattr(obj, field_name)
    return cls(**changes)


def invoke(c: typing.Callable, **provided_kwargs):
    sig = inspect.signature(c)
    used_kwargs = {k: v for k, v in provided_kwargs.items() if k in sig.parameters}
    return c(**used_kwargs)
