import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions

# Cấu hình logging cơ bản
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_available_models():
    """
    Tải API key, kết nối đến Google và liệt kê các model có thể sử dụng.
    """
    try:
        # 1. Tải key từ file .env
        load_dotenv()
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            logging.error("Không tìm thấy GEMINI_API_KEY trong file .env")
            return

        # 2. Cấu hình API key
        genai.configure(api_key=api_key)

        logging.info("Đã cấu hình API key. Đang lấy danh sách models...")
        
        # 3. Lấy danh sách tất cả models
        usable_models = []
        for model in genai.list_models():
            # 4. Kiểm tra xem model có hỗ trợ phương thức 'generateContent' không
            # (Một số model chỉ dùng để embedding, ví dụ 'text-embedding-004')
            if 'generateContent' in model.supported_generation_methods:
                usable_models.append((model.name, model.display_name))

        # 5. In kết quả
        if not usable_models:
            logging.warning("Không tìm thấy model nào có thể generateContent với key này.")
            return

        logging.info("--- CÁC MODEL CÓ THỂ SỬ DỤNG (generateContent) ---")
        for name, display_name in usable_models:
            logging.info(f"- Tên API (name): {name}")
            logging.info(f"  Tên hiển thị (display_name): {display_name}\n")
        
        logging.info(f"Tổng cộng: {len(usable_models)} models khả dụng.")

    except google_exceptions.PermissionDenied as e:
        logging.error(f"LỖI XÁC THỰC: API key không hợp lệ hoặc không có quyền.")
        logging.error(f"Chi tiết: {e}")
    except Exception as e:
        logging.error(f"Đã xảy ra lỗi không xác định: {e}")

if __name__ == "__main__":
    check_available_models()