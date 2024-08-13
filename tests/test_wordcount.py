from tabula.editor.wordcount import count_plain_text


def test_plain_text():
    text = """“I wonder when in the world you’re going to do anything, Rudolf?” said my brother’s wife."""
    assert count_plain_text(text) == 16


def test_with_markdown():
    text = """“I wonder _when in_ the world you’re **going to** do anything, Rudolf?” said my brother’s wife."""
    assert count_plain_text(text) == 16


def test_with_open_markdown():
    text = """“I wonder when in the world you’re going to do _anything, Rudolf?” said my brother’s wife."""
    assert count_plain_text(text) == 16
