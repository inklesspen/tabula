# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# We cannot have automated tests, because the minute details of rendering
# depend on a number of things, including fonts installed on the host.
# So instead we have acceptance tests, which require human eyes.
import pathlib

import PIL.Image
import pytest

from stilus.types import RenderOpts, Opts, Size, WrapMode
from stilus.pango_render import PangoCairoRenderer

pytestmark = pytest.mark.usefixtures("goldenspath", "actualspath")

TI = (
    "Squire Trelawney, Doctor Livesey, and the rest of these gentlemen having asked me "
    "to write down the whole particulars about _<i>Treasure Island</i>_, from the "
    "beginning to the end, keeping nothing back but the bearings of the island, and "
    "that **<b>only</b>** because there is still treasure not yet lifted, I take up "
    "my pen in the year of grace 17—, and go back to the time when my father kept the "
    "Admiral Benbow Inn, and the brown old seaman, with the saber cut, first took up "
    "his lodging under our roof."
)


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
    opts = Opts(
        dpi=300,
        screen_size=Size(width=800, height=800),
        margin_t=6,
        margin_b=6,
        margin_l=6,
        margin_r=6,
    )
    instance = PangoCairoRenderer(opts)
    return instance


def test_ti(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: PangoCairoRenderer,
):
    render_opts = RenderOpts(font="B612 Regular 8", markup=True, text=TI)

    with renderer.create_surface() as surface:
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)

    im = PIL.Image.frombytes("L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1)
    imagepath = actualspath / f"{request.node.name}.png"
    im.save(imagepath)


def test_border(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: PangoCairoRenderer,
):
    render_opts = RenderOpts(
        font="TeX Gyre Pagella 8", markup=True, text=TI, draw_border=True
    )

    with renderer.create_surface() as surface:
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)

    im = PIL.Image.frombytes("L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1)
    outerim = PIL.Image.new("L", (1000, 1000), "white")
    outerim.paste(im, (100, 100))
    imagepath = actualspath / f"{request.node.name}.png"
    outerim.save(imagepath)
