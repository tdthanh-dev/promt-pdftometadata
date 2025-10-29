import os
import json
import csv
import logging
import time
from datetime import date
from uuid import UUID, uuid4
from typing import List, Optional, Union

# Pydantic dùng để định nghĩa và xác thực schema
from pydantic import BaseModel, Field, ValidationError

# Google GenAI (sử dụng thư viện google-genai mới)
from google import genai
from google.genai import types

# .env
from dotenv import load_dotenv

# --- 1. CẤU HÌNH CƠ BẢN ---

# Cấu hình logging để xem thông báo tiến trình
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Tải biến môi trường từ file .env
load_dotenv()

# Lấy API key và cấu hình client
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    logging.error("Lỗi: Không tìm thấy GEMINI_API_KEY. Vui lòng tạo file .env và thêm key vào.")
    exit()

client = genai.Client(api_key=api_key)


# --- 2. ĐỊNH NGHĨA SCHEMA PYDANTIC (Sườn Metadata Hoàn Chỉnh) ---

class DocumentMetadata(BaseModel):
    """Metadata cho toàn bộ tài liệu."""
    DOC_ID: str = Field(default_factory=lambda: str(uuid4()), description="Mã định danh duy nhất của file.")
    FILE_NAME: Optional[str] = Field(default=None, description="Tên file gốc.")
    DOC_TITLE: Optional[str] = Field(default=None, description="Tiêu đề chính thức của văn bản.")
    DOC_TYPE: Optional[str] = Field(default=None, description="Loại văn bản (Quyết định, Quy chế, Thông báo...).")
    ISSUE_NUMBER: Optional[str] = Field(default=None, description="Số hiệu của văn bản.")
    ISSUING_AUTHORITY: Optional[str] = Field(default=None, description="Cơ quan/Người ban hành (Hiệu trưởng, Hội đồng Trường...).")
    ISSUING_DEPT: Optional[str] = Field(default=None, description="Phòng ban chịu trách nhiệm (Phòng Đào tạo, P. CT Sinh viên...).")
    ISSUE_DATE: Optional[date] = Field(default=None, description="Ngày ban hành chính thức (YYYY-MM-DD).")
    EFFECTIVE_DATE: Optional[str] = Field(default=None, description="Ngày văn bản bắt đầu có hiệu lực (YYYY-MM-DD hoặc 'Kể từ ngày ký').")
    EXPIRATION_DATE: Optional[date] = Field(default=None, description="Ngày văn bản hết hiệu lực (YYYY-MM-DD).")
    MAJOR_TOPIC: Optional[str] = Field(default=None, description="Chủ đề chính (Học vụ, Tài chính, Tuyển sinh...).")

