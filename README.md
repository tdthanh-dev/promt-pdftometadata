# 🤖 ChatBot - Trợ lý học vụ tự động

Hệ thống trích xuất metadata từ tài liệu PDF học vụ và xây dựng chatbot hỗ trợ sinh viên tra cứu thông tin thông qua semantic search.

## 📋 Tổng quan

- **Input**: PDF files (Thông báo CTDT, Quy định học phí, Quy chế đào tạo, ...)
- **Processing**: Gemini 2.0 Flash với Structured Output
- **Storage**: PostgreSQL + pgvector (768-dimensional embeddings)
- **Search**: Vector similarity search với HNSW index

## 🗂️ Cấu trúc dự án

```
ChatBot/
├── data/                          # Data directory (không commit lên Git)
│   ├── raw_pdfs/                  # PDF files gốc
│   │   └── THONGBAO/              # 34 files CTDT các khóa, ngành
│   ├── processed/                 # Kết quả xử lý
│   │   ├── json/                  # Structured metadata
│   │   └── csv/                   # Human-readable format
│   └── logs/                      # Processing logs
│
├── src/                           # Source code
│   ├── extractors/                # PDF extraction logic
│   ├── pgvector_storage.py        # PostgreSQL + pgvector storage
│   └── chatbot_storage.py         # Legacy storage (deprecated)
│
├── scripts/                       # Utility scripts
│   └── batch_process.py           # Batch processing for multiple PDFs
│
├── main.py                        # Single file processor
├── docker-compose.yml             # PostgreSQL + pgvector setup
├── init.sql                       # Database schema
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (API keys)
└── ARCHITECTURE.md                # Detailed architecture docs
```

## 🚀 Quick Start

### 1️⃣ Setup môi trường

```bash
# Clone repository
git clone https://github.com/tdthanh-dev/promt-pdftometadata.git
cd ChatBot

# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### 2️⃣ Khởi động Database

```bash
# Start PostgreSQL + pgvector
docker-compose up -d

# Verify database
docker ps
docker exec chatbot_pgvector psql -U chatbot_user -d chatbot_db -c "\dt"
```

### 3️⃣ Xử lý PDF files

**Option A: Xử lý 1 file**
```bash
python main.py
# Nhập đường dẫn PDF khi được hỏi
```

**Option B: Xử lý hàng loạt (Recommended)**
```bash
# Xử lý toàn bộ THONGBAO folder (34 files)
python scripts/batch_process.py --input data/raw_pdfs/THONGBAO --output data/processed

# Xử lý 5 files đầu tiên (để test)
python scripts/batch_process.py --input data/raw_pdfs/THONGBAO --output data/processed --limit 5

# Reprocess tất cả (overwrite)
python scripts/batch_process.py --input data/raw_pdfs/THONGBAO --output data/processed --no-skip
```

### 4️⃣ Load vào Database

```bash
# TODO: Script đang phát triển
python scripts/migrate_to_db.py --input data/processed/json
```

### 5️⃣ Test Semantic Search

```bash
# TODO: API đang phát triển
python scripts/test_search.py --query "Học phí khóa 2025"
```

## 📊 Database Schema

### Table: `documents`
Lưu metadata cấp tài liệu

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `doc_id` | VARCHAR(100) | Unique document ID |
| `file_name` | VARCHAR(255) | Original filename |
| `doc_title` | TEXT | Document title |
| `doc_type` | VARCHAR(50) | "Thông báo", "Quy định", ... |
| `issue_number` | VARCHAR(100) | Số hiệu văn bản |
| `issuing_authority` | VARCHAR(255) | Cơ quan ban hành |
| `issue_date` | DATE | Ngày ban hành |
| `major_topic` | VARCHAR(100) | Chủ đề chính |

### Table: `chunks`
Lưu metadata cấp đoạn văn + vector embeddings

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `chunk_id` | VARCHAR(150) | Unique chunk ID |
| `doc_id` | VARCHAR(100) | Foreign key → documents |
| `page_number` | INTEGER | Số trang |
| `chunk_topic` | VARCHAR(255) | Chủ đề đoạn văn |
| `content_type` | VARCHAR(100) | "Đại trà", "CLCQ", ... |
| `applicable_cohort` | VARCHAR(100) | "Khóa 2024", "Khóa 2025" |
| `chunk_text` | TEXT | Nội dung đầy đủ |
| `embedding` | vector(768) | Vector embedding |

## 🔧 Configuration

### Environment Variables (`.env`)

```env
# Gemini API
GEMINI_API_KEY=your_gemini_api_key

# PostgreSQL
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=Thanh1410@
POSTGRES_DB=chatbot_db
POSTGRES_PORT=5433
```

### Docker Compose

```yaml
services:
  pgvector:
    image: pgvector/pgvector:pg16
    container_name: chatbot_pgvector
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: chatbot_user
      POSTGRES_PASSWORD: Thanh1410@
      POSTGRES_DB: chatbot_db
    volumes:
      - pgvector_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
```

## 📈 Processing Stats

### THONGBAO Folder (34 files CTDT)

- **Total files**: 34 PDFs
- **Estimated time**: ~17 phút (30s/file)
- **Output size**: 
  - JSON: ~1.7 MB
  - Database: ~5 MB (with embeddings)
- **Chunks**: ~500-1000 chunks tổng cộng

## 🛠️ Development

### Thêm PDF mới

```bash
# 1. Copy PDF vào thư mục phù hợp
cp new_document.pdf data/raw_pdfs/QUY_DINH/

# 2. Chạy batch processor
python scripts/batch_process.py --input data/raw_pdfs/QUY_DINH --output data/processed

# 3. Load vào database
python scripts/migrate_to_db.py --input data/processed/json/new_document_output.json
```

### Update Schema

```bash
# 1. Sửa file init.sql
# 2. Restart database
docker-compose down
docker-compose up -d
```

## 📝 Logs

Logs được lưu tại `data/logs/batch_YYYYMMDD_HHMMSS.log`

```bash
# Xem log mới nhất
Get-ChildItem data/logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

## 🐛 Troubleshooting

### Database connection failed

```bash
# Check container status
docker ps

# Check logs
docker logs chatbot_pgvector

# Restart container
docker-compose restart
```

### PDF extraction failed

```bash
# Check API key
cat .env | grep GEMINI_API_KEY

# Check file encoding
file data/raw_pdfs/THONGBAO/filename.pdf

# Test with single file
python main.py
```

## 📚 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed architecture & design decisions
- [docker-compose.yml](docker-compose.yml) - Infrastructure setup
- [init.sql](init.sql) - Database schema

## 🤝 Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Submit Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

## 👥 Authors

- **tdthanh-dev** - Initial work - [GitHub](https://github.com/tdthanh-dev)

## 🙏 Acknowledgments

- Gemini 2.0 Flash for structured PDF extraction
- pgvector for efficient vector similarity search
- PostgreSQL for reliable data storage
