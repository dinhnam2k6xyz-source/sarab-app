import pytest
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.core.database import init_db, AsyncSessionLocal
from app.models.novel import Novel, Chapter, ChapterContent, Translation, TranslationJob
from app.queue.job_runner import execute_translation_job


@pytest.mark.asyncio
async def test_full_end_to_end_flow():
    # 1. Initialize Database
    await init_db()

    test_uid = uuid.uuid4().hex[:8]
    test_url = f"https://test-novel-{test_uid}.example.com/fiction/1"
    chapter_url = f"{test_url}/chapter-1"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Test Health check
        res = await client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        # 3. Insert a mock novel and chapter for end-to-end translation pipeline test
        async with AsyncSessionLocal() as session:
            novel = Novel(
                url=test_url,
                title="Kiếm Đạo Độc Tôn Thí Nghiệm",
                author="Phong Hỏa",
                description="Bộ truyện thí nghiệm dịch thuật AI.",
                source_domain=f"test-novel-{test_uid}.example.com",
                total_chapters=1,
            )
            session.add(novel)
            await session.flush()

            chapter = Chapter(
                novel_id=novel.id,
                chapter_number=1,
                title="Chapter 1: The Awakening Sword",
                url=chapter_url,
                status="pending",
            )
            session.add(chapter)
            await session.flush()

            raw_sample_content = (
                "<div id='chapter-content'>"
                "<p>The legendary sword rested on the ancient stone altar.</p>"
                "<p>\"Who dares disturb my sleep?\" a mysterious voice echoed.</p>"
                "<p>John Smith took a deep breath and drew his sword.</p>"
                "</div>"
            )
            content = ChapterContent(
                chapter_id=chapter.id,
                raw_html=raw_sample_content,
                cleaned_text=(
                    "The legendary sword rested on the ancient stone altar.\n\n"
                    "\"Who dares disturb my sleep?\" a mysterious voice echoed.\n\n"
                    "John Smith took a deep breath and drew his sword."
                ),
                paragraph_count=3,
                char_count=180,
                source_hash="test_sha_hash_12345",
            )
            session.add(content)
            await session.commit()

            novel_id = novel.id
            chapter_id = chapter.id

        # 4. Add Glossary Term
        gloss_res = await client.post(
            f"/api/novels/{novel_id}/glossary",
            json={
                "source_term": "John Smith",
                "translated_term": "Trương Tam",
                "note": "Nhân vật chính",
            },
        )
        assert gloss_res.status_code == 200
        assert gloss_res.json()["translated_term"] == "Trương Tam"

        # 5. Enqueue Translation Job
        trans_res = await client.post(f"/api/translate/chapter/{chapter_id}")
        assert trans_res.status_code == 200
        job_data = trans_res.json()
        job_id = job_data["job_id"]
        assert job_data["status"] == "queued"

        # 6. Wait for the background worker job to reach completed
        for _ in range(150):
            await asyncio.sleep(0.2)
            job_check = await client.get(f"/api/jobs/{job_id}")
            if job_check.json()["status"] in ("completed", "failed"):
                break

        # 7. Check Job Status
        job_check = await client.get(f"/api/jobs/{job_id}")
        assert job_check.status_code == 200
        assert job_check.json()["status"] == "completed"
        assert job_check.json()["progress_percent"] == 100

        # 8. Check Reader API
        reader_res = await client.get(f"/api/reader/{chapter_id}")
        assert reader_res.status_code == 200
        reader_data = reader_res.json()
        assert reader_data["novel_title"] == "Kiếm Đạo Độc Tôn Thí Nghiệm"
        assert reader_data["chapter_number"] == 1
        assert reader_data["status"] == "completed"
        assert reader_data["translated_text"] != ""
        # Verify glossary was applied!
        assert "Trương Tam" in reader_data["translated_text"]

        # 9. Test Caching: Translating again should hit cache instantly
        trans_res_2 = await client.post(f"/api/translate/chapter/{chapter_id}")
        job_id_2 = trans_res_2.json()["job_id"]
        for _ in range(30):
            await asyncio.sleep(0.05)
            job_check_2 = await client.get(f"/api/jobs/{job_id_2}")
            if job_check_2.json()["status"] in ("completed", "failed"):
                break

        assert job_check_2.json()["status"] == "completed"
        assert "Cache" in job_check_2.json()["message"]