class ChunkMetadata(BaseModel):
    """Metadata cho từng đoạn văn bản (chunk) được bóc tách."""
    CHUNK_ID: str = Field(default_factory=lambda: str(uuid4()), description="Mã định danh duy nhất của chunk.")
    PAGE_NUMBER: Optional[int] = Field(default=None, description="Số trang chứa chunk này.")
    SECTION_TITLE: Optional[str] = Field(default=None, description="Tiêu đề của mục/điều/khoản (VD: 'Điều 3', 'Khoản 2', 'Phụ lục', 'Căn cứ').")
    CHUNK_TOPIC: Optional[str] = Field(default=None, description="Chủ đề ngắn gọn của chunk (VD: 'Mức học phí Khóa 2025', 'Điều kiện miễn giảm', 'Thời hạn nộp hồ sơ'). KHÔNG trùng lặp với CONTENT_TYPE.")
    CONTENT_TYPE: Optional[str] = Field(default=None, description="Loại chương trình đào tạo (VD: 'Đại trà', 'Chất lượng cao', 'Liên kết quốc tế', 'Vừa học vừa làm'). CHỈ áp dụng cho văn bản về học phí/chương trình đào tạo.")
    SPECIFIC_TARGET: Optional[str] = Field(default=None, description="Chi tiết cụ thể của đối tượng áp dụng (VD: 'Học phần tiếng Anh', 'Học phần tiếng Việt', 'Ngành CNTT', 'Sinh viên chính quy').")
    APPLICABLE_COHORT: Optional[str] = Field(default=None, description="Khóa/đợt áp dụng (VD: 'Khóa 2024', 'Khóa 2023 trở về trước', 'Khóa 2024 và Khóa 2025', 'Tất cả khóa', 'Đợt 1 năm 2024-2025').")
    VALUE: Optional[Union[float, str]] = Field(default=None, description="Giá trị số liệu thuần túy (VD: 450000, 90, 30). Với học phí, chỉ ghi SỐ TIỀN, KHÔNG ghi đơn vị. Với điểm, chỉ ghi SỐ ĐIỂM.")
    UNIT: Optional[str] = Field(default=None, description="Đơn vị của VALUE (VD: 'Đ/tín chỉ', 'Đ/tháng', 'Điểm', 'Ngày', 'Tháng'). CHỈ điền khi có VALUE.")
    KEYWORDS: List[str] = Field(default_factory=list, description="Từ 3-8 từ khóa quan trọng (VD: ['học phí', 'khóa 2025', 'chất lượng cao']).")
    chunk_text: str = Field(description="Nội dung văn bản ĐẦY ĐỦ NGỮ CẢNH của chunk. PHẢI là câu văn hoàn chỉnh, CÓ THỂ đọc hiểu ĐỘC LẬP mà không cần xem các trường khác.")

class DocumentData(BaseModel):
    """Schema JSON đầu ra tổng thể mà AI phải tuân thủ."""
    document_metadata: DocumentMetadata
    chunk_metadata: List[ChunkMetadata]


# --- 3. PROMPT PHÂN TÍCH (Hoàn Chỉnh Nhất) ---

