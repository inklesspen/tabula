# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pathlib
import typing

import attr
import numpy as np
import numpy.typing as npt
import PIL.Image
import PIL.ImageChops
import pytest

import stilus.markdown
import stilus.pango_render
import stilus.types


CLARA_SIZE = stilus.types.Size(width=1072, height=1448)
FONT = "Tabula Quattro 6"


@pytest.fixture(scope="module")
def renderer():
    opts = stilus.types.Opts(
        dpi=300,
        screen_size=CLARA_SIZE,
    )
    instance = stilus.pango_render.PangoCairoRenderer(opts)
    return instance


@pytest.fixture(scope="module")
def count_markup():
    mdpath = pathlib.Path(__file__).parent / "sampletexts" / "count-of-monte-cristo.md"
    return [
        p.markup.replace("\n", " ")
        for p in stilus.markdown.make_paragraphs(mdpath.read_text(encoding="utf-8"))
    ]


@pytest.fixture(scope="module")
def great_markup():
    mdpath = pathlib.Path(__file__).parent / "sampletexts" / "great-expectations.md"
    return [
        p.markup.replace("\n", " ")
        for p in stilus.markdown.make_paragraphs(mdpath.read_text(encoding="utf-8"))
    ]


@pytest.fixture(scope="module")
def pride_markup():
    mdpath = pathlib.Path(__file__).parent / "sampletexts" / "pride-and-prejudice.md"
    return [
        p.markup.replace("\n", " ")
        for p in stilus.markdown.make_paragraphs(mdpath.read_text(encoding="utf-8"))
    ]


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class NpRenderPara:
    index: int
    rendered: npt.ArrayLike
    size: stilus.types.Size


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class PILRenderPara:
    index: int
    rendered: PIL.Image.Image
    size: stilus.types.Size


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class LaidOutPara:
    index: int
    screen_top: int
    screen_bottom: int


def composite_PIL_stilus_inversion(
    renderer: stilus.pango_render.PangoCairoRenderer,
    screen_size: stilus.types.Size,
    font: str,
    skip_height: int,
    cursor_y: int,
    markups: typing.List[str],
):
    half_screen = PIL.Image.new("L", (screen_size.width, cursor_y), "white")
    renders = []

    current_y = cursor_y
    for index, markup in reversed(tuple(enumerate(markups))):
        if current_y < 0:
            break
        render_opts = stilus.types.RenderOpts(
            font=font,
            markup=True,
            text=markup,
            alignment=stilus.types.Alignment.LEFT,
            margin_t=0,
            margin_b=0,
            margin_l=10,
            margin_r=10,
        )

        with renderer.create_surface() as surface:
            rendered_size = renderer.render(surface, render_opts)
            rendered_bytes = renderer.surface_to_bytes(surface, rendered_size)

        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), rendered_bytes, "raw", "L", 0, 1
        )

        renders.insert(0, PILRenderPara(index=index, rendered=im, size=rendered_size))
        current_y -= rendered_size.height
        if index > 0:
            current_y -= skip_height

    laidouts = [None for _ in renders]
    current_y = cursor_y
    index = len(renders) - 1
    while index >= 0:
        size = renders[index].size
        top = current_y - size.height
        laidouts[index] = LaidOutPara(
            index=index, screen_bottom=current_y, screen_top=top
        )
        current_y -= size.height
        if index > 0:
            current_y -= skip_height
        index -= 1

    for laidout in laidouts:
        if laidout is not None:
            render = renders[laidout.index]
            if laidout.screen_top < 0:
                cropped = render.rendered.crop(
                    (
                        0,
                        render.size.height - laidout.screen_bottom,
                        render.size.width,
                        render.size.height,
                    )
                )
                half_screen.paste(cropped, (0, 0))
            else:
                half_screen.paste(render.rendered, (0, laidout.screen_top))

    return half_screen.tobytes("raw")


def test_composite_PIL_stilus_inversion(renderer, count_markup, benchmark):
    skip_height = int(renderer.calculate_line_height(FONT))
    cursor_y = CLARA_SIZE.height // 2
    rendered_bytes = benchmark(
        composite_PIL_stilus_inversion,
        renderer,
        CLARA_SIZE,
        FONT,
        skip_height,
        cursor_y,
        count_markup,
    )
    im = PIL.Image.frombytes(
        "L", (CLARA_SIZE.width, cursor_y), rendered_bytes, "raw", "L", 0, 1
    )
    im.save(str(pathlib.Path(__file__).parent / "composite_PIL_stilus_inversion.png"))


