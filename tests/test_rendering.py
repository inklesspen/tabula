import pathlib
import typing

import PIL.Image
import pytest
import timeflake

from tabula.commontypes import Size, Rect
from tabula.editor.doctypes import Paragraph
from tabula.editor.document import DocumentModel
from tabula.rendering.layout import LayoutManager
from tabula.rendering.rendertypes import ScreenInfo
from tabula.rendering.renderer import Renderer

if typing.TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

CLARA_SCREEN = ScreenInfo(size=Size(width=1072, height=1448), dpi=300)
FONT = "Tabula Quattro 6"
ZENDA = (
    """“I wonder when in the world you’re going to do anything, Rudolf?” said my brother’s wife.""",
    """“My dear Rose,” I answered, laying down my egg-spoon, “why in the world should I do anything? My position is a comfortable one. I have an income nearly sufficient for my wants (no one’s income is ever quite sufficient, you know), I enjoy an enviable social position: I am brother to Lord Burlesdon, and brother-in-law to that charming lady, his countess. Behold, it is enough!”""",
    """“You are nine-and-twenty,” she observed, “and you’ve done nothing but⁠—”""",
    """“Knock about? It is true. Our family doesn’t need to do things.”""",
    """This remark of mine rather annoyed Rose, for everybody knows (and therefore there can be no harm in referring to the fact) that, pretty and accomplished as she herself is, her family is hardly of the same standing as the Rassendylls. Besides her attractions, she possessed a large fortune, and my brother Robert was wise enough not to mind about her ancestry. Ancestry is, in fact, a matter concerning which the next observation of Rose’s has some truth.""",
    """“Good families are generally worse than any others,” she said.""",
    """Upon this I stroked my hair: I knew quite well what she meant.""",
    """“I’m so glad Robert’s is black!” she cried.""",
    """At this moment Robert (who rises at seven and works before breakfast) came in. He glanced at his wife: her cheek was slightly flushed; he patted it caressingly.""",
    """“What’s the matter, my dear?” he asked.""",
    """“She objects to my doing nothing and having red hair,” said I, in an injured tone.""",
    """“Oh! of course he can’t help his hair,” admitted Rose.""",
    """“It generally crops out once in a generation,” said my brother. “So does the nose. Rudolf has got them both.”""",
    """“I wish they didn’t crop out,” said Rose, still flushed.""",
    """“I rather like them myself,” said I, and, rising, I bowed to the portrait of Countess Amelia.""",
    """My brother’s wife uttered an exclamation of impatience.""",
    """“I wish you’d take that picture away, Robert,” said she.""",
    """“My dear!” he cried.""",
    """“Good heavens!” I added.""",
    """“Then it might be forgotten,” she continued.""",
    """“Hardly⁠—with Rudolf about,” said Robert, shaking his head.""",
    """“Why should it be forgotten?” I asked.""",
    """“Rudolf!” exclaimed my brother’s wife, blushing very prettily.""",
    """I laughed, and went on with my egg. At least I had shelved the question of what (if anything) I ought to do. And, by way of closing the discussion⁠—and also, I must admit, of exasperating my strict little sister-in-law a trifle more⁠—I observed:""",
    """“I rather like being an Elphberg myself.”""",
    """When I read a story, I skip the explanations; yet the moment I begin to write one, I find that I must have an explanation. For it is manifest that I must explain why my sister-in-law was vexed with my nose and hair, and why I ventured to call myself an Elphberg. For eminent as, I must protest, the Rassendylls have been for many generations, yet participation in their blood of course does not, at first sight, justify the boast of a connection with the grander stock of the Elphbergs or a claim to be one of that Royal House. For what relationship is there between Ruritania and Burlesdon, between the Palace at Strelsau or the Castle of Zenda and Number 305 Park Lane, W.?""",
)
IMAGE_SAVE_DIR = pathlib.Path(__file__).parent / "renders"
IMAGE_SAVE_DIR.mkdir(exist_ok=True)


def with_layout_manager(renderer: Renderer, document: DocumentModel):
    lm = LayoutManager(renderer=renderer, document=document, full_height=True)
    rendered = lm.render_update(FONT)
    target_im = PIL.Image.new("L", CLARA_SCREEN.size.as_tuple(), "white")
    framelet_im = PIL.Image.frombytes(
        "L", rendered.rect.pillow_size, rendered.image, "raw", "L", 0, 1
    )
    target_im.paste(framelet_im, rendered.rect.pillow_origin)
    target_im.save(str(IMAGE_SAVE_DIR / "layout-manager.png"))


@pytest.mark.skip("Disabled")
def test_with_layout_manager():
    renderer = Renderer(CLARA_SCREEN)
    session_id = timeflake.random()
    document = DocumentModel()
    document.session_id = session_id
    paras = [
        Paragraph(id=timeflake.random(), session_id=session_id, index=i, markdown=z)
        for i, z in enumerate(ZENDA[:-1])
    ]
    document.contents = paras
    document.currently = paras[-1]
    with_layout_manager(renderer, document)
