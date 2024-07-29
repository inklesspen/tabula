import dataclasses
import enum
import logging
import subprocess

from .hwtypes import BluetoothVariant, MultitouchVariant

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class KoboModelMixin:
    bluetooth_variant: BluetoothVariant
    multitouch_variant: MultitouchVariant


class KoboModel(KoboModelMixin, enum.Enum):
    CLARA_HD = BluetoothVariant.NONE, MultitouchVariant.SNOW_PROTOCOL
    CLARA_2E = BluetoothVariant.CLARA2E, MultitouchVariant.TYPE_B


CODENAMES = {"nova": KoboModel.CLARA_HD, "goldfinch": KoboModel.CLARA_2E}


def detect_model():
    proc = subprocess.run("/bin/kobo_config.sh", shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    model = proc.stdout.strip()
    logger.debug("Detected Kobo model %r", model)
    return CODENAMES[model]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    model = detect_model()
    logging.debug("Model details: %r", model)
