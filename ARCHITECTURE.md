# 🏗️ Kiến trúc hệ thống ChatBot - Trợ lý học vụ

## 📊 Tổng quan

Hệ thống xử lý và lưu trữ tài liệu học vụ (PDF) → Trích xuất metadata → Lưu vào PostgreSQL + pgvector → Semantic Search

---

## 🗂️ Cấu trúc thư mục đề xuất

```
ChatBot/
├── data/
│   ├── raw_pdfs/                      # PDFs gốc (KHÔNG commit lên Git)
│   │   ├── THONGBAO/                  # 34 files CTDT (Chương trình đào tạo)
│   │   ├── QUY_DINH/                  # Quy định học phí, rèn luyện
│   │   └── QUY_CHE/                   # Quy chế đào tạo
│   │
│   ├── processed/                     # Kết quả xử lý
│   │   ├── json/                      # JSON structured data
│   │   │   ├── THONGBAO/              # Theo từng nhóm
│   │   │   ├── QUY_DINH/
│   │   │   └── QUY_CHE/
│   │   └── csv/                       # CSV để kiểm tra manual
│   │
│   └── logs/                          # Logs xử lý
│       └── batch_YYYYMMDD_HHMMSS.log
│
├── src/
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── gemini_extractor.py        # Gemini API logic
│   │   └── schemas.py                 # Pydantic schemas
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── pgvector_storage.py        # PostgreSQL + pgvector
│   │   └── embeddings.py              # Generate embeddings
│   │
│   ├── search/
│   │   ├── __init__.py
│   │   └── semantic_search.py         # Vector similarity search
│   │
│   └── api/                           # FastAPI (Giai đoạn 2)
│       ├── __init__.py
│       └── main.py
│
├── scripts/
│   ├── batch_process.py               # Xử lý hàng loạt PDFs
│   ├── migrate_to_db.py               # Load JSON → PostgreSQL
│   └── verify_data.py                 # Kiểm tra data quality
│
├── tests/
│   └── test_extraction.py
│
├── main.py                            # Script xử lý 1 file (hiện tại)
├── batch_processor.py                 # Batch processor (hiện tại)
├── pgvector_storage.py               # DB storage (hiện tại)
├── chatbot_storage.py                # Legacy storage
├── docker-compose.yml                # PostgreSQL + pgvector
├── init.sql                          # DB schema
├── requirements.txt
├── .env                              # API keys (KHÔNG commit)
├── .gitignore
└── README.md
```

---

## 🔄 Quy trình xử lý dữ liệu

### **Giai đoạn 1: Trích xuất (Extraction Pipeline)**

```
┌─────────────┐
│  PDF Files  │
│  (34 files) │
└──────┬──────┘
       │
       ▼
┌──────────────────────────┐
│  batch_process.py        │
│  ├─ Scan folder          │
│  ├─ Upload to Gemini     │
│  ├─ Extract metadata     │
│  └─ Save JSON + CSV      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  processed/json/         │
│  ├─ File1_output.json    │
│  ├─ File2_output.json    │
│  └─ ...                  │
└──────────────────────────┘
```

### **Giai đoạn 2: Lưu trữ (Storage Pipeline)**

```
┌──────────────────────────┐
│  processed/json/*.json   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  migrate_to_db.py        │
│  ├─ Read JSON files      │
│  ├─ Generate embeddings  │
│  └─ Insert to PostgreSQL │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  PostgreSQL + pgvector   │
│  ├─ documents table      │
│  ├─ chunks table         │
│  └─ vector index (HNSW) │
└──────────────────────────┘
```

### **Giai đoạn 3: Tìm kiếm (Search Pipeline)**

```
User Query: "Học phí khóa 2025?"
           │
           ▼
┌──────────────────────────┐
│  semantic_search.py      │
│  ├─ Embed query          │
│  ├─ Vector similarity    │
│  └─ Rank results         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Top-K relevant chunks   │
│  + Full context          │
└──────────────────────────┘
```

---

## 💾 Chiến lược lưu trữ

### **1. Database Schema (PostgreSQL)**

