# NOVEL TRANSLATOR AI — API DOCUMENTATION

Hệ thống API backend được xây dựng trên FastAPI, cung cấp tài liệu tự động Swagger UI tại:
`http://localhost:8000/api/docs` và ReDoc tại `http://localhost:8000/api/redoc`.

---

## 1. Authentication & Common Response Formats

Tất cả các phản hồi lỗi từ hệ thống đều tuân thủ cấu trúc chuẩn, **không bao giờ trả về stack trace cho frontend**:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Thông điệp mô tả lỗi thân thiện với người dùng."
  }
}
```

Mỗi request được gắn kèm header `X-Request-ID` phục vụ truy vết và logging.

---

## 2. API Endpoints

### 2.1. Phân tích URL truyện (URL Analyzer)

- **Endpoint:** `POST /api/analyze`
- **Rate Limit:** 25 requests / phút (Anti-abuse)
- **SSRF Protection:** Kiểm tra tự động IP nội bộ, localhost, link-local, AWS/GCP metadata.

**Request Body:**
```json
{
  "url": "https://ncode.syosetu.com/n1444ie/"
}
```

**Response (Thành công - 200 OK):**
```json
{
  "success": true,
  "novel": {
    "id": 1,
    "title": "Tên tiểu thuyết",
    "author": "Tên tác giả",
    "cover": "https://example.com/cover.jpg",
    "description": "Mô tả / tóm tắt nội dung truyện...",
    "url": "https://ncode.syosetu.com/n1444ie/",
    "source_domain": "ncode.syosetu.com",
    "total_chapters": 12,
    "chapters": [
      {
        "id": 1,
        "chapter_number": 1,
        "title": "Chương 1: Khởi đầu",
        "url": "https://ncode.syosetu.com/n1444ie/1/",
        "status": "pending",
        "has_translation": false
      }
    ]
  }
}
```

---

### 2.2. Danh sách truyện & Chi tiết truyện (Novels)

#### Lấy danh sách truyện đã phân tích
- **Endpoint:** `GET /api/novels?limit=50&offset=0&search=keyword`
- **Response:** Mảng danh sách các bộ truyện kèm số chương đã dịch (`translated_count`).

#### Lấy chi tiết một bộ truyện
- **Endpoint:** `GET /api/novels/{id}`
- **Response:** Thông tin tổng quan, số chương, tác giả, ảnh bìa.

#### Lấy danh sách chương của truyện
- **Endpoint:** `GET /api/novels/{id}/chapters?limit=100&offset=0&sort=asc&filter_status=completed`
- **Parameters:**
  - `limit`: Số lượng chương (mặc định 100, tối đa 500)
  - `offset`: Phân trang
  - `sort`: `asc` (cũ -> mới) hoặc `desc` (mới -> cũ)
  - `search`: Từ khóa tìm kiếm tên chương
  - `filter_status`: `all`, `completed`, `pending`, `translating`, `failed`

#### Xóa truyện
- **Endpoint:** `DELETE /api/novels/{id}`

---

### 2.3. Hàng đợi dịch AI (Translation Queue)

#### Dịch một chương
- **Endpoint:** `POST /api/translate/chapter/{chapter_id}`
- **Request Body:**
```json
{
  "force": false
}
```
- **Response (200 OK):**
```json
{
  "job_id": "c1f7b03a-3bf4-4f80-9971-d64e05f63901",
  "chapter_id": 1,
  "status": "queued",
  "current_chunk": 0,
  "total_chunks": 0,
  "progress_percent": 0,
  "message": "Đã đưa vào hàng đợi dịch...",
  "error_message": null
}
```

#### Dịch hàng loạt chương (Bulk Translate)
- **Endpoint:** `POST /api/translate/bulk`
- **Request Body:**
```json
{
  "chapter_ids": [1, 2, 3, 4],
  "force": false
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "queued_count": 4,
  "jobs": [ ... ]
}
```

---

### 2.4. Tiến trình dịch thời gian thực (Realtime Progress)

#### Lấy trạng thái công việc
- **Endpoint:** `GET /api/jobs/{job_id}`

#### Stream tiến trình thời gian thực (Server-Sent Events)
- **Endpoint:** `GET /api/jobs/{job_id}/events`
- **Content-Type:** `text/event-stream`
- **Dữ liệu stream:**
```json
data: {"job_id": "...", "status": "translating", "current_chunk": 17, "total_chunks": 21, "progress_percent": 82, "message": "Đang dịch đoạn 17/21..."}
```

#### WebSocket Stream
- **Endpoint:** `ws://localhost:8000/api/ws/jobs/{job_id}`

---

### 2.5. Trình đọc truyện (Reader API)

- **Endpoint:** `GET /api/reader/{chapter_id}`
- **Response:**
```json
{
  "chapter_id": 1,
  "novel_id": 1,
  "novel_title": "Tên truyện",
  "chapter_number": 1,
  "chapter_title": "Chapter 1",
  "translated_title": "Chương 1: Mở đầu",
  "translated_text": "Nội dung đoạn 1...\n\nNội dung đoạn 2...",
  "original_text": "Original paragraph 1...\n\nOriginal paragraph 2...",
  "prev_chapter_id": null,
  "next_chapter_id": 2,
  "status": "completed"
}
```

---

### 2.6. Quản lý Thuật ngữ & Translation Memory (Glossary)

#### Xem danh sách thuật ngữ của truyện
- **Endpoint:** `GET /api/novels/{novel_id}/glossary`

#### Thêm / Cập nhật thuật ngữ
- **Endpoint:** `POST /api/novels/{novel_id}/glossary`
- **Request Body:**
```json
{
  "source_term": "张三",
  "translated_term": "Trương Tam",
  "note": "Nhân vật chính"
}
```

#### Xóa thuật ngữ
- **Endpoint:** `DELETE /api/novels/{novel_id}/glossary/{term_id}`

---

### 2.7. Health Check

- **Endpoint:** `GET /api/health`
- **Response:**
```json
{
  "status": "healthy",
  "app": "Novel Translator AI",
  "version": "1.0.0",
  "provider": "gemini"
}
```