def get_full_analysis_prompt(file_name: str) -> str:
    """
    Tạo prompt phân tích chi tiết, tổng quát cho mọi loại tài liệu.
    """
    return f"""
Bạn là một hệ thống Trích xuất Dữ liệu (Data Extraction System). Nhiệm vụ của bạn là phân tích nội dung văn bản được cung cấp từ file PDF có tên '{file_name}' và trả về MỘT VÀ CHỈ MỘT đối tượng JSON hợp lệ.

## YÊU CẦU NGHIÊM NGẶT:

### 1. ĐỊNH DẠNG ĐẦU RA
* **CHỈ TRẢ VỀ JSON:** Không được chứa văn bản giải thích, không dùng markdown.
* **TUÂN THỦ SCHEMA:** JSON phải khớp chính xác với schema Pydantic `DocumentData`.

### 2. CHUNKING (CHIA ĐOẠN)
* **Bảng biểu:** MỖI DÒNG = MỘT CHUNK
* **Văn bản:** MỖI ĐIỀU/MỤC/ĐOẠN = MỘT CHUNK  
* **Thông báo ngắn:** CÓ THỂ LÀ MỘT CHUNK DUY NHẤT

### 3. ĐIỀN DỮ LIỆU - QUY TẮC CHI TIẾT

#### A. METADATA CƠ BẢN
* `FILE_NAME`: PHẢI là '{file_name}'
* `DOC_TYPE`: Quyết định/Thông báo/Quy chế/Hướng dẫn
* `MAJOR_TOPIC`: Học vụ/Tài chính/Tuyển sinh/KTX/HĐSV
* Dùng `null` nếu không tìm thấy (KHÔNG dùng chuỗi "null")

#### B. CHUNK METADATA - CÁC TRƯỜNG QUAN TRỌNG

**B1. SECTION_TITLE** (Tiêu đề mục)
* Ví dụ: "Điều 1", "Khoản 2", "Phụ lục", "Căn cứ"
* Lấy CHÍNH XÁC từ văn bản, không thêm bớt

**B2. CHUNK_TOPIC** (Chủ đề ngắn gọn)
* MỤC ĐÍCH: Xác định điểm khác biệt chính của chunk này so với các chunk khác
* GIỚI HẠN: 3-7 từ, ngắn gọn, súc tích
* **QUY TẮC BẮT BUỘC:**
  1. TUYỆT ĐỐI KHÔNG lặp lại thông tin đã có trong CONTENT_TYPE
  2. KHÔNG viết lại toàn bộ tên chương trình (đã có ở CONTENT_TYPE)
  3. TẬP TRUNG vào yếu tố PHÂN BIỆT: khóa học, đối tượng, thời gian, điều kiện
* **ĐỐI VỚI HỌC PHÍ - CÁCH VIẾT:**
  - Nếu chunk nói về học phí của một khóa cụ thể → Viết: "Mức học phí Khóa [X]"
  - Nếu chunk nói về học phần cụ thể → Viết: "Học phí học phần [tên học phần]"
  - Nếu chunk nói về điều kiện miễn giảm → Viết: "Điều kiện [loại miễn giảm]"
  - KHÔNG BAO GIỜ viết: "Mức học phí chương trình [tên chương trình]" vì tên chương trình đã ở CONTENT_TYPE
* **ĐỐI VỚI VĂN BẢN HÀNH CHÍNH:**
  - Căn cứ pháp lý → Viết: "Căn cứ [tên nghị định/quyết định ngắn gọn]"
  - Điều khoản → Viết: "[Nội dung chính của điều]"
  - Thời hạn → Viết: "Thời hạn [hành động]"

**B3. CONTENT_TYPE** (Loại chương trình)
* MỤC ĐÍCH: Phân loại chương trình đào tạo hoặc loại hình dịch vụ
* CHỈ áp dụng cho: Văn bản về HỌC PHÍ, CHƯƠNG TRÌNH ĐÀO TẠO
* CÁCH VIẾT: Ngắn gọn, KHÔNG thêm từ "Chương trình" phía trước
* CÁC GIÁ TRỊ HỢP LỆ:
  - "Đại trà" (không viết "Chương trình đại trà")
  - "Chất lượng cao" (không viết "Chương trình chất lượng cao")
  - "Hoàn toàn tiếng Anh" (không viết "Chương trình hoàn toàn tiếng Anh")
  - "Liên kết quốc tế"
  - "Vừa học vừa làm"
  - "Thạc sỹ"
  - "Tiến sỹ"
* Với văn bản KHÔNG liên quan học phí/đào tạo (thông báo, quy chế, hướng dẫn): Điền `null`

**B4. SPECIFIC_TARGET** (Đối tượng cụ thể)
* MỤC ĐÍCH: Chỉ rõ đối tượng áp dụng CHI TIẾT hơn CONTENT_TYPE
* CẤP ĐỘ: Chi tiết hơn một bước so với CONTENT_TYPE
* CÁCH SỬ DỤNG:
  - Nếu chunk phân biệt giữa các HỌC PHẦN trong cùng một chương trình → Ghi rõ tên học phần
    VD: "Học phần tiếng Anh", "Học phần tiếng Việt"
  - Nếu chunk chỉ áp dụng cho MỘT NGÀNH cụ thể → Ghi tên ngành
    VD: "Ngành Công nghệ thông tin", "Ngành Kế toán"
  - Nếu chunk áp dụng cho MỘT HÌNH THỨC cụ thể → Ghi hình thức
    VD: "Sinh viên chính quy", "Sinh viên tại chức"
* QUAN HỆ với CONTENT_TYPE:
  - CONTENT_TYPE: "Hoàn toàn tiếng Anh" → SPECIFIC_TARGET có thể là: "Học phần tiếng Anh" hoặc "Học phần tiếng Việt"
  - CONTENT_TYPE: "Đại trà" → SPECIFIC_TARGET thường là `null` (trừ khi có phân biệt ngành)
* Nếu chunk KHÔNG có phân biệt chi tiết → Điền `null`

**B5. APPLICABLE_COHORT** (Khóa áp dụng)
* MỤC ĐÍCH: Xác định khóa học hoặc đợt áp dụng chính sách
* **CÚ PHÁP BẮT BUỘC:**
  - Một khóa duy nhất: "Khóa [năm]" 
    VD: "Khóa 2024"
  - Hai hoặc nhiều khóa liệt kê: "Khóa [năm1] và Khóa [năm2]" (dùng "và", KHÔNG dùng dấu ";")
    VD: "Khóa 2024 và Khóa 2025"
  - Từ khóa X trở về trước: "Khóa [năm] trở về trước"
    VD: "Khóa 2023 trở về trước"
  - Từ khóa X trở về sau: "Khóa [năm] trở về sau"
    VD: "Khóa 2025 trở về sau"
  - Tất cả các khóa: "Tất cả khóa"
  - Đợt tuyển sinh: "Đợt [số] năm [năm]" hoặc "Khóa [mã khóa]"
    VD: "Đợt 1 năm 2024-2025", "Khóa 25.01"
* **SAI LẦM CẦN TRÁNH:**
  - KHÔNG dùng dấu chấm phẩy (;) để ngăn cách khóa
  - KHÔNG viết tắt: "K2024" → Phải viết đầy đủ: "Khóa 2024"
  - KHÔNG bỏ chữ "Khóa": "2024" → Phải viết: "Khóa 2024"
* Nếu chunk KHÔNG đề cập khóa cụ thể → Điền `null`

**B6. VALUE và UNIT** (Giá trị và đơn vị)
* MỤC ĐÍCH: Lưu trữ giá trị số liệu và đơn vị đo lường
* **QUY TẮC NGHIÊM NGẶT cho VALUE:**
  1. CHỈ GHI SỐ THUẦN TÚY, KHÔNG kèm đơn vị, KHÔNG có dấu phân cách
  2. Với học phí: Ghi số tiền nguyên (VD: 450000, KHÔNG: "450.000" hoặc "450000đ")
  3. Với điểm: Ghi số điểm (VD: 90, KHÔNG: "90 điểm")
  4. Với thời gian: Ghi số ngày/tháng (VD: 30, KHÔNG: "30 ngày")
  5. Cho phép: Số thực (VD: 3.5) hoặc chuỗi đặc biệt (VD: "Miễn phí")
* **QUY TẮC cho UNIT:**
  1. CHỈ điền khi có VALUE
  2. CÁC ĐƠN VỊ HỢP LỆ:
     - Tiền tệ: "Đ/tín chỉ", "Đ/tháng", "Đ/học kỳ", "Đ/năm"
     - Điểm: "Điểm"
     - Thời gian: "Ngày", "Tháng", "Tuần"
  3. Viết CHÍNH XÁC, phân biệt hoa/thường
* **LOGIC PHỐI HỢP:**
  - Nếu VALUE = `null` → UNIT PHẢI = `null`
  - Nếu VALUE có giá trị → UNIT PHẢI có đơn vị tương ứng
  - Nếu VALUE = "Miễn phí" → UNIT có thể = `null`

**B7. KEYWORDS** (Từ khóa)
* MỤC ĐÍCH: Hỗ trợ tìm kiếm và phân loại chunk
* SỐ LƯỢNG: Từ 3 đến 8 từ khóa
* NGUYÊN TẮC CHỌN:
  1. Chọn từ khóa QUAN TRỌNG NHẤT trong chunk
  2. Ưu tiên: Tên riêng, số liệu, thuật ngữ chuyên môn
  3. KHÔNG chọn: Từ quá chung chung (VD: "văn bản", "quy định")
  4. Bao gồm: Số hiệu văn bản, tên chương trình, khóa học, số tiền
* ĐỊNH DẠNG:
  - Viết thường toàn bộ
  - Mỗi từ khóa ngắn gọn (1-4 từ)
  - Không trùng lặp
* PHÂN BỐ:
  - 2-3 từ khóa về CHỦ ĐỀ CHÍNH
  - 1-2 từ khóa về ĐỐI TƯỢNG/KHÓA
  - 1-2 từ khóa về GIÁ TRỊ/SỐ LIỆU (nếu có)
  - 1-2 từ khóa về VĂN BẢN PHÁP LÝ (nếu có)

#### C. chunk_text - TRƯỜNG QUAN TRỌNG NHẤT ⭐

**VAI TRÒ QUYẾT ĐỊNH:** 
chunk_text là dữ liệu GỐC để tạo vector embedding cho semantic search. Nếu chunk_text kém chất lượng, toàn bộ hệ thống tìm kiếm sẽ SAI.

**NGUYÊN TẮC VÀNG - 3 PHẢI:**
1. **PHẢI ĐỘC LẬP:** Người đọc chunk_text PHẢI hiểu đầy đủ ý nghĩa MÀ KHÔNG CẦN xem bất kỳ trường metadata nào khác
2. **PHẢI HOÀN CHỈNH:** Câu văn phải có đầy đủ: CHỦ NGỮ + VỊ NGỮ + BỔ NGỮ + CÁC THÔNG TIN NGỮCẢNH cần thiết
3. **PHẢI RÕ RÀNG:** Mỗi thông tin quan trọng (chương trình, khóa, giá trị, điều kiện) phải được DIỄN ĐẠT TƯỜNG MINH

**CẤU TRÚC CÂU CHUẨN cho HỌC PHÍ:**
"Mức thu học phí [theo tín chỉ/theo tháng] cho [loại chương trình] [đối tượng cụ thể nếu có] dành cho [khóa/đợt] là [số tiền bằng chữ] đồng [đơn vị]."

**PHÂN TÍCH CẤU TRÚC:**
- Phần 1: "Mức thu học phí" → Chủ đề chính
- Phần 2: "[theo tín chỉ/theo tháng]" → Hình thức tính phí (nếu cần thiết)
- Phần 3: "cho [loại chương trình]" → VD: "cho chương trình đại trà", "cho chương trình chất lượng cao"
- Phần 4: "[đối tượng cụ thể]" → VD: "học phần tiếng Anh", "học phần tiếng Việt" (nếu có)
- Phần 5: "dành cho [khóa]" → VD: "dành cho sinh viên Khóa 2024 và Khóa 2025"
- Phần 6: "là [số tiền]" → VD: "là 450.000 đồng", "là 1.500.000 đồng"
- Phần 7: "[đơn vị]" → VD: "mỗi tín chỉ", "mỗi tháng"

**ĐIỀU TUYỆT ĐỐI CẤM:**
- KHÔNG viết chunk_text chỉ có giá trị đơn lẻ: "450.000đ", "400.000đ/tín chỉ"
- KHÔNG bỏ qua thông tin về khóa học
- KHÔNG bỏ qua thông tin về loại chương trình
- KHÔNG dùng đại từ không rõ nghĩa: "nó", "đó", "này"
- KHÔNG viết tắt: "SV" → Phải viết: "sinh viên"

**XỬ LÝ CÁC TRƯỜNG HỢP ĐẶC BIỆT:**
1. Nếu có phân biệt học phần (tiếng Anh/tiếng Việt):
   → PHẢI ghi rõ: "cho học phần tiếng Anh trong chương trình hoàn toàn tiếng Anh"
2. Nếu có nhiều khóa:
   → Liệt kê đầy đủ: "dành cho sinh viên Khóa 2024 và Khóa 2025"
3. Nếu là văn bản hành chính (Căn cứ, Điều khoản):
   → Copy NGUYÊN VĂN từ PDF, giữ nguyên dấu chấm phẩy cuối câu

### 4. TẦM QUAN TRỌNG
* chunk_text là trường QUAN TRỌNG NHẤT
* Nếu chunk_text ngắn/thiếu ngữ cảnh → Semantic search SẼ SAI
* Luôn viết câu ĐẦY ĐỦ, RÕ RÀNG, ĐỘC LẬP
"""


