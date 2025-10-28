"""
Chatbot Storage Manager - Quản lý lưu trữ dữ liệu cho chatbot
Sử dụng SQLite làm chính + JSON backup
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class ChatbotStorage:
    """Quản lý storage cho chatbot - SQLite + JSON backup"""
    
    def __init__(self, db_path='output/documents.db', 
                 json_backup='output/all_documents.json'):
        self.db_path = db_path
        self.json_backup = json_backup
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Đảm bảo database và bảng tồn tại"""
        if not Path(self.db_path).exists():
            print(f"⚠️ Database chưa tồn tại: {self.db_path}")
            print(f"   Chạy: python batch_processor.py để tạo dữ liệu")
    
    # ========== QUERY & SEARCH ==========
    
    def search_by_keyword(self, keyword):
        """Tìm kiếm văn bản theo từ khóa trong tiêu đề hoặc trích yếu"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, trich_yeu, ngay_ban_hanh, don_vi_ban_hanh
            FROM thong_bao 
            WHERE tieu_de LIKE ? OR trich_yeu LIKE ?
            ORDER BY ngay_ban_hanh DESC
        """, (f'%{keyword}%', f'%{keyword}%'))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def search_full_text(self, keyword):
        """Tìm kiếm trong toàn bộ nội dung văn bản"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, ngay_ban_hanh
            FROM thong_bao 
            WHERE noi_dung_thuan_text LIKE ?
            ORDER BY ngay_ban_hanh DESC
        """, (f'%{keyword}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_by_date_range(self, start_date, end_date):
        """Lấy văn bản theo khoảng thời gian"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, ngay_ban_hanh, don_vi_ban_hanh
            FROM thong_bao 
            WHERE ngay_ban_hanh BETWEEN ? AND ?
            ORDER BY ngay_ban_hanh DESC
        """, (start_date, end_date))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_by_unit(self, don_vi):
        """Lấy văn bản theo đơn vị ban hành"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, ngay_ban_hanh
            FROM thong_bao 
            WHERE don_vi_ban_hanh LIKE ?
            ORDER BY ngay_ban_hanh DESC
        """, (f'%{don_vi}%',))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_document_by_id(self, doc_id):
        """Lấy chi tiết văn bản theo ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM thong_bao WHERE id = ?", (doc_id,))
        result = cursor.fetchone()
        
        if result:
            columns = [desc[0] for desc in cursor.description]
            doc = dict(zip(columns, result))
            
            # Parse JSON fields
            if doc.get('noi_dung_quan_trong'):
                doc['noi_dung_quan_trong'] = json.loads(doc['noi_dung_quan_trong'])
        else:
            doc = None
        
        conn.close()
        return doc
    
    # ========== STATISTICS ==========
    
    def get_statistics(self):
        """Thống kê tổng quan"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tổng số văn bản
        cursor.execute("SELECT COUNT(*) FROM thong_bao")
        total = cursor.fetchone()[0]
        
        # Theo đơn vị
        cursor.execute("""
            SELECT don_vi_ban_hanh, COUNT(*) as count
            FROM thong_bao 
            GROUP BY don_vi_ban_hanh
            ORDER BY count DESC
        """)
        by_unit = cursor.fetchall()
        
        # Theo năm
        cursor.execute("""
            SELECT substr(ngay_ban_hanh, 1, 4) as year, COUNT(*) as count
            FROM thong_bao 
            GROUP BY year
            ORDER BY year DESC
        """)
        by_year = cursor.fetchall()
        
        conn.close()
        
        return {
            'total': total,
            'by_unit': by_unit,
            'by_year': by_year
        }
    
    def get_recent_documents(self, limit=10):
        """Lấy các văn bản mới nhất"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, ngay_ban_hanh
            FROM thong_bao 
            ORDER BY ngay_ban_hanh DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    # ========== BACKUP & EXPORT ==========
    
    def backup_to_json(self):
        """Backup SQLite sang JSON"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM thong_bao")
        rows = cursor.fetchall()
        
        # Chuyển sang dict
        documents = []
        columns = [desc[0] for desc in cursor.description]
        
        for row in rows:
            doc = dict(zip(columns, row))
            # Parse JSON strings
            if doc.get('noi_dung_quan_trong'):
                try:
                    doc['noi_dung_quan_trong'] = json.loads(doc['noi_dung_quan_trong'])
                except:
                    pass
            # Không lưu vector_data vào JSON (quá lớn)
            doc.pop('vector_data', None)
            documents.append(doc)
        
        # Lưu JSON
        output = {
            'metadata': {
                'total_documents': len(documents),
                'backup_at': datetime.now().isoformat(),
                'source': 'SQLite database'
            },
            'documents': documents
        }
        
        with open(self.json_backup, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        conn.close()
        
        file_size = Path(self.json_backup).stat().st_size / 1024  # KB
        print(f"✅ Đã backup {len(documents)} documents sang {self.json_backup}")
        print(f"📦 Kích thước: {file_size:.2f} KB")
        
        return len(documents)
    
    def export_to_csv(self, output_file='output/documents.csv'):
        """Export dữ liệu ra CSV"""
        import csv
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, tieu_de, ngay_ban_hanh, 
                   don_vi_ban_hanh, trich_yeu
            FROM thong_bao
        """)
        
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        
        conn.close()
        print(f"✅ Đã export {len(rows)} documents sang {output_file}")


# ========== DEMO USAGE ==========

def demo_search():
    """Demo tìm kiếm"""
    storage = ChatbotStorage()
    
    print("="*70)
    print("🔍 DEMO TÌM KIẾM")
    print("="*70)
    
    # 1. Tìm theo từ khóa
    print("\n📌 Tìm kiếm: 'học phí'")
    results = storage.search_by_keyword('học phí')
    
    if results:
        for r in results:
            print(f"\n   ID: {r[0]}")
            print(f"   📄 Tiêu đề: {r[2][:70]}...")
            print(f"   📅 Ngày: {r[4]}")
            print(f"   🏢 Đơn vị: {r[5]}")
    else:
        print("   ❌ Không tìm thấy kết quả")
    
    # 2. Tìm theo khoảng thời gian
    print(f"\n📌 Văn bản từ 2025-01-01 đến 2025-12-31:")
    results = storage.get_by_date_range('2025-01-01', '2025-12-31')
    print(f"   Tìm thấy: {len(results)} kết quả")
    
    # 3. Văn bản mới nhất
    print(f"\n📌 5 văn bản mới nhất:")
    results = storage.get_recent_documents(5)
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r[2][:60]}... ({r[3]})")


def demo_statistics():
    """Demo thống kê"""
    storage = ChatbotStorage()
    
    print("\n" + "="*70)
    print("📊 DEMO THỐNG KÊ")
    print("="*70)
    
    stats = storage.get_statistics()
    
    print(f"\n📈 Tổng quan:")
    print(f"   Tổng số văn bản: {stats['total']}")
    
    print(f"\n🏢 Theo đơn vị ban hành:")
    for unit, count in stats['by_unit']:
        print(f"   • {unit}: {count} văn bản")
    
    print(f"\n📅 Theo năm:")
    for year, count in stats['by_year']:
        print(f"   • Năm {year}: {count} văn bản")


def demo_detail():
    """Demo xem chi tiết văn bản"""
    storage = ChatbotStorage()
    
    print("\n" + "="*70)
    print("📄 DEMO XEM CHI TIẾT VĂN BẢN")
    print("="*70)
    
    # Lấy văn bản ID = 1
    doc = storage.get_document_by_id(1)
    
    if doc:
        print(f"\n📌 Tiêu đề: {doc['tieu_de']}")
        print(f"📅 Ngày ban hành: {doc['ngay_ban_hanh']}")
        print(f"🏢 Đơn vị: {doc['don_vi_ban_hanh']}")
        print(f"\n📝 Trích yếu:")
        print(f"   {doc['trich_yeu']}")
        print(f"\n⭐ Nội dung quan trọng:")
        if isinstance(doc['noi_dung_quan_trong'], list):
            for i, item in enumerate(doc['noi_dung_quan_trong'], 1):
                print(f"   {i}. {item}")
    else:
        print("   ❌ Không tìm thấy văn bản")


def demo_backup():
    """Demo backup"""
    storage = ChatbotStorage()
    
    print("\n" + "="*70)
    print("💾 DEMO BACKUP")
    print("="*70)
    
    print("\n🔄 Đang backup SQLite → JSON...")
    count = storage.backup_to_json()
    
    print("\n🔄 Đang export → CSV...")
    storage.export_to_csv()


if __name__ == "__main__":
    print("🤖 CHATBOT STORAGE MANAGER")
    print("="*70)
    
    # Chạy tất cả demos
    demo_search()
    demo_statistics()
    demo_detail()
    demo_backup()
    
    print("\n" + "="*70)
    print("✅ HOÀN TẤT DEMO!")
    print("="*70)
    
    print("\n💡 GỢI Ý SỬ DỤNG:")
    print("   from chatbot_storage import ChatbotStorage")
    print("   storage = ChatbotStorage()")
    print("   results = storage.search_by_keyword('học phí')")
