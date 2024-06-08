import contextlib
import importlib.resources
import pathlib
import tempfile

from ._cairopango import lib as clib, ffi  # type: ignore
from .fonts import FILES


ROOT_CONFIG = """\
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<!-- /etc/fonts/fonts.conf file to configure system font access -->
<fontconfig>
    <its:rules xmlns:its="http://www.w3.org/2005/11/its" version="1.0">
        <its:translateRule translate="no" selector="/fontconfig/*[not(self::description)]"/>
    </its:rules>
<reset-dirs />
<include>[APPFONTS_PATH]</include>
<dir>[APPFONTS_PATH]</dir>
<include ignore_missing="yes">[USERFONTS_PATH]</include>
<dir>[USERFONTS_PATH]</dir>
<cachedir>[CACHE_PATH]</cachedir>
</fontconfig>
"""

NON_DRAFTING_FONTS = {
    # UI fonts
    "B612 Mod",
    "B612 Mod Mono",
    "Crimson Pro",
    "Ibarra Real Nova Straylight",
    # Generic families
    "Monospace",
    "Sans",
    "Serif",
    "System-ui",
}


def setup_fontconfig(user_font_path: pathlib.Path):
    # Returns ExitStack which should be exited when the app is exiting. One way is with a finalizer.
    # self._finalizer = weakref.finalize(self, fontconfig.close())
    resource_manager = contextlib.ExitStack()
    if not FILES.is_dir():
        raise Exception("unable to load app fonts")
    appfonts_path = resource_manager.enter_context(importlib.resources.as_file(FILES))
    cache_path = resource_manager.enter_context(tempfile.TemporaryDirectory(prefix="fc_cache"))
    root_config = (
        ROOT_CONFIG.replace("[APPFONTS_PATH]", str(appfonts_path))
        .replace("[USERFONTS_PATH]", str(user_font_path))
        .replace("[CACHE_PATH]", cache_path)
    )
    fc_conf = ffi.gc(clib.FcConfigCreate(), clib.FcConfigDestroy)
    root_config_bytes = root_config.encode()
    clib.FcConfigParseAndLoadFromMemory(fc_conf, root_config_bytes, True)
    clib.FcConfigSetCurrent(fc_conf)
    return resource_manager
