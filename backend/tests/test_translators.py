import pytest
from app.translator.providers.offline_provider import OfflineTranslationProvider
from app.translator.manager import TranslationManager


@pytest.mark.asyncio
async def test_offline_provider_with_glossary():
    provider = OfflineTranslationProvider()
    text = "Chapter 1.\n\nJohn Smith held his sword and nodded to Mary."
    glossary = {
        "John Smith": "Trương Tam",
        "Mary": "Tiểu Muội",
    }
    result = await provider.translate(text, glossary=glossary)

    assert "Chương 1." in result
    assert "Trương Tam" in result
    assert "Tiểu Muội" in result
    assert "John Smith" not in result
    assert "Mary" not in result


@pytest.mark.asyncio
async def test_translation_manager_flow():
    mgr = TranslationManager()
    text = "Chapter 1: The Beginning.\n\nHe took a deep breath."
    glossary = {"The Beginning": "Khởi Nguyên"}

    events = []
    def on_progress(cur, tot, pct, msg):
        events.append((cur, tot, pct, msg))

    title, trans, prov, score = await mgr.translate_chapter(
        cleaned_text=text,
        chapter_title="Chapter 1",
        glossary=glossary,
        progress_callback=on_progress,
    )

    assert trans != ""
    assert len(events) > 0
    assert score > 0.0
