import os
import json
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
    SECTION_TITLE: Optional[str] = Field(default=None, description="Tiêu đề của mục/điều/khoản (Điều 3, Khoản 2, Phụ lục...).")
    CHUNK_TOPIC: Optional[str] = Field(default=None, description="Chủ đề chi tiết của chunk (Điều kiện tốt nghiệp, Mức học phí K2025...).")
    CONTENT_TYPE: Optional[str] = Field(default=None, description="Loại hình đào tạo/dịch vụ (Đại trà, Chất lượng cao...).")
    SPECIFIC_TARGET: Optional[str] = Field(default=None, description="Đối tượng/Khóa học cụ thể (Khóa 2025, Ngành CNTT...).")
    APPLICABLE_COHORT: Optional[str] = Field(default=None, description="Khóa áp dụng (VD: 'Khóa 2024', 'Khóa 2023 trở về trước', 'Tất cả khóa').")
    VALUE: Optional[Union[float, str]] = Field(default=None, description="Giá trị số liệu (450000) hoặc text ('Miễn phí').")
    UNIT: Optional[str] = Field(default=None, description="Đơn vị của giá trị (Đ/tín chỉ, Ngày, Điểm...).")
    KEYWORDS: List[str] = Field(default_factory=list, description="Mảng các từ khóa liên quan đến chunk.")
    chunk_text: str = Field(description="Nội dung văn bản gốc của chính chunk này.")

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
    1.  **CHỈ TRẢ VỀ JSON:** Phản hồi của bạn không được chứa bất kỳ văn bản giải thích nào trước hoặc sau khối JSON. Không sử dụng markdown.
    2.  **TUÂN THỦ SCHEMA:** Đối tượng JSON phải tuân thủ nghiêm ngặt schema Pydantic `DocumentData` (bao gồm `document_metadata` và `chunk_metadata`) đã được định nghĩa.
    3.  **PHÂN TÍCH VÀ BÓC TÁCH (CHUNKING):**
        * Bạn phải tự động chia nội dung văn bản thành các đoạn (chunks) logic.
        * Mỗi chunk phải tương ứng với một mục thông tin có ý nghĩa.
        * **QUAN TRỌNG VỀ CHUNKING:**
            * **Đối với Bảng biểu** (học phí, chương trình đào tạo): MỖI DÒNG DỮ LIỆU có ý nghĩa trong bảng PHẢI LÀ MỘT CHUNK.
            * **Đối với Văn bản** (quy chế, thông báo): MỖI ĐIỀU KHOẢN, MỤC, hoặc ĐOẠN VĂN logic PHẢI LÀ MỘT CHUNK.
            * **Đối với Thông báo cực ngắn** (vài dòng): Toàn bộ nội dung thông báo CÓ THỂ LÀ MỘT CHUNK DUY NHẤT.
    4.  **ĐIỀN DỮ LIỆU (RẤT QUAN TRỌNG):**
        * Bạn phải điền giá trị cho tất cả các trường trong schema một cách tốt nhất có thể.
        * **BẮT BUỘC DÙNG `null`:** Nếu không tìm thấy thông tin cho một trường (ví dụ: thông báo ngắn không có `ISSUE_NUMBER`, hoặc chunk không có `VALUE` / `UNIT`), BẮT BUỘC phải sử dụng giá trị `null` (không phải chuỗi "null").
        * Trường `FILE_NAME` trong `document_metadata` phải là '{file_name}'.
        * Trường `chunk_text` phải là nội dung văn bản thô chính xác của chunk đó.
        * Cố gắng suy luận `DOC_TYPE` (Quyết định, Thông báo, Quy chế, Hướng dẫn, Chương trình đào tạo...) và `MAJOR_TOPIC` (Học vụ, Tài chính, Tuyển sinh, KTX, Hoạt động sinh viên...) dựa trên nội dung.
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
        
        # Ghi kết quả ra file JSON
        output_filename = 'output.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            # Sử dụng model_dump_json để xuất chuẩn (xử lý UUID, date, v.v.)
            f.write(data.model_dump_json(indent=2, ensure_ascii=False))
        logging.info(f"Đã lưu kết quả vào file: {output_filename}")
        
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
    PDF_FILE_TO_PROCESS = 'Du_khao_diem_ren_luyen_2024_2025.pdf'
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