```sql
-- Bảng documents (metadata cấp tài liệu)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(100) UNIQUE NOT NULL,
    file_name VARCHAR(255),
    doc_title TEXT,
    doc_type VARCHAR(50),          -- "Thông báo CTDT", "Quy định", etc.
    category VARCHAR(50),           -- "THONGBAO", "QUY_DINH", "QUY_CHE"
    issue_number VARCHAR(100),
    issuing_authority VARCHAR(255),
    issue_date DATE,
    effective_date VARCHAR(100),
    expiration_date DATE,
    major_topic VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Bảng chunks (metadata cấp đoạn văn + vector)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(150) UNIQUE NOT NULL,
    doc_id VARCHAR(100) REFERENCES documents(doc_id),
    page_number INTEGER,
    section_title TEXT,
    chunk_topic VARCHAR(255),
    content_type VARCHAR(100),     -- "Đại trà", "CLCQ", etc.
    specific_target VARCHAR(255),
    applicable_cohort VARCHAR(100), -- "Khóa 2024", "Khóa 2025"
    value NUMERIC,
    unit VARCHAR(50),
    keywords TEXT[],
    chunk_text TEXT NOT NULL,
    embedding vector(768),         -- Gemini embedding
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index cho vector search
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);

-- Index cho filtering
CREATE INDEX idx_doc_category ON documents(category);
CREATE INDEX idx_chunk_cohort ON chunks(applicable_cohort);
CREATE INDEX idx_chunk_content_type ON chunks(content_type);
```

### **2. File Storage (JSON/CSV)**

**Lợi ích:**
- ✅ Backup dễ dàng
- ✅ Version control (Git LFS cho JSON)
- ✅ Dễ debug và kiểm tra manual
- ✅ Có thể re-import nếu DB bị lỗi

**Tổ chức:**
```
processed/json/THONGBAO/
├── CTDT_CNTT_K24_output.json
├── CTDT_CNTT_K25_output.json
└── ...

processed/csv/THONGBAO/
├── CTDT_CNTT_K24_chunks.csv
├── CTDT_CNTT_K25_chunks.csv
└── ...
```

---

## 🚀 Kế hoạch triển khai

### **Phase 1: Xử lý hàng loạt (Tuần này)**

1. ✅ Cấu trúc lại thư mục
2. ✅ Chạy batch_processor cho 34 files THONGBAO
3. ✅ Kiểm tra quality (sample 5-10 files)
4. ✅ Fix prompt nếu cần

**Script chính:**
```bash
python scripts/batch_process.py --input data/raw_pdfs/THONGBAO --output data/processed/json/THONGBAO
```

### **Phase 2: Migration vào Database (Tuần sau)**

1. ✅ Generate embeddings cho tất cả chunks
2. ✅ Load vào PostgreSQL
3. ✅ Verify data integrity
4. ✅ Test semantic search

**Script chính:**
```bash
python scripts/migrate_to_db.py --input data/processed/json/THONGBAO
```

### **Phase 3: Semantic Search API (2 tuần nữa)**

1. ✅ FastAPI endpoint
2. ✅ Query processing
3. ✅ Response formatting
4. ✅ Filtering by: cohort, ngành, loại CTDT

### **Phase 4: Frontend Integration (1 tháng nữa)**

1. ✅ Chat interface
2. ✅ Context-aware responses
3. ✅ Citation/source linking

---

## 🔧 Tech Stack

| Layer | Technology | Lý do |
|-------|-----------|-------|
| **Extraction** | Gemini 2.0 Flash | Structured output, hỗ trợ PDF tốt |
| **Validation** | Pydantic v2 | Type safety, schema validation |
| **Database** | PostgreSQL 16 | Reliable, mạnh mẽ |
| **Vector Store** | pgvector 0.8.1 | Tích hợp sẵn với PostgreSQL |
| **Embeddings** | Gemini Embedding | Miễn phí, chất lượng tốt |
| **API** | FastAPI | Async, type hints, auto docs |
| **Container** | Docker Compose | Easy deployment |

---

## 📈 Ước tính chi phí & Performance

### **Với 34 files THONGBAO:**
- **Gemini API calls**: ~34 uploads + 34 extractions = **FREE** (trong quota)
- **Storage**: ~34 JSON files × 50KB = **~1.7MB**
- **Database**: ~34 documents + ~500 chunks × 768D = **~5MB**
- **Processing time**: ~34 files × 30s/file = **~17 phút**

### **Scalability:**
- Có thể xử lý **1000+ files** mà không vấn đề
- pgvector HNSW index → sub-second search với 10K+ chunks

---

## ✅ Action Items (NGAY BÂY GIỜ)

1. **Cấu trúc lại thư mục** (5 phút)
2. **Update batch_processor.py** để lưu theo category (10 phút)
3. **Chạy batch processing cho THONGBAO** (20 phút)
4. **Kiểm tra 5 files ngẫu nhiên** (15 phút)

**Bạn muốn tôi làm ngay bước nào?** 🚀
