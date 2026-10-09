from app.translator.quality_check import QualityChecker


def test_quality_check_empty_translation():
    res = QualityChecker.check_chunk("Hello world", "")
    assert res.is_valid is False
    assert res.score == 0.0


def test_quality_check_ai_refusal_hallucination():
    source = "The dark lord stood atop the tower of doom."
    trans = "As an AI language model, I cannot translate this text."
    res = QualityChecker.check_chunk(source, trans)
    assert res.is_valid is False
    assert any("từ chối" in issue for issue in res.issues)


def test_quality_check_repetition_loop():
    source = "A brief walk in the garden under the sunlight."
    trans = "Hắn bước đi trong hoa viên. Hắn bước đi trong hoa viên. Hắn bước đi trong hoa viên."
    res = QualityChecker.check_chunk(source, trans)
    assert res.is_valid is False
    assert any("lặp" in issue for issue in res.issues)


def test_quality_check_valid():
    source = "Chapter 1.\n\nHe smiled and drew his legendary sword.\n\nThe battle was about to begin."
    trans = "Chương 1.\n\nHắn mỉm cười và rút ra thanh kiếm truyền thuyết của mình.\n\nTrận chiến sắp sửa bắt đầu."
    res = QualityChecker.check_chunk(source, trans)
    assert res.is_valid is True
    assert res.score >= 0.8
