# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# We cannot have automated tests, because the minute details of rendering
# depend on a number of things, including fonts installed on the host.
# So instead we have acceptance tests, which require human eyes.
import pathlib
import typing

import PIL.Image
import pytest

from stilus.types import Size
from notare.host.rendering import ModalDialog
from notare.host.help import COMPOSES_TEMPLATE, HELP
from notare.host.loop import CIRCLED_ALPHANUMERICS
from notare.protocol import Framelet

pytestmark = pytest.mark.usefixtures("goldenspath", "actualspath")

CLARA_SIZE = Size(width=1072, height=1448)


@pytest.fixture(scope="module")
def goldenspath():
    testpath = pathlib.Path(__file__)
    goldenspath = testpath.parent / "renders" / "goldens"
    assert goldenspath.is_dir(), "Goldens path does not exist"
    return goldenspath


@pytest.fixture(scope="module")
def actualspath():
    testpath = pathlib.Path(__file__)
    actualspath = testpath.parent / "renders" / "actuals"
    assert actualspath.is_dir(), "Actuals path does not exist"
    for impath in actualspath.glob("*.png"):
        impath.unlink()
    return actualspath


@pytest.fixture(scope="module")
def renderer():
    return ModalDialog(screen_size=CLARA_SIZE, dpi=300)


def make_image(framelets: typing.List[Framelet]) -> PIL.Image:
    im = PIL.Image.new("L", CLARA_SIZE.as_tuple(), color=0)
    for framelet in framelets:
        src = PIL.Image.frombytes(
            "L",
            (framelet.rect.width, framelet.rect.height),
            Framelet.decode_bytes(framelet.image),
            "raw",
            "L",
            0,
            1,
        )
        im.paste(src, (framelet.rect.x, framelet.rect.y))
    return im


def test_frame(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: ModalDialog,
):
    ops = [renderer.render_frame(), renderer.render_header()]
    im = make_image(ops)

    imagepath = actualspath / f"{request.node.name}.png"
    im.save(imagepath)


def test_help(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: ModalDialog,
):
    ops = renderer.render_dialog(HELP, "Noto Serif 8")
    im = make_image(ops)

    imagepath = actualspath / f"{request.node.name}.png"
    im.save(imagepath)


def test_composes(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: ModalDialog,
):
    ops = renderer.render_dialog(COMPOSES_TEMPLATE, "Noto Serif 6")
    im = make_image(ops)

    imagepath = actualspath / f"{request.node.name}.png"
    im.save(imagepath)


SYSTEM_MENU = f"""
<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['1']}</span> \u00B7 \u00B7 \u00B7 New Session
<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['2']}</span> \u00B7 \u00B7 \u00B7 Resume Session
<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['3']}</span> \u00B7 \u00B7 \u00B7 Export Markdown

<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['Y']}</span> \u00B7 \u00B7 \u00B7 Wifi
<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['N']}</span> \u00B7 \u00B7 \u00B7 Clock

<span font="Noto Sans Symbols">{CIRCLED_ALPHANUMERICS['0']}</span> \u00B7 \u00B7 \u00B7 Shutdown
""".strip()


def test_system_menu(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: ModalDialog,
):
    ops = renderer.render_dialog(SYSTEM_MENU, "Noto Serif 8", margin_lr=30)
    im = make_image(ops)

    imagepath = actualspath / f"{request.node.name}.png"
    im.save(imagepath)
