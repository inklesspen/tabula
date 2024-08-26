import io
import logging
import pathlib
import re
import typing

logger = logging.getLogger(__name__)

OCTET = r"[0-9A-Fa-f][0-9A-Fa-f]"
BLUETOOTH_MAC_MATCHER = re.compile(f"^{OCTET}:{OCTET}:{OCTET}:{OCTET}:{OCTET}:{OCTET}$")
DEV_INPUT_PATH = pathlib.Path("/dev/input")
DEVICES_PATH = pathlib.Path("/proc/bus/input/devices")


class Device(typing.TypedDict):
    identifier: str
    name: str
    dev_path: pathlib.Path
    bluetooth_mac: typing.Optional[str]


def parse_handlers(line: str) -> str:
    handlers = line.rstrip().removeprefix("H: Handlers=").split()
    event_handlers = [h for h in handlers if h.startswith("event")]
    if len(event_handlers) != 1:
        raise ValueError("Expected exactly one handler starting with event, got %r" % line)
    return event_handlers[0]


def parse_dev_path(line: str, check_path: bool):
    handler = parse_handlers(line)
    dev_path = DEV_INPUT_PATH / handler
    if check_path and not dev_path.is_char_device():
        raise ValueError("Expected event handler to be a char device: %r", handler)
    return dev_path


def parse_devices(raw: io.TextIOWrapper, check_paths=True) -> tuple[Device]:
    parsed = []
    current = None
    skip_rest = False
    for line in raw:
        if skip_rest is True:
            if line.rstrip() == "":
                skip_rest = False
                current = None
            continue
        try:
            if line.startswith("I:"):
                current = {"identifier": line.rstrip().removeprefix("I: ")}
            elif line.startswith("N:"):
                current["name"] = line.rstrip().removeprefix('N: Name="').removesuffix('"')
            elif line.startswith("H:"):
                current["dev_path"] = parse_dev_path(line, check_paths)
            elif line.startswith("P:"):
                current["phys"] = line.rstrip().removeprefix("P: Phys=")
            elif line.startswith("U:"):
                current["uniq"] = line.rstrip().removeprefix("U: Uniq=")
            elif line.rstrip() == "":
                # there is always a blank line at the end of the input
                # if current is None:
                #     continue
                if BLUETOOTH_MAC_MATCHER.match(current["uniq"]) and BLUETOOTH_MAC_MATCHER.match(current["phys"]):
                    current["bluetooth_mac"] = current["uniq"]
                else:
                    current["bluetooth_mac"] = None
                del current["phys"]
                del current["uniq"]
                parsed.append(current)
        except Exception:
            logger.exception("Error while parsing /proc/bus/input/devices")
            skip_rest = True
    return tuple(parsed)
