"""Document AI Parser - Pydantic Models"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ContentType(str, Enum):
    """Type of content in a chunk."""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    FIGURE = "figure"
    FOOTER = "footer"
    HEADER = "header"


class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x: float
    y: float
    width: float
    height: float


class KeyValuePair(BaseModel):
    """Extracted key-value pair."""
    key: str
    value: str
    confidence: float = 1.0
    page_number: Optional[int] = None
    bounding_box: Optional[BoundingBox] = None


class TableCell(BaseModel):
    """Table cell data."""
    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1


class ExtractedTable(BaseModel):
    """Extracted table data."""
    table_id: str
    page_number: int
    rows: int
    cols: int
    cells: List[TableCell]
    headers: Optional[List[str]] = None
    data_as_dict: Optional[List[Dict[str, str]]] = None
    confidence: float = 1.0
    bounding_box: Optional[BoundingBox] = None


class DocumentChunk(BaseModel):
    """A chunk of document content with metadata."""
    # Identifiers
    chunk_id: str
    document_id: str
    
    # Position
    chunk_index: int
    chunk_total: int
    page_number: int
    
    # Content
    content: str
    content_type: ContentType = ContentType.PARAGRAPH
    confidence_score: float = 1.0
    
    # Bounding box
    bounding_box: Optional[BoundingBox] = None
    
    # Chunk Linkage
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    parent_section: Optional[str] = None
    section_hierarchy: List[str] = Field(default_factory=list)
    sibling_chunks: List[str] = Field(default_factory=list)
    overlap_with_prev: Optional[str] = None
    overlap_with_next: Optional[str] = None
    is_continuation: bool = False
    continues_to_next: bool = False


class DocumentMetadata(BaseModel):
    """Rich document metadata."""
    # File info
    document_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    page_count: int
    
    # Processing info
    upload_timestamp: datetime
    processing_time_ms: int
    
    # Language
    language_detected: str = "en"
    languages: List[str] = Field(default_factory=list)
    
    # Document category
    document_category: Optional[str] = None
    state: Optional[str] = None  # For Indian legal docs
    
    # Flags
    has_handwriting: bool = False
    has_stamps: bool = False
    has_tables: bool = False
    has_forms: bool = False
    has_toc: bool = False
    is_encrypted: bool = False
    
    # PDF Metadata
    pdf_title: Optional[str] = None
    pdf_author: Optional[str] = None
    pdf_subject: Optional[str] = None
    pdf_keywords: Optional[str] = None
    pdf_creator: Optional[str] = None
    
    # Extracted data
    key_value_pairs: List[KeyValuePair] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)
    
    # Embedded data (from PDF)
    embedded_links: List[Dict[str, Any]] = Field(default_factory=list)
    embedded_emails: List[Dict[str, Any]] = Field(default_factory=list)
    embedded_phones: List[Dict[str, Any]] = Field(default_factory=list)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)
    table_of_contents: List[Dict[str, Any]] = Field(default_factory=list)
    form_fields: List[Dict[str, Any]] = Field(default_factory=list)


class ProcessedDocument(BaseModel):
    """Complete processed document."""
    metadata: DocumentMetadata
    chunks: List[DocumentChunk]
    raw_text: str


class UploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str
    filename: str
    status: str = "processed"
    page_count: int
    chunk_count: int
    processing_time_ms: int
    key_value_pairs_count: int
    tables_count: int
    # Embedded data counts
    links_count: int = 0
    emails_count: int = 0
    annotations_count: int = 0


class SearchRequest(BaseModel):
    """Search request body."""
    query: str
    document_id: Optional[str] = None
    page: int = 1
    size: int = 10
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Single search result."""
    chunk_id: str
    document_id: str
    filename: str
    content: str
    page_number: int
    score: float
    highlights: Optional[List[str]] = None
    # Linkage for context
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    total: int
    page: int
    size: int
    results: List[SearchResult]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    elasticsearch: str
    version: str = "1.0.0"