def composite_PIL_PIL_inversion(
    renderer: stilus.pango_render.PangoCairoRenderer,
    screen_size: stilus.types.Size,
    font: str,
    skip_height: int,
    cursor_y: int,
    markups: typing.List[str],
):
    half_screen = PIL.Image.new("L", (screen_size.width, cursor_y), "white")
    renders = []

    current_y = cursor_y
    for index, markup in reversed(tuple(enumerate(markups))):
        if current_y < 0:
            break
        render_opts = stilus.types.RenderOpts(
            font=font,
            markup=True,
            text=markup,
            alignment=stilus.types.Alignment.LEFT,
            margin_t=0,
            margin_b=0,
            margin_l=10,
            margin_r=10,
        )

        with renderer.create_surface() as surface:
            rendered_size = renderer.render(surface, render_opts)
            rendered_bytes = renderer.surface_to_bytes(
                surface, rendered_size, skip_inversion=True
            )

        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), rendered_bytes, "raw", "L;I", 0, 1
        )

        renders.insert(0, PILRenderPara(index=index, rendered=im, size=rendered_size))
        current_y -= rendered_size.height
        if index > 0:
            current_y -= skip_height

    laidouts = [None for _ in renders]
    current_y = cursor_y
    index = len(renders) - 1
    while index >= 0:
        size = renders[index].size
        top = current_y - size.height
        laidouts[index] = LaidOutPara(
            index=index, screen_bottom=current_y, screen_top=top
        )
        current_y -= size.height
        if index > 0:
            current_y -= skip_height
        index -= 1

    for laidout in laidouts:
        if laidout is not None:
            render = renders[laidout.index]
            if laidout.screen_top < 0:
                cropped = render.rendered.crop(
                    (
                        0,
                        render.size.height - laidout.screen_bottom,
                        render.size.width,
                        render.size.height,
                    )
                )
                half_screen.paste(cropped, (0, 0))
            else:
                half_screen.paste(render.rendered, (0, laidout.screen_top))

    return half_screen.tobytes("raw")


def test_composite_PIL_PIL_inversion(renderer, count_markup, benchmark):
    skip_height = int(renderer.calculate_line_height(FONT))
    cursor_y = CLARA_SIZE.height // 2
    rendered_bytes = benchmark(
        composite_PIL_PIL_inversion,
        renderer,
        CLARA_SIZE,
        FONT,
        skip_height,
        cursor_y,
        count_markup,
    )
    im = PIL.Image.frombytes(
        "L", (CLARA_SIZE.width, cursor_y), rendered_bytes, "raw", "L", 0, 1
    )
    # im.save(str(pathlib.Path(__file__).parent / "composite_PIL_PIL_inversion.png"))


def composite_PIL_stilus_inversion(
    renderer: stilus.pango_render.PangoCairoRenderer,
    screen_size: stilus.types.Size,
    font: str,
    skip_height: int,
    cursor_y: int,
    markups: typing.List[str],
):
    half_screen = PIL.Image.new("L", (screen_size.width, cursor_y), "white")
    renders = []

    current_y = cursor_y
    for index, markup in reversed(tuple(enumerate(markups))):
        if current_y < 0:
            break
        render_opts = stilus.types.RenderOpts(
            font=font,
            markup=True,
            text=markup,
            alignment=stilus.types.Alignment.LEFT,
            margin_t=0,
            margin_b=0,
            margin_l=10,
            margin_r=10,
        )

        with renderer.create_surface() as surface:
            rendered_size = renderer.render(surface, render_opts)
            rendered_bytes = renderer.surface_to_bytes(surface, rendered_size)

        im = PIL.Image.frombytes(
            "L", rendered_size.as_tuple(), rendered_bytes, "raw", "L", 0, 1
        )

        renders.insert(0, PILRenderPara(index=index, rendered=im, size=rendered_size))
        current_y -= rendered_size.height
        if index > 0:
            current_y -= skip_height

    laidouts = [None for _ in renders]
    current_y = cursor_y
    index = len(renders) - 1
    while index >= 0:
        size = renders[index].size
        top = current_y - size.height
        laidouts[index] = LaidOutPara(
            index=index, screen_bottom=current_y, screen_top=top
        )
        current_y -= size.height
        if index > 0:
            current_y -= skip_height
        index -= 1

    for laidout in laidouts:
        if laidout is not None:
            render = renders[laidout.index]
            if laidout.screen_top < 0:
                cropped = render.rendered.crop(
                    (
                        0,
                        render.size.height - laidout.screen_bottom,
                        render.size.width,
                        render.size.height,
                    )
                )
                half_screen.paste(cropped, (0, 0))
            else:
                half_screen.paste(render.rendered, (0, laidout.screen_top))

    return half_screen.tobytes("raw")


