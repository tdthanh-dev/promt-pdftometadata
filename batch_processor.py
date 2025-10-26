import os
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Tải biến môi trường
load_dotenv()

# Khởi tạo client
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# --- Schema Pydantic ---
class ThongBaoData(BaseModel):
    """Cấu trúc dữ liệu cho một Thông Báo cần lưu vào DB."""
    file_name: str = Field(description="Tên file gốc.")
    tieu_de: str = Field(description="Tiêu đề đầy đủ của thông báo.")
    ngay_ban_hanh: str = Field(description="Ngày ban hành, định dạng YYYY-MM-DD.")
    don_vi_ban_hanh: str = Field(description="Tên đơn vị hoặc tổ chức ban hành thông báo.")
    trich_yeu: str = Field(description="Tóm tắt nội dung chính yếu không quá 30 từ.")
    noi_dung_quan_trong: list[str] = Field(description="Các điểm hoặc điều khoản quan trọng nhất, dưới dạng danh sách.")
    noi_dung_thuan_text: str = Field(description="Toàn bộ nội dung thông báo được chuyển đổi sang dạng văn bản thuần.")


# --- Xử lý 1 file ---
def process_single_file(file_path: str) -> dict:
    """Xử lý 1 file PDF/DOCX và trả về dữ liệu đã trích xuất."""
    
    file_name = os.path.basename(file_path)
    print(f"\n{'='*70}")
    print(f"📄 Đang xử lý: {file_name}")
    print(f"{'='*70}")
    
    uploaded_file = None
    try:
        # Upload file
        print(f"🔄 Đang tải file lên...")
        uploaded_file = client.files.upload(file=file_path)
        print(f"✅ Đã tải lên: {uploaded_file.name}")
        
        # Trích xuất dữ liệu
        prompt = (
            "Bạn là chuyên gia phân tích tài liệu hành chính Việt Nam.\n\n"
            "YÊU CẦU:\n"
            "1. Đọc kỹ toàn bộ tài liệu được cung cấp\n"
            "2. Trích xuất chính xác các trường thông tin theo schema\n"
            "3. Đảm bảo ngày ban hành đúng định dạng YYYY-MM-DD\n"
            "4. Trich yếu phải súc tích, không quá 30 từ\n"
            "5. Nội dung quan trọng là các điều khoản, quy định chính\n"
            "6. Chuyển toàn bộ nội dung sang văn bản thuần, loại bỏ ký tự đặc biệt\n\n"
            "LƯU Ý: Phải chính xác 100%, không thêm thắt hoặc bịa đặt thông tin."
        )
        
        print(f"🤖 Đang phân tích với Gemini AI...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, uploaded_file],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ThongBaoData,
                temperature=0.1,  # Độ sáng tạo thấp = chính xác cao
            ),
        )
        
        # Parse JSON
        extracted_data = ThongBaoData.model_validate_json(response.text)
        data_dict = extracted_data.model_dump()
        
        # Thêm file_name
        data_dict['file_name'] = file_name
        
        # Tạo embedding
        print(f"🗺️ Đang tạo vector embedding...")
        embed_response = client.models.embed_content(
            model='text-embedding-004',
            contents=data_dict['noi_dung_thuan_text'],
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        data_dict['vector_data'] = embed_response.embeddings[0].values
        
        # Metadata
        data_dict['processed_at'] = datetime.now().isoformat()
        data_dict['model_used'] = 'gemini-2.5-flash'
        
        print(f"✅ Hoàn tất xử lý: {file_name}")
        return data_dict
        
    except Exception as e:
        print(f"❌ Lỗi khi xử lý {file_name}: {e}")
        return None
        
    finally:
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
                print(f"🗑️ Đã xóa file tạm")
            except:
                pass


# --- CÁCH 1: Lưu từng file riêng biệt ---
def save_individual_files(results: list, output_dir: str = "extracted_data"):
    """Lưu mỗi document thành 1 file JSON riêng."""
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"💾 CÁCH 1: Lưu từng file riêng biệt")
    print(f"{'='*70}")
    
    for data in results:
        if data is None:
            continue
            
        # Tạo tên file output từ file gốc
        original_name = Path(data['file_name']).stem
        output_file = os.path.join(output_dir, f"{original_name}_data.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Đã lưu: {output_file}")
    
    print(f"\n📁 Tổng cộng: {len([d for d in results if d])} files")


