# Docker Setup với PostgreSQL + pgvector

Hướng dẫn thiết lập PostgreSQL với pgvector extension để lưu trữ embeddings.

## 🚀 Bắt đầu nhanh

### 1. Khởi động Docker container

```bash
docker-compose up -d
```

Lệnh này sẽ:
- Pull image `pgvector/pgvector:pg16`
- Khởi tạo PostgreSQL database
- Tự động chạy script `init.sql` để tạo tables và indexes
- Expose port 5432

### 2. Kiểm tra container đang chạy

```bash
docker ps
```

Hoặc xem logs:
```bash
docker-compose logs -f postgres
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Cấu hình environment

Copy file `.env.example` thành `.env`:
```bash
cp .env.example .env
```

Sửa `.env` với API key của bạn:
```env
GEMINI_API_KEY=your_actual_api_key_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_pass
```

### 5. Test kết nối database

```bash
python pgvector_storage.py
```

## 📊 Database Schema

### Table: `documents`
Lưu metadata của tài liệu:
- `doc_id` (PK): UUID/ID của document
- `file_name`: Tên file gốc
- `doc_title`: Tiêu đề văn bản
- `doc_type`: Loại văn bản (Quyết định, Thông báo...)
- `issue_date`: Ngày ban hành
- `major_topic`: Chủ đề chính
- ...

### Table: `chunks`
Lưu chunks với vector embeddings:
- `chunk_id` (PK): UUID của chunk
- `doc_id` (FK): Reference đến documents
- `chunk_text`: Nội dung văn bản
- `embedding`: Vector 768 chiều (pgvector)
- `content_type`: Loại nội dung
- `applicable_cohort`: Khóa áp dụng
- `value`, `unit`: Giá trị và đơn vị
- ...

## 🔍 Tìm kiếm

### Semantic Search (Vector similarity)
```python
from pgvector_storage import PgVectorStorage

storage = PgVectorStorage()
results = storage.semantic_search(
    query="học phí chương trình tiên tiến khóa 2024",
    limit=5,
    content_type="Chương trình tiên tiến"
)
```

### Keyword Search (Full-text)
```python
results = storage.keyword_search("học phí", limit=10)
```

## 🛠️ Quản lý Docker

### Dừng containers
```bash
docker-compose down
```

### Dừng và xóa data (CẢNH BÁO: Xóa toàn bộ dữ liệu)
```bash
docker-compose down -v
```

### Restart containers
```bash
docker-compose restart
```

### Truy cập PostgreSQL shell
```bash
docker exec -it chatbot_pgvector psql -U chatbot_user -d chatbot_db
```

Trong psql shell:
```sql
-- Kiểm tra extension pgvector
\dx

-- Xem các tables
\dt

-- Đếm số documents
SELECT COUNT(*) FROM documents;

-- Đếm số chunks
SELECT COUNT(*) FROM chunks;

-- Test vector search
SELECT chunk_id, chunk_text, 
       embedding <=> '[0.1, 0.2, ...]'::vector as distance
FROM chunks
ORDER BY distance
LIMIT 5;
```

## 📈 Performance Tips

### 1. HNSW Index (đã tạo sẵn)
```sql
CREATE INDEX chunks_embedding_idx ON chunks 
USING hnsw (embedding vector_cosine_ops);
```

### 2. IVFFlat Index (alternative)
```sql
CREATE INDEX chunks_embedding_ivf_idx ON chunks 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);
```

### 3. Monitoring
```bash
docker stats chatbot_pgvector
```

## 🔧 Troubleshooting

### Port 5432 đã được sử dụng
Đổi port trong `docker-compose.yml`:
```yaml
ports:
  - "5433:5432"  # Host:Container
```

Và update `.env`:
```env
POSTGRES_PORT=5433
```

### Container không khởi động
Xem logs chi tiết:
```bash
docker-compose logs postgres
```

### Reset toàn bộ
```bash
docker-compose down -v
docker-compose up -d
```

## 📚 Tài liệu tham khảo

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