def test_composite_PIL_stilus_inversion(renderer, count_markup, benchmark):
    skip_height = int(renderer.calculate_line_height(FONT))
    cursor_y = CLARA_SIZE.height // 2
    rendered_bytes = benchmark(
        composite_PIL_stilus_inversion,
        renderer,
        CLARA_SIZE,
        FONT,
        skip_height,
        cursor_y,
        count_markup,
    )
    im = PIL.Image.frombytes(
        "L", (CLARA_SIZE.width, cursor_y), rendered_bytes, "raw", "L", 0, 1
    )
    # im.save(str(pathlib.Path(__file__).parent / "composite_PIL_stilus_inversion.png"))


def composite_numpy(
    renderer: stilus.pango_render.PangoCairoRenderer,
    screen_size: stilus.types.Size,
    font: str,
    skip_height: int,
    cursor_y: int,
    markups: typing.List[str],
):
    half_screen = np.full((cursor_y, screen_size.width), 255, dtype=np.uint8)

    renders = []

    current_y = cursor_y
    for index, markup in reversed(tuple(enumerate(markups))):
        if current_y < 0:
            break
        render_opts = stilus.types.RenderOpts(
            font=font,
            markup=True,
            text=markup,
            alignment=stilus.types.Alignment.LEFT,
            margin_t=0,
            margin_b=0,
            margin_l=10,
            margin_r=10,
        )

        with renderer.create_surface() as surface:
            rendered_size = renderer.render(surface, render_opts)
            rendered_bytes = renderer.surface_to_bytes(surface, rendered_size)

        new_rendered = np.ndarray(
            rendered_size.as_numpy_shape(), dtype=np.uint8, buffer=rendered_bytes
        )

        renders.insert(
            0, NpRenderPara(index=index, rendered=new_rendered, size=rendered_size)
        )
        current_y -= rendered_size.height
        if index > 0:
            current_y -= skip_height

    laidouts = [None for _ in renders]
    current_y = cursor_y
    index = len(renders) - 1
    while index >= 0:
        size = renders[index].size
        top = current_y - size.height
        laidouts[index] = LaidOutPara(
            index=index, screen_bottom=current_y, screen_top=top
        )
        current_y -= size.height
        if index > 0:
            current_y -= skip_height
        index -= 1

    for laidout in laidouts:
        if laidout is not None:
            render = renders[laidout.index]
            if laidout.screen_top < 0:
                half_screen[0 : laidout.screen_bottom] = render.rendered[
                    -laidout.screen_top :
                ]
            else:
                half_screen[
                    laidout.screen_top : laidout.screen_bottom
                ] = render.rendered

    return half_screen.tobytes()


def test_composite_numpy(renderer, count_markup, benchmark):
    skip_height = int(renderer.calculate_line_height(FONT))
    cursor_y = CLARA_SIZE.height // 2
    rendered_bytes = benchmark(
        composite_numpy,
        renderer,
        CLARA_SIZE,
        FONT,
        skip_height,
        cursor_y,
        count_markup,
    )
    im = PIL.Image.frombytes(
        "L", (CLARA_SIZE.width, cursor_y), rendered_bytes, "raw", "L", 0, 1
    )
    # im.save(str(pathlib.Path(__file__).parent / "composite_numpy.png"))


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class ArrayRect:
    top: int
    bottom: int
    left: int
    right: int

    def to_stilus_rect(self):
        return stilus.types.Rect(
            origin=stilus.types.Point(x=self.left, y=self.top),
            spread=stilus.types.Size(
                width=self.right - self.left, height=self.bottom - self.top
            ),
        )


