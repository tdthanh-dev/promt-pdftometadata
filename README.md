# PDF to Metadata Extraction System

Hệ thống trích xuất metadata và nội dung có cấu trúc từ file PDF sử dụng Google Gemini AI.

## ✨ Tính năng

- 🤖 Sử dụng **Gemini 2.5 Flash** - Model AI mạnh nhất hiện tại
- 📄 Trích xuất metadata từ văn bản PDF (Quyết định, Thông báo, Quy chế...)
- 🎯 Schema validation với Pydantic v2
- 🔍 Phân tích chi tiết theo chunks (mỗi điều khoản, mỗi dòng bảng = 1 chunk)
- 🆔 Tự động tạo UUID có ý nghĩa cho documents và chunks
- 📊 Trích xuất thông tin: Học phí, Khóa áp dụng, Điểm rèn luyện...

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

```bash
pip install google-genai pydantic python-dotenv
```

## ⚙️ Cấu hình

Tạo file `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

## 🎯 Sử dụng

```python
python main.py
```

Chỉnh sửa tên file PDF trong `main.py`:
```python
PDF_FILE_TO_PROCESS = 'your_file.pdf'
```

## 📁 Files

- `main.py` - Script chính để xử lý PDF
- `check_models.py` - Kiểm tra models có sẵn với API key
- `output.json` - Kết quả trích xuất (tự động tạo)

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
