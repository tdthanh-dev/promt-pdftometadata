"""
Pydantic schemas for document and chunk metadata.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class DocumentMetadata(BaseModel):
    """Metadata cấp tài liệu."""
    
    DOC_ID: str = Field(description="Mã định danh duy nhất của tài liệu")
    FILE_NAME: str = Field(description="Tên file gốc")
    DOC_TITLE: str = Field(description="Tiêu đề đầy đủ của tài liệu")
    DOC_TYPE: str = Field(description="Loại tài liệu: Thông báo, Quy định, Quy chế, ...")
    ISSUE_NUMBER: Optional[str] = Field(default=None, description="Số hiệu văn bản")
    ISSUING_AUTHORITY: Optional[str] = Field(default=None, description="Cơ quan ban hành")
    ISSUING_DEPT: Optional[str] = Field(default=None, description="Phòng ban ban hành")
    ISSUE_DATE: Optional[str] = Field(default=None, description="Ngày ban hành (YYYY-MM-DD)")
    EFFECTIVE_DATE: Optional[str] = Field(default=None, description="Ngày hiệu lực")
    EXPIRATION_DATE: Optional[str] = Field(default=None, description="Ngày hết hiệu lực")
    MAJOR_TOPIC: str = Field(description="Chủ đề chính")


class ChunkMetadata(BaseModel):
    """Metadata cấp đoạn văn."""
    
    CHUNK_ID: str = Field(description="Mã định danh duy nhất của chunk")
    PAGE_NUMBER: int = Field(description="Số trang trong tài liệu")
    SECTION_TITLE: Optional[str] = Field(default=None, description="Tiêu đề phần/mục")
    CHUNK_TOPIC: str = Field(description="Chủ đề của đoạn văn này")
    CONTENT_TYPE: Optional[str] = Field(default=None, description="Loại nội dung: Đại trà, CLCQ, ...")
    SPECIFIC_TARGET: Optional[str] = Field(default=None, description="Đối tượng cụ thể")
    APPLICABLE_COHORT: Optional[str] = Field(default=None, description="Khóa áp dụng: Khóa 2024, Khóa 2025, ...")
    VALUE: Optional[float] = Field(default=None, description="Giá trị số nếu có")
    UNIT: Optional[str] = Field(default=None, description="Đơn vị của giá trị")
    KEYWORDS: List[str] = Field(description="Từ khóa cho semantic search")
    chunk_text: str = Field(description="Nội dung đầy đủ của đoạn văn")
