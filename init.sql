-- Kích hoạt extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Tạo bảng documents để lưu metadata tài liệu
CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(255) PRIMARY KEY,
    file_name VARCHAR(500),
    doc_title TEXT,
    doc_type VARCHAR(100),
    issue_number VARCHAR(100),
    issuing_authority VARCHAR(500),
    issuing_dept VARCHAR(500),
    issue_date DATE,
    effective_date VARCHAR(100),
    expiration_date DATE,
    major_topic VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tạo bảng chunks để lưu metadata và embedding của từng chunk
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    doc_id VARCHAR(255) REFERENCES documents(doc_id) ON DELETE CASCADE,
    page_number INTEGER,
    section_title VARCHAR(500),
    chunk_topic TEXT,
    content_type VARCHAR(200),
    specific_target VARCHAR(500),
    applicable_cohort VARCHAR(200),
    value VARCHAR(100),
    unit VARCHAR(50),
    keywords TEXT[],
    chunk_text TEXT NOT NULL,
    embedding vector(768),  -- text-embedding-004 tạo 768 chiều
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index cho tìm kiếm vector (HNSW hoặc IVFFlat)
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks 
USING hnsw (embedding vector_cosine_ops);

-- Index cho các trường thường query
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_type ON chunks(content_type);
CREATE INDEX IF NOT EXISTS idx_chunks_applicable_cohort ON chunks(applicable_cohort);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_major_topic ON documents(major_topic);
CREATE INDEX IF NOT EXISTS idx_documents_issue_date ON documents(issue_date);

-- Full-text search index cho chunk_text
CREATE INDEX IF NOT EXISTS idx_chunks_text_search ON chunks 
USING gin(to_tsvector('vietnamese', chunk_text));

-- Trigger để tự động update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chunks_updated_at BEFORE UPDATE ON chunks
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- View để query dễ dàng hơn
CREATE OR REPLACE VIEW chunks_with_doc_info AS
SELECT 
    c.*,
    d.doc_title,
    d.doc_type,
    d.issue_date,
    d.major_topic,
    d.file_name
FROM chunks c
JOIN documents d ON c.doc_id = d.doc_id;

COMMENT ON TABLE documents IS 'Lưu metadata của các tài liệu PDF';
COMMENT ON TABLE chunks IS 'Lưu metadata và vector embeddings của từng chunk văn bản';
COMMENT ON COLUMN chunks.embedding IS 'Vector embedding 768 chiều từ text-embedding-004';
