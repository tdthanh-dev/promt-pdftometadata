import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor
from google import genai
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PgVectorStorage:
    """Lớp quản lý lưu trữ và tìm kiếm với PostgreSQL + pgvector"""
    
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'chatbot_db'),
            'user': os.getenv('POSTGRES_USER', 'chatbot_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'chatbot_pass')
        }
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
    def get_connection(self):
        """Tạo kết nối đến PostgreSQL"""
        return psycopg2.connect(**self.conn_params)
    
    def create_embedding(self, text: str) -> List[float]:
        """Tạo embedding vector từ text sử dụng Gemini text-embedding-004"""
        try:
            result = self.client.models.embed_content(
                model='models/text-embedding-004',
                content=text
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Lỗi tạo embedding: {e}")
            return None
    
    def save_document(self, doc_data: Dict[str, Any]) -> bool:
        """Lưu document và chunks vào PostgreSQL với embeddings"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            # Lưu document metadata
            doc_meta = doc_data['document_metadata']
            cur.execute("""
                INSERT INTO documents (
                    doc_id, file_name, doc_title, doc_type, issue_number,
                    issuing_authority, issuing_dept, issue_date, 
                    effective_date, expiration_date, major_topic
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    doc_title = EXCLUDED.doc_title,
                    doc_type = EXCLUDED.doc_type,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                doc_meta.get('DOC_ID'),
                doc_meta.get('FILE_NAME'),
                doc_meta.get('DOC_TITLE'),
                doc_meta.get('DOC_TYPE'),
                doc_meta.get('ISSUE_NUMBER'),
                doc_meta.get('ISSUING_AUTHORITY'),
                doc_meta.get('ISSUING_DEPT'),
                doc_meta.get('ISSUE_DATE'),
                doc_meta.get('EFFECTIVE_DATE'),
                doc_meta.get('EXPIRATION_DATE'),
                doc_meta.get('MAJOR_TOPIC')
            ))
            
            logger.info(f"Đã lưu document: {doc_meta.get('DOC_ID')}")
            
            # Lưu chunks với embeddings
            chunks_data = []
            for chunk in doc_data['chunk_metadata']:
                # Tạo embedding cho chunk text
                embedding = self.create_embedding(chunk['chunk_text'])
                if embedding is None:
                    logger.warning(f"Bỏ qua chunk {chunk.get('CHUNK_ID')} - không tạo được embedding")
                    continue
                
                chunks_data.append((
                    chunk.get('CHUNK_ID'),
                    doc_meta.get('DOC_ID'),
                    chunk.get('PAGE_NUMBER'),
                    chunk.get('SECTION_TITLE'),
                    chunk.get('CHUNK_TOPIC'),
                    chunk.get('CONTENT_TYPE'),
                    chunk.get('SPECIFIC_TARGET'),
                    chunk.get('APPLICABLE_COHORT'),
                    str(chunk.get('VALUE')) if chunk.get('VALUE') else None,
                    chunk.get('UNIT'),
                    chunk.get('KEYWORDS', []),
                    chunk['chunk_text'],
                    embedding
                ))
            
            # Batch insert chunks
            if chunks_data:
                execute_values(cur, """
                    INSERT INTO chunks (
                        chunk_id, doc_id, page_number, section_title, chunk_topic,
                        content_type, specific_target, applicable_cohort, value, unit,
                        keywords, chunk_text, embedding
                    ) VALUES %s
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        updated_at = CURRENT_TIMESTAMP
                """, chunks_data)
                
                logger.info(f"Đã lưu {len(chunks_data)} chunks với embeddings")
            
            conn.commit()
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Lỗi lưu document: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def semantic_search(self, query: str, limit: int = 5, 
                       content_type: Optional[str] = None,
                       applicable_cohort: Optional[str] = None) -> List[Dict]:
        """Tìm kiếm semantic sử dụng vector similarity"""
        conn = None
        try:
            # Tạo embedding cho query
            query_embedding = self.create_embedding(query)
            if query_embedding is None:
                return []
            
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build query với filters
            where_clauses = []
            params = [query_embedding, limit]
            
            if content_type:
                where_clauses.append("c.content_type = %s")
                params.insert(-1, content_type)
            
            if applicable_cohort:
                where_clauses.append("c.applicable_cohort LIKE %s")
                params.insert(-1, f"%{applicable_cohort}%")
            
            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            cur.execute(f"""
                SELECT 
                    c.chunk_id,
                    c.chunk_text,
                    c.chunk_topic,
                    c.content_type,
                    c.specific_target,
                    c.applicable_cohort,
                    c.value,
                    c.unit,
                    d.doc_title,
                    d.doc_type,
                    d.file_name,
                    d.issue_date,
                    1 - (c.embedding <=> %s::vector) as similarity
                FROM chunks c
                JOIN documents d ON c.doc_id = d.doc_id
                {where_sql}
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
            """, params)
            
            results = cur.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Lỗi tìm kiếm semantic: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def keyword_search(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Tìm kiếm full-text search"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT 
                    c.chunk_id,
                    c.chunk_text,
                    c.chunk_topic,
                    c.content_type,
                    d.doc_title,
                    d.file_name,
                    ts_rank(to_tsvector('vietnamese', c.chunk_text), 
                            plainto_tsquery('vietnamese', %s)) as rank
                FROM chunks c
                JOIN documents d ON c.doc_id = d.doc_id
                WHERE to_tsvector('vietnamese', c.chunk_text) @@ 
                      plainto_tsquery('vietnamese', %s)
                ORDER BY rank DESC
                LIMIT %s
            """, (keyword, keyword, limit))
            
            results = cur.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Lỗi tìm kiếm keyword: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_statistics(self) -> Dict:
        """Lấy thống kê database"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM documents) as total_documents,
                    (SELECT COUNT(*) FROM chunks) as total_chunks,
                    (SELECT COUNT(DISTINCT doc_type) FROM documents) as doc_types,
                    (SELECT COUNT(DISTINCT content_type) FROM chunks WHERE content_type IS NOT NULL) as content_types
            """)
            
            return dict(cur.fetchone())
            
        except Exception as e:
            logger.error(f"Lỗi lấy thống kê: {e}")
            return {}
        finally:
            if conn:
                conn.close()


# Ví dụ sử dụng
if __name__ == '__main__':
    storage = PgVectorStorage()
    
    # Load và lưu document từ output.json
    if os.path.exists('output.json'):
        with open('output.json', 'r', encoding='utf-8') as f:
            doc_data = json.load(f)
            success = storage.save_document(doc_data)
            if success:
                print("✅ Đã lưu document vào PostgreSQL với embeddings")
    
    # Test semantic search
    results = storage.semantic_search("học phí chương trình tiên tiến khóa 2024", limit=3)
    print(f"\n🔍 Kết quả tìm kiếm semantic (top 3):")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['chunk_topic']} - Similarity: {result['similarity']:.4f}")
        print(f"   {result['chunk_text'][:100]}...")
    
    # Thống kê
    stats = storage.get_statistics()
    print(f"\n📊 Thống kê:")
    print(f"   Documents: {stats.get('total_documents', 0)}")
    print(f"   Chunks: {stats.get('total_chunks', 0)}")
