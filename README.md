# PDF to Metadata Extraction System

Hệ thống trích xuất metadata và nội dung có cấu trúc từ file PDF sử dụng Google Gemini AI + PostgreSQL pgvector.

## ✨ Tính năng

- 🤖 Sử dụng **Gemini 2.5 Flash** - Model AI mạnh nhất hiện tại
- 📄 Trích xuất metadata từ văn bản PDF (Quyết định, Thông báo, Quy chế...)
- 🎯 Schema validation với Pydantic v2
- 🔍 Phân tích chi tiết theo chunks (mỗi điều khoản, mỗi dòng bảng = 1 chunk)
- 🆔 Tự động tạo UUID có ý nghĩa cho documents và chunks
- 📊 Trích xuất thông tin: Học phí, Khóa áp dụng, Điểm rèn luyện...
- 🐘 **PostgreSQL + pgvector** cho vector similarity search
- 🔎 **Semantic search** với embeddings (768 dimensions)
- 💾 Lưu trữ persistent với Docker volume

## 🚀 Schema Metadata

### Document Metadata
- DOC_ID, FILE_NAME, DOC_TITLE
- DOC_TYPE, ISSUE_NUMBER, ISSUE_DATE
- ISSUING_AUTHORITY, ISSUING_DEPT
- EFFECTIVE_DATE, EXPIRATION_DATE
- MAJOR_TOPIC

### Chunk Metadata
- CHUNK_ID, PAGE_NUMBER, SECTION_TITLE
- CHUNK_TOPIC, CONTENT_TYPE
- SPECIFIC_TARGET, APPLICABLE_COHORT
- VALUE, UNIT, KEYWORDS
- chunk_text

## 📦 Cài đặt

### Option 1: Sử dụng Docker (Khuyến nghị)

```bash
# Clone repository
git clone https://github.com/tdthanh-dev/promt-pdftometadata.git
cd promt-pdftometadata

# Khởi động PostgreSQL với pgvector
docker-compose up -d

# Cài đặt Python dependencies
pip install -r requirements.txt

# Cấu hình environment
cp .env.example .env
# Sửa .env với GEMINI_API_KEY của bạn
```

📖 **Xem chi tiết:** [DOCKER_SETUP.md](DOCKER_SETUP.md)

### Option 2: Manual Installation

```bash
pip install google-genai pydantic python-dotenv psycopg2-binary
```

## ⚙️ Cấu hình

Tạo file `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

## 🎯 Sử dụng

### 1. Trích xuất PDF
```python
python main.py
```

Chỉnh sửa tên file PDF trong `main.py`:
```python
PDF_FILE_TO_PROCESS = 'your_file.pdf'
```

### 2. Lưu vào PostgreSQL với embeddings
```python
from pgvector_storage import PgVectorStorage
import json

storage = PgVectorStorage()

# Load từ output.json
with open('output.json', 'r', encoding='utf-8') as f:
    doc_data = json.load(f)
    storage.save_document(doc_data)
```

### 3. Tìm kiếm semantic
```python
# Tìm kiếm theo ngữ nghĩa
results = storage.semantic_search(
    query="học phí chương trình tiên tiến khóa 2024",
    limit=5
)

for result in results:
    print(f"{result['chunk_topic']}: {result['chunk_text']}")
    print(f"Similarity: {result['similarity']:.4f}\n")
```

## 📁 Files

- `main.py` - Script chính để xử lý PDF
- `pgvector_storage.py` - PostgreSQL + pgvector storage & search
- `check_models.py` - Kiểm tra models có sẵn với API key
- `docker-compose.yml` - Docker setup cho PostgreSQL
- `init.sql` - Database schema với pgvector
- `output.json` - Kết quả trích xuất (tự động tạo)
- `DOCKER_SETUP.md` - Hướng dẫn chi tiết Docker

## 🎨 Ví dụ Output

```json
{
  "document_metadata": {
    "DOC_ID": "DRL_2024_2025_TB_001",
    "DOC_TITLE": "Về việc công bố dự thảo...",
    "DOC_TYPE": "THÔNG BÁO",
    "ISSUE_DATE": "2025-10-13"
  },
  "chunk_metadata": [
    {
      "CHUNK_ID": "DRL_2024_2025_TB_001_CHUNK_001",
      "CHUNK_TOPIC": "Căn cứ và mục đích thông báo",
      "APPLICABLE_COHORT": "Năm học 2024 - 2025",
      "chunk_text": "..."
    }
  ]
}
```

## 🔥 Model Support

Hỗ trợ các Gemini models:
- ⭐ **gemini-2.5-flash** (Khuyến nghị - đang dùng)
- 💎 gemini-2.5-pro
- ⚡ gemini-2.0-flash-exp

## 📄 License

MIT

## 👨‍💻 Author

Created with ❤️ using Google Gemini AI
