from app.translator.chunker import ContentChunker


def test_chunker_small_text_single_chunk():
    text = "Đoạn 1: Mở đầu câu chuyện.\n\nĐoạn 2: Nhân vật chính thức tỉnh ma pháp."
    chunks = ContentChunker.chunk(text, max_chunk_chars=1000)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 1
    assert chunks[0].total_chunks == 1
    assert len(chunks[0].paragraphs) == 2
    assert chunks[0].context_hint == ""


def test_chunker_splits_at_paragraph_boundaries():
    p1 = "A" * 150
    p2 = "B" * 150
    p3 = "C" * 150
    text = f"{p1}\n\n{p2}\n\n{p3}"

    # Set max_chunk_chars so that two paragraphs exceed limit
    chunks = ContentChunker.chunk(text, max_chunk_chars=200)

    assert len(chunks) == 3
    assert chunks[0].chunk_index == 1
    assert chunks[0].total_chunks == 3
    assert chunks[0].text == p1
    assert chunks[1].text == p2
    assert chunks[2].text == p3

    # Check context overlap in second and third chunks
    assert chunks[1].context_hint == p1
    assert chunks[2].context_hint == p2
