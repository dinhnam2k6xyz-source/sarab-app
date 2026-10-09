# NOVEL TRANSLATOR AI — URL → VIETNAMESE

Hệ thống web app dịch tiểu thuyết, web novel từ URL bất kỳ sang tiếng Việt bằng AI với chất lượng cao, giữ nguyên ngữ cảnh câu thoại, không nuốt đoạn, hỗ trợ Translation Memory (Glossary) và trình đọc truyện hiện đại.

---

## 🚀 Tính năng nổi bật

1. **Phân tích URL thông minh (URL Analyzer):**
   - Tự động nhận diện cấu trúc trang, tên truyện, tác giả, ảnh bìa, mô tả và mục lục toàn bộ chương.
   - Hỗ trợ các website truyện phổ biến (Syosetu Nhật Bản, Royal Road Âu Mỹ, ReadNovelFull, Wuxiaworld...) và có Generic Scraper thông minh làm fallback cho bất kỳ website nào.

2. **Bảo mật & Chống tấn công SSRF:**
   - Kiểm tra nghiêm ngặt URL đầu vào, chặn truy cập vào `localhost`, `127.0.0.1`, IP mạng nội bộ (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7) và endpoint metadata đám mây (AWS, GCP, Azure).

3. **Làm sạch nội dung (Content Cleaner):**
   - Loại bỏ hoàn toàn quảng cáo, tracking, banner kêu gọi donate, watermark và menu điều hướng.
   - Giữ nguyên tiêu đề chương, đoạn văn (paragraphs), lời thoại nhân vật (`「...」`, `"..."`), xuống dòng và dấu câu.
   - Chuẩn hóa Unicode NFKC và HTML entities.

4. **Chia đoạn thông minh (Smart Chunking):**
   - Chia văn bản theo ranh giới đoạn văn tự nhiên (không bao giờ cắt giữa câu).
   - Truyền ngữ cảnh của đoạn trước (Context Hint) để AI nắm bắt diễn biến và đại từ xưng hô.

5. **Đa dạng AI Translation Providers:**
   - Hỗ trợ Google Gemini (`gemini-1.5-flash`, `gemini-2.0-flash`), OpenAI (`gpt-4o-mini`, `gpt-4o`), DeepL và bộ dịch Offline Fallback.
   - Tự động thử lại (Retry) với exponential backoff và chuyển đổi sang Fallback Provider nếu gặp sự cố.

6. **Translation Memory & Glossary:**
   - Quản lý bảng thuật ngữ tên nhân vật, địa danh, chiêu thức.
   - Ép buộc AI dịch đồng nhất tên nhân vật xuyên suốt mọi chương truyện.

7. **Kiểm tra chất lượng (Quality Check):**
   - Phát hiện mất đoạn, đoạn rỗng, câu dịch bất thường, lặp câu hoặc AI hallucination.
   - Tự động thử lại đoạn bị lỗi mà không bắt người dùng dịch lại cả chương.

8. **Lưu trữ & Cache SHA-256:**
   - Tính toán hash SHA-256 của nội dung gốc. Khi gặp lại chương đã dịch, trả về ngay lập tức không tốn token AI.

9. **Tiến trình thời gian thực (Realtime Progress):**
   - Theo dõi từng bước: Đang tải nội dung... → Đang chia đoạn... → Đang dịch (17/21 đoạn - 82%) → Đang kiểm tra... → Hoàn thành!
   - Sử dụng Server-Sent Events (SSE) và WebSocket, phản ánh đúng tiến độ xử lý thực tế.

10. **Trình đọc truyện hiện đại (Reader):**
    - Điều chỉnh kích thước chữ, khoảng cách dòng, độ rộng trang đọc.
    - Chế độ giao diện: Tối (Dark), Giấy ấm (Sepia), Sáng (Light).
    - Chế độ hiển thị song ngữ (Bilingual) đối chiếu bản dịch và bản gốc.
    - Tự động ghi nhớ vị trí đọc (Reading position auto-save).

---

## 🛠️ Tech Stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide React, Glassmorphism UI.
- **Backend:** Python 3.12, FastAPI, Pydantic v2, BeautifulSoup4, httpx, lxml, SQLAlchemy 2.0 (Async), Alembic.
- **Database:** PostgreSQL (hỗ trợ SQLite out-of-the-box cho môi trường dev local).
- **Queue & Async:** Redis, Celery, Async Background Workers, Server-Sent Events (SSE).
- **Testing:** Pytest, pytest-asyncio.
- **DevOps:** Docker, docker-compose.

---

## 📁 Cấu trúc thư mục