def bbox(img: npt.ArrayLike) -> ArrayRect:
    rows = np.any(img, axis=1)
    cols = np.any(img, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    return ArrayRect(top=rmin, bottom=rmax, left=cmin, right=cmax)


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class RenderBytes:
    rendered: bytes
    rect: stilus.types.Rect


def diff_numpy(old_image, new_image):
    render_diff = new_image - old_image
    changed_box = bbox(render_diff)
    changed: npt.ArrayLike = new_image[
        changed_box.top : changed_box.bottom,
        changed_box.left : changed_box.right,
    ]
    framelet = RenderBytes(
        rendered=changed.tobytes(), rect=changed_box.to_stilus_rect()
    )
    return framelet


def test_diff_numpy(renderer, great_markup, benchmark):
    render_opts = stilus.types.RenderOpts(
        font=FONT,
        markup=True,
        text=great_markup[-1],
        alignment=stilus.types.Alignment.LEFT,
        margin_t=0,
        margin_b=0,
        margin_l=10,
        margin_r=10,
    )

    with renderer.create_surface() as surface:
        rendered_size = renderer.render(surface, render_opts)
        rendered_bytes = renderer.surface_to_bytes(surface, rendered_size)

    new_image = np.ndarray(
        rendered_size.as_numpy_shape(), dtype=np.uint8, buffer=rendered_bytes
    )

    with renderer.create_surface() as surface:
        rendered_size = renderer.render(
            surface, attr.evolve(render_opts, text=great_markup[-1][:-20])
        )
        rendered_bytes = renderer.surface_to_bytes(surface, rendered_size)

    old_image = np.ndarray(
        rendered_size.as_numpy_shape(), dtype=np.uint8, buffer=rendered_bytes
    )

    framelet = benchmark(diff_numpy, old_image, new_image)

    # screen = PIL.Image.new("L", CLARA_SIZE.as_tuple(), "white")

    # im = PIL.Image.frombytes(
    #     "L", framelet.rect.spread.as_tuple(), framelet.rendered, "raw", "L", 0, 1
    # )
    # screen.paste(im, framelet.rect.as_pillow_box())
    # screen.save(str(pathlib.Path(__file__).parent / "diff_numpy.png"))


def diff_PIL(old_image, new_image):

    image_diff = PIL.ImageChops.difference(old_image, new_image)
    # image_diff.save("image_diff.png")

    changed_left, changed_top, changed_right, changed_bottom = image_diff.getbbox()
    changed_box = ArrayRect(
        top=changed_top, bottom=changed_bottom, left=changed_left, right=changed_right
    )
    changed = new_image.crop((changed_left, changed_top, changed_right, changed_bottom))
    framelet = RenderBytes(
        rendered=changed.tobytes("raw"), rect=changed_box.to_stilus_rect()
    )
    return framelet


def test_diff_PIL(renderer, great_markup, benchmark):
    render_opts = stilus.types.RenderOpts(
        font=FONT,
        markup=True,
        text=great_markup[-1],
        alignment=stilus.types.Alignment.LEFT,
        margin_t=0,
        margin_b=0,
        margin_l=10,
        margin_r=10,
    )
    with renderer.create_surface() as surface:
        rendered_size = renderer.render(surface, render_opts)
        rendered_bytes = renderer.surface_to_bytes(
            surface, rendered_size, skip_inversion=True
        )

    new_image = PIL.Image.frombytes(
        "L", rendered_size.as_tuple(), rendered_bytes, "raw", "L;I", 0, 1
    )

    with renderer.create_surface() as surface:
        rendered_size = renderer.render(
            surface, attr.evolve(render_opts, text=great_markup[-1][:-20])
        )
        rendered_bytes = renderer.surface_to_bytes(
            surface, rendered_size, skip_inversion=True
        )

    old_image = PIL.Image.frombytes(
        "L", rendered_size.as_tuple(), rendered_bytes, "raw", "L;I", 0, 1
    )

    framelet = benchmark(diff_PIL, old_image, new_image)