# --- CÁCH 2: Lưu tất cả vào 1 file JSON duy nhất ---
def save_single_json(results: list, output_file: str = "all_documents.json"):
    """Lưu tất cả documents vào 1 file JSON."""
    
    print(f"\n{'='*70}")
    print(f"💾 CÁCH 2: Lưu tất cả vào 1 file JSON")
    print(f"{'='*70}")
    
    # Lọc bỏ None
    valid_results = [r for r in results if r is not None]
    
    output_data = {
        "metadata": {
            "total_documents": len(valid_results),
            "processed_at": datetime.now().isoformat(),
            "model_used": "gemini-2.5-flash"
        },
        "documents": valid_results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Đã lưu: {output_file}")
    print(f"📊 Tổng số documents: {len(valid_results)}")
    file_size = os.path.getsize(output_file) / 1024  # KB
    print(f"📦 Kích thước file: {file_size:.2f} KB")


# --- CÁCH 3: Lưu theo cấu trúc phân cấp (theo thời gian/loại) ---
def save_hierarchical(results: list, base_dir: str = "data_hierarchy"):
    """Lưu theo cấu trúc thư mục phân cấp (theo năm/tháng/loại)."""
    
    print(f"\n{'='*70}")
    print(f"💾 CÁCH 3: Lưu theo cấu trúc phân cấp")
    print(f"{'='*70}")
    
    for data in results:
        if data is None:
            continue
        
        try:
            # Parse ngày ban hành
            ngay_ban_hanh = data.get('ngay_ban_hanh', '2025-01-01')
            year = ngay_ban_hanh.split('-')[0]
            month = ngay_ban_hanh.split('-')[1]
            
            # Xác định loại document (dựa vào từ khóa trong tiêu đề)
            tieu_de = data.get('tieu_de', '').lower()
            if 'học phí' in tieu_de or 'hoc phi' in tieu_de:
                doc_type = 'hoc_phi'
            elif 'thông báo' in tieu_de or 'thong bao' in tieu_de:
                doc_type = 'thong_bao'
            elif 'quyết định' in tieu_de or 'quyet dinh' in tieu_de:
                doc_type = 'quyet_dinh'
            else:
                doc_type = 'khac'
            
            # Tạo cấu trúc thư mục: base_dir/năm/tháng/loại/
            dir_path = os.path.join(base_dir, year, month, doc_type)
            os.makedirs(dir_path, exist_ok=True)
            
            # Tạo tên file
            original_name = Path(data['file_name']).stem
            output_file = os.path.join(dir_path, f"{original_name}.json")
            
            # Lưu file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Đã lưu: {output_file}")
            
        except Exception as e:
            print(f"⚠️ Lỗi khi lưu {data.get('file_name', 'unknown')}: {e}")
    
    print(f"\n📂 Cấu trúc thư mục đã tạo:")
    print(f"   {base_dir}/")
    print(f"   ├── 2025/")
    print(f"   │   ├── 01/")
    print(f"   │   │   ├── hoc_phi/")
    print(f"   │   │   ├── thong_bao/")
    print(f"   │   │   └── quyet_dinh/")


# --- CÁCH 4: Lưu vào SQLite Database ---
def save_to_sqlite(results: list, db_file: str = "documents.db"):
    """Lưu vào SQLite database."""
    import sqlite3
    
    print(f"\n{'='*70}")
    print(f"💾 CÁCH 4: Lưu vào SQLite Database")
    print(f"{'='*70}")
    
    # Tạo database và bảng
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS thong_bao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            tieu_de TEXT,
            ngay_ban_hanh TEXT,
            don_vi_ban_hanh TEXT,
            trich_yeu TEXT,
            noi_dung_quan_trong TEXT,
            noi_dung_thuan_text TEXT,
            vector_data TEXT,
            processed_at TEXT,
            model_used TEXT
        )
    ''')
    
    # Insert dữ liệu
    count = 0
    for data in results:
        if data is None:
            continue
        
        cursor.execute('''
            INSERT INTO thong_bao (
                file_name, tieu_de, ngay_ban_hanh, don_vi_ban_hanh,
                trich_yeu, noi_dung_quan_trong, noi_dung_thuan_text,
                vector_data, processed_at, model_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('file_name'),
            data.get('tieu_de'),
            data.get('ngay_ban_hanh'),
            data.get('don_vi_ban_hanh'),
            data.get('trich_yeu'),
            json.dumps(data.get('noi_dung_quan_trong', []), ensure_ascii=False),
            data.get('noi_dung_thuan_text'),
            json.dumps(data.get('vector_data', []), ensure_ascii=False),
            data.get('processed_at'),
            data.get('model_used')
        ))
        count += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Đã lưu {count} documents vào database: {db_file}")
    print(f"📊 Bảng: thong_bao")


