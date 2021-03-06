# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# We cannot have automated tests, because the minute details of rendering
# depend on a number of things, including fonts installed on the host.
# So instead we have acceptance tests, which require human eyes.
import math
import pathlib

import attr
import PIL.Image
import pytest

from stilus.types import RenderOpts, Opts, Size, Alignment
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

VERSE = (
    "<big>Paradise Lost</big> by John Milton",
    """Of Man’s first disobedience, and the fruit
Of that forbidden Tree, whose mortal taste
Brought death into the world, and all our woe,
With loss of Eden, till one greater Man
Restore us, and regain the blissful seat[…]""",
    "<big>The Iliad</big> by Homer",
    """O Goddess! Sing the wrath of Peleus’ son,
Achilles; sing the deadly wrath that brought
Woes numberless upon the Greeks, and swept
To Hades many a valiant soul, and gave
Their limbs a prey to dogs and birds of air⁠—
For so had Jove appointed⁠—from the time
When the two chiefs, Atrides, king of men,
And great Achilles, parted first as foes.""",
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
    )
    instance = PangoCairoRenderer(opts)
    return instance


def test_ti(
    request: pytest.FixtureRequest,
    actualspath: pathlib.Path,
    renderer: PangoCairoRenderer,
):
    render_opts = RenderOpts(
        font="Noto Sans 8", markup=True, text=TI, margin_t=0, margin_b=0
    )

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
    base_render_opts = RenderOpts(
        font="Noto Serif 6",
        markup=True,
        text="n/a",
        margin_t=0,
        margin_b=0,
        margin_l=6,
        margin_r=6,
    )
    skip_height = math.ceil(renderer.calculate_line_height(base_render_opts.font))
    outerim = PIL.Image.new("L", (1000, 1000), "white")
    with renderer.create_surface() as surface:
        rendered_size = renderer.render_border(surface)
        buf = renderer.surface_to_bytes(surface, rendered_size)
        im = PIL.Image.frombytes("L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1)
        outerim.paste(im, (100, 100))

        skip_y = 106

    with renderer.create_surface() as surface:
        render_opts = attr.evolve(
            base_render_opts,
            text=VERSE[0],
            alignment=Alignment.CENTER,
        )
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)
        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1
        ).crop((6, 0, rendered_size.width - 12, rendered_size.height))
        outerim.paste(im, (106, skip_y))
        skip_y += rendered_size.height + skip_height

    with renderer.create_surface() as surface:
        render_opts = attr.evolve(
            base_render_opts,
            text=VERSE[1],
        )
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)
        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1
        ).crop((6, 0, rendered_size.width - 12, rendered_size.height))
        outerim.paste(im, (106, skip_y))
        skip_y += rendered_size.height + skip_height

    with renderer.create_surface() as surface:
        render_opts = attr.evolve(
            base_render_opts,
            text=VERSE[2],
            alignment=Alignment.CENTER,
        )
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)
        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1
        ).crop((6, 0, rendered_size.width - 12, rendered_size.height))
        outerim.paste(im, (106, skip_y))
        skip_y += rendered_size.height + skip_height

    with renderer.create_surface() as surface:
        render_opts = attr.evolve(
            base_render_opts,
            text=VERSE[3],
        )
        rendered_size = renderer.render(surface, render_opts)
        buf = renderer.surface_to_bytes(surface, rendered_size)
        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1
        ).crop((6, 0, rendered_size.width - 12, rendered_size.height))
        outerim.paste(im, (106, skip_y))
        # skip_y += rendered_size.height + skip_height

    # im = PIL.Image.frombytes("L", rendered_size.as_tuple(), buf, "raw", "L", 0, 1)
    # outerim.paste(im, (100, 100))
    imagepath = actualspath / f"{request.node.name}.png"
    outerim.save(imagepath)