# --- 4. HÀM XỬ LÝ CHÍNH ---

def process_document(file_path: str) -> Optional[DocumentData]:
    """
    Thực hiện toàn bộ quy trình: Tải file, phân tích, xác thực và trả về dữ liệu.
    """
    if not os.path.exists(file_path):
        logging.error(f"Lỗi: File không tồn tại tại đường dẫn: {file_path}")
        return None

    file_name = os.path.basename(file_path)
    uploaded_file = None  # Khởi tạo để dùng trong khối 'finally'

    try:
        logging.info(f"Đang tải file lên: {file_name}...")
        uploaded_file = client.files.upload(file=file_path)
        
        logging.info("File đã sẵn sàng. Đang tạo prompt...")
        prompt = get_full_analysis_prompt(file_name)
        
        logging.info("Bắt đầu phân tích tài liệu (có thể mất vài giây)...")
        
        # Gửi yêu cầu phân tích - Sử dụng Gemini 2.5 Flash (model mạnh nhất)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=DocumentData, 
                temperature=0.1
            ),
        )
        
        logging.info("Phân tích hoàn tất. Đang xác thực (validate) schema Pydantic...")
        
        # Xác thực JSON trả về bằng schema Pydantic
        # Đây là bước quan trọng nhất để đảm bảo "chuẩn chỉ"
        data = DocumentData.model_validate_json(response.text)
        
        logging.info(f"Trích xuất thành công {len(data.chunk_metadata)} chunks.")
        
        # Tạo base filename (bỏ phần mở rộng .pdf)
        base_filename = os.path.splitext(file_name)[0]
        
        # Tạo thư mục output nếu chưa có
        json_dir = 'data/processed/json'
        csv_dir = 'data/processed/csv'
        os.makedirs(json_dir, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)
        
        # 1. Ghi kết quả ra file JSON
        json_output = os.path.join(json_dir, f'{base_filename}_output.json')
        with open(json_output, 'w', encoding='utf-8') as f:
            # Sử dụng model_dump_json để xuất chuẩn (xử lý UUID, date, v.v.)
            f.write(data.model_dump_json(indent=2, ensure_ascii=False))
        logging.info(f"✅ Đã lưu JSON vào: {json_output}")
        
        # 2. Ghi document metadata ra CSV
        doc_csv = os.path.join(csv_dir, f'{base_filename}_document.csv')
        with open(doc_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                'DOC_ID', 'FILE_NAME', 'DOC_TITLE', 'DOC_TYPE', 
                'ISSUE_NUMBER', 'ISSUING_AUTHORITY', 'ISSUING_DEPT',
                'ISSUE_DATE', 'EFFECTIVE_DATE', 'EXPIRATION_DATE', 'MAJOR_TOPIC'
            ])
            # Data row
            doc = data.document_metadata
            writer.writerow([
                doc.DOC_ID, doc.FILE_NAME, doc.DOC_TITLE, doc.DOC_TYPE,
                doc.ISSUE_NUMBER, doc.ISSUING_AUTHORITY, doc.ISSUING_DEPT,
                doc.ISSUE_DATE, doc.EFFECTIVE_DATE, doc.EXPIRATION_DATE, doc.MAJOR_TOPIC
            ])
        logging.info(f"✅ Đã lưu Document CSV vào: {doc_csv}")
        
        # 3. Ghi chunk metadata ra CSV
        chunks_csv = os.path.join(csv_dir, f'{base_filename}_chunks.csv')
        with open(chunks_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                'CHUNK_ID', 'PAGE_NUMBER', 'SECTION_TITLE', 'CHUNK_TOPIC',
                'CONTENT_TYPE', 'SPECIFIC_TARGET', 'APPLICABLE_COHORT',
                'VALUE', 'UNIT', 'KEYWORDS', 'chunk_text'
            ])
            # Data rows
            for chunk in data.chunk_metadata:
                writer.writerow([
                    chunk.CHUNK_ID, chunk.PAGE_NUMBER, chunk.SECTION_TITLE, chunk.CHUNK_TOPIC,
                    chunk.CONTENT_TYPE, chunk.SPECIFIC_TARGET, chunk.APPLICABLE_COHORT,
                    chunk.VALUE, chunk.UNIT, 
                    ', '.join(chunk.KEYWORDS) if chunk.KEYWORDS else '',
                    chunk.chunk_text
                ])
        logging.info(f"✅ Đã lưu Chunks CSV vào: {chunks_csv}")
        
        return data

    # Xử lý các lỗi có thể xảy ra
    except (ValidationError, json.JSONDecodeError) as e:
        logging.error(f"!!! Lỗi VALIDATE/JSON: Model đã trả về JSON không hợp lệ hoặc không khớp schema.")
        logging.error(f"Chi tiết lỗi: {e}")
        # In phản hồi thô để gỡ lỗi
        if 'response' in locals():
            logging.error(f"Phản hồi thô từ model: {response.text}")
        return None
    except Exception as e:
        logging.error(f"!!! Đã xảy ra lỗi không xác định: {e}")
        return None

    finally:
        # Quan trọng: Luôn xóa file đã tải lên máy chủ của Google sau khi hoàn tất
        # (kể cả khi bị lỗi) để tránh tốn dung lượng
        if uploaded_file:
            logging.info(f"Đang xóa file tạm trên server: {uploaded_file.name}")
            try:
                client.files.delete(name=uploaded_file.name)
                logging.info("Đã xóa file tạm.")
            except Exception as e:
                logging.warning(f"Không thể xóa file tạm {uploaded_file.name}. Lỗi: {e}")