# --- Main Function ---
def batch_process_documents(input_dir: str = ".", file_pattern: str = "*.pdf"):
    """Xử lý hàng loạt các file PDF/DOCX."""
    
    print("="*70)
    print("🚀 BẮT ĐẦU XỬ LÝ HÀNG LOẠT TÀI LIỆU")
    print("="*70)
    
    # Tìm tất cả file PDF
    pdf_files = list(Path(input_dir).glob(file_pattern))
    
    if not pdf_files:
        print(f"⚠️ Không tìm thấy file {file_pattern} trong thư mục {input_dir}")
        return
    
    print(f"\n📁 Tìm thấy {len(pdf_files)} files:")
    for i, f in enumerate(pdf_files, 1):
        print(f"   {i}. {f.name}")
    
    # Xử lý từng file
    results = []
    for file_path in pdf_files:
        result = process_single_file(str(file_path))
        results.append(result)
    
    # Thống kê
    successful = len([r for r in results if r is not None])
    failed = len([r for r in results if r is None])
    
    print(f"\n{'='*70}")
    print(f"📊 THỐNG KÊ")
    print(f"{'='*70}")
    print(f"✅ Thành công: {successful}/{len(results)}")
    print(f"❌ Thất bại: {failed}/{len(results)}")
    
    if successful == 0:
        print("\n⚠️ Không có dữ liệu để lưu!")
        return
    
    # Lưu dữ liệu
    print(f"\n{'='*70}")
    print(f"💾 LƯU TRỮ DỮ LIỆU")
    print(f"{'='*70}")
    
    # LƯU VÀO SQLite (CHÍNH)
    save_to_sqlite(results, "output/documents.db")
    
    # BACKUP VÀO JSON
    save_single_json(results, "output/all_documents.json")
    
    print(f"\n{'='*70}")
    print(f"🎉 HOÀN TẤT!")
    print(f"{'='*70}")
    print(f"\n📂 Dữ liệu đã được lưu:")
    print(f"   🗄️ SQLite (chính): output/documents.db")
    print(f"   💾 JSON (backup): output/all_documents.json")
    print(f"\n💡 SỬ DỤNG:")
    print(f"   python chatbot_storage.py        # Demo query & search")
    print(f"   python demo_storage_query.py     # Xem chi tiết query")


if __name__ == "__main__":
    # Xử lý tất cả file PDF trong thư mục hiện tại
    batch_process_documents(input_dir=".", file_pattern="*.pdf")