```
sarab-app/
├── backend/
│   ├── alembic/              # Database migration scripts
│   ├── app/
│   │   ├── api/v1/           # API routers (analyze, novels, chapters, translate, jobs, glossary)
│   │   ├── cleaner/          # Content cleaner & Unicode normalizer
│   │   ├── core/             # Config, SSRF security, logging, database, rate limiting
│   │   ├── models/           # SQLAlchemy models (Novel, Chapter, Translation, Jobs, Glossary...)
│   │   ├── queue/            # Background job runner, progress hub & Celery tasks
│   │   ├── schemas/          # Pydantic v2 schemas
│   │   ├── scrapers/         # Adapter Pattern scrapers (Syosetu, RoyalRoad, ReadNovelFull, Generic)
│   │   ├── translator/       # Translation manager, chunker, quality check & AI providers
│   │   └── main.py           # FastAPI entrypoint & middleware
│   ├── tests/                # Pytest test suite (SSRF, scrapers, cleaner, chunker, API...)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router (Home, Novel Detail, Reader)
│   │   ├── components/       # Navbar, TranslationProgressModal, GlossaryModal
│   │   ├── lib/              # API client with SSE tracking
│   │   └── types/            # TypeScript data contracts
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml        # Multi-container orchestration (5 services)
├── .env.example              # Environment variables template
├── API_DOCUMENTATION.md      # Detailed API reference
└── README.md
```

---

## 💻 Hướng dẫn cài đặt & Chạy ứng dụng

### Bước 1: Clone kho mã nguồn

```bash
git clone <repository_url>
cd sarab-app
```

### Bước 2: Cấu hình biến môi trường (`.env`)

Sao chép file `.env.example` thành `.env`:

```bash
cp .env.example .env
```

Điền các thông tin API key của bạn:
- `TRANSLATION_PROVIDER=gemini` (hoặc `openai`, `deepl`, `offline`)
- `GEMINI_API_KEY=your_gemini_api_key_here`
- `OPENAI_API_KEY=your_openai_api_key_here`

*(Ghi chú: Nếu chưa có API key, bạn có thể để `TRANSLATION_PROVIDER=offline` để hệ thống tự động dịch bằng bộ dịch Offline chuyên dụng mà không tốn phí).*

---

### Cách 1: Chạy toàn bộ hệ thống bằng Docker (Khuyên dùng)

Chỉ cần một lệnh duy nhất:

```bash
docker compose up -d
```

Lệnh trên sẽ tự động khởi động toàn bộ 5 dịch vụ:
1. `novel_postgres`: Cơ sở dữ liệu PostgreSQL
2. `novel_redis`: Hàng đợi Redis
3. `novel_backend`: FastAPI Backend (tự động chạy migrations)
4. `novel_worker`: Celery Background Worker
5. `novel_frontend`: Next.js Web App

- Truy cập Web App: **http://localhost:3000**
- Swagger API Docs: **http://localhost:8000/api/docs**

---

### Cách 2: Chạy thủ công trên máy cục bộ (Development)

#### 1. Cài đặt Dependencies Backend

```bash
cd backend
python -m venv .venv
# Trên Windows:
.\.venv\Scripts\activate
# Trên Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

#### 2. Chạy Database Migrations

```bash
alembic upgrade head
```

#### 3. Khởi động Backend Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend sẽ hoạt động tại: **http://localhost:8000**

#### 4. Khởi động Frontend

Mở một terminal mới:

```bash
cd frontend
npm install
npm run dev
```

Frontend sẽ hoạt động tại: **http://localhost:3000**

---

## 🧪 Chạy kiểm thử tự động (Testing)

Hệ thống đi kèm bộ kiểm thử bao quát toàn bộ logic cốt lõi:

```bash
cd backend
python -m pytest
```

Kết quả kiểm thử bao gồm:
- ✅ `test_ssrf.py`: Chống tấn công SSRF, chặn IP nội bộ và DNS loopback.
- ✅ `test_cleaner.py`: Làm sạch HTML, loại bỏ quảng cáo, chuẩn hóa Unicode.
- ✅ `test_chunker.py`: Chia đoạn văn bản giữ nguyên ranh giới hội thoại và ngữ cảnh.
- ✅ `test_quality_check.py`: Kiểm tra chất lượng bản dịch, chống lặp câu và ảo giác AI.
- ✅ `test_scrapers.py`: Cơ chế phân giải Scraper và trích xuất thông tin.
- ✅ `test_translators.py`: Kiểm tra luồng dịch Offline và Glossary Translation Memory.
- ✅ `test_api.py`: Kiểm tra các API endpoints và xử lý mã lỗi.

---

## 📖 Hướng dẫn sử dụng

1. **Phân tích truyện:**
   - Dán URL của một bộ truyện vào ô nhập tại trang chủ (ví dụ: `https://ncode.syosetu.com/n1444ie/`).
   - Nhấn **PHÂN TÍCH TRUYỆN**.
2. **Xem danh sách chương:**
   - Xem thông tin tác giả, ảnh bìa, tóm tắt và toàn bộ các chương đã lấy về.
3. **Quản lý Thuật ngữ (Glossary):**
   - Nhấn nút **Thuật ngữ / Glossary** để thêm các tên nhân vật hoặc thuật ngữ quan trọng.
4. **Dịch chương:**
   - Chọn một chương hoặc chọn nhiều chương và bấm **Dịch chương đã chọn**.
   - Theo dõi thanh tiến trình thời gian thực (đếm từng đoạn theo % thực tế).
5. **Đọc truyện:**
   - Khi chương hiển thị trạng thái `✅ Đã dịch`, bấm **Đọc ngay** để thưởng thức bản dịch trên giao diện Reader chuyên nghiệp.