# --- 5. ĐIỂM THỰC THI CHƯƠNG TRÌNH ---

if __name__ == '__main__':
    
    # === THAY TÊN FILE PDF CỦA BẠN VÀO ĐÂY ===
    PDF_FILE_TO_PROCESS = 'CTDT_CNTT_2024_K25.pdf'
    # Bạn có thể thử với các file khác như 'TB_DangKyHocPhan.pdf' v.v.
    # ========================================
    
    logging.info(f"--- BẮT ĐẦU XỬ LÝ FILE: {PDF_FILE_TO_PROCESS} ---")
    
    result_data = process_document(PDF_FILE_TO_PROCESS)
    
    if result_data:
        logging.info("\n--- XỬ LÝ HOÀN TẤT! XEM TRƯỚC 5 CHUNKS ĐẦU TIÊN ---")
        
        # In metadata tài liệu
        logging.info(f"\n[METADATA TÀI LIỆU]")
        logging.info(f"  Tiêu đề: {result_data.document_metadata.DOC_TITLE}")
        logging.info(f"  Loại VB: {result_data.document_metadata.DOC_TYPE}")
        logging.info(f"  Ngày BH: {result_data.document_metadata.ISSUE_DATE}")
        logging.info(f"  Chủ đề: {result_data.document_metadata.MAJOR_TOPIC}")
        
        # In 5 chunks đầu
        for i, chunk in enumerate(result_data.chunk_metadata[:5]):
            logging.info(f"\n[Chunk {i+1}] (ID: {chunk.CHUNK_ID})")
            logging.info(f"  Chủ đề: {chunk.CHUNK_TOPIC}")
            logging.info(f"  Đối tượng: {chunk.SPECIFIC_TARGET}")
            logging.info(f"  Giá trị: {chunk.VALUE} {chunk.UNIT or ''}")
            # Cắt ngắn text cho dễ đọc
            text_preview = chunk.chunk_text[:75].replace('\n', ' ')
            logging.info(f"  Text: {text_preview}...") 
    else:
        logging.warning("--- XỬ LÝ THẤT BẠI. Vui lòng kiểm tra log lỗi bên trên. ---")