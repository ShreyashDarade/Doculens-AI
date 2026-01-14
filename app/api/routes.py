"""Document AI Parser - API Routes"""
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.document import (
    UploadResponse, SearchRequest, SearchResponse, HealthResponse
)
from app.api.dependencies import validate_file, UPLOAD_DIR
from app.pipeline.document_pipeline import get_document_pipeline
from app.services.elasticsearch_service import get_elasticsearch_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and Elasticsearch health."""
    es_service = get_elasticsearch_service()
    es_healthy = es_service.is_healthy()
    
    return HealthResponse(
        status="healthy" if es_healthy else "degraded",
        elasticsearch="connected" if es_healthy else "disconnected",
        version="1.0.0"
    )


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    language: str = Query("en", description="OCR language (en, hi, mr, ta, te)"),
    chunking_strategy: str = Query("semantic", description="Chunking strategy: semantic, fixed, layout"),
    validated_file: UploadFile = Depends(validate_file)
):
    """
    Upload and process a document.
    
    Extracts text, tables, key-value pairs, and stores in Elasticsearch.
    """
    # Save uploaded file
    file_id = uuid.uuid4().hex[:16]
    file_ext = file.filename.rsplit('.', 1)[-1].lower()
    file_path = UPLOAD_DIR / f"{file_id}.{file_ext}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process document
        pipeline = get_document_pipeline()
        processed_doc = pipeline.process_and_store(
            file_path=file_path,
            filename=file.filename,
            lang=language,
            chunking_strategy=chunking_strategy
        )
        
        return UploadResponse(
            document_id=processed_doc.metadata.document_id,
            filename=processed_doc.metadata.filename,
            status="processed",
            page_count=processed_doc.metadata.page_count,
            chunk_count=len(processed_doc.chunks),
            processing_time_ms=processed_doc.metadata.processing_time_ms,
            key_value_pairs_count=len(processed_doc.metadata.key_value_pairs),
            tables_count=len(processed_doc.metadata.tables),
            links_count=len(processed_doc.metadata.embedded_links),
            emails_count=len(processed_doc.metadata.embedded_emails),
            annotations_count=len(processed_doc.metadata.annotations),
        )
        
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up uploaded file
        if file_path.exists():
            os.remove(file_path)


@router.post("/documents/batch", response_model=List[UploadResponse])
async def batch_upload(
    files: List[UploadFile] = File(...),
    language: str = Query("en"),
    chunking_strategy: str = Query("semantic")
):
    """Upload and process multiple documents."""
    results = []
    
    for file in files:
        try:
            result = await upload_document(
                file=file,
                language=language,
                chunking_strategy=chunking_strategy,
                validated_file=file
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            results.append(UploadResponse(
                document_id="",
                filename=file.filename,
                status=f"failed: {str(e)}",
                page_count=0,
                chunk_count=0,
                processing_time_ms=0,
                key_value_pairs_count=0,
                tables_count=0
            ))
    
    return results


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document metadata by ID."""
    es_service = get_elasticsearch_service()
    metadata = es_service.get_document(document_id)
    
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return metadata.model_dump()


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100)
):
    """Get all chunks for a document with linkage information."""
    es_service = get_elasticsearch_service()
    chunks = es_service.get_chunks(document_id)
    
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Paginate
    start = (page - 1) * size
    end = start + size
    paginated = chunks[start:end]
    
    return {
        "document_id": document_id,
        "total_chunks": len(chunks),
        "page": page,
        "size": size,
        "chunks": paginated
    }


@router.get("/documents/{document_id}/key-values")
async def get_document_key_values(document_id: str):
    """Get extracted key-value pairs for a document."""
    es_service = get_elasticsearch_service()
    key_values = es_service.get_key_values(document_id)
    
    return {
        "document_id": document_id,
        "count": len(key_values),
        "key_value_pairs": key_values
    }


@router.get("/documents/{document_id}/tables")
async def get_document_tables(document_id: str):
    """Get extracted tables for a document."""
    es_service = get_elasticsearch_service()
    tables = es_service.get_tables(document_id)
    
    return {
        "document_id": document_id,
        "count": len(tables),
        "tables": tables
    }


@router.get("/documents/{document_id}/embedded")
async def get_document_embedded(document_id: str):
    """Get all embedded data from a document (links, emails, phones, annotations)."""
    es_service = get_elasticsearch_service()
    
    metadata = es_service.get_document(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": document_id,
        "links": metadata.embedded_links,
        "emails": metadata.embedded_emails,
        "phone_numbers": metadata.embedded_phones,
        "annotations": metadata.annotations,
        "table_of_contents": metadata.table_of_contents,
        "form_fields": metadata.form_fields,
        "pdf_metadata": {
            "title": metadata.pdf_title,
            "author": metadata.pdf_author,
            "subject": metadata.pdf_subject,
            "keywords": metadata.pdf_keywords,
            "creator": metadata.pdf_creator,
            "has_forms": metadata.has_forms,
            "has_toc": metadata.has_toc,
            "is_encrypted": metadata.is_encrypted,
        },
        "counts": {
            "links": len(metadata.embedded_links),
            "emails": len(metadata.embedded_emails),
            "phones": len(metadata.embedded_phones),
            "annotations": len(metadata.annotations),
        }
    }


@router.get("/documents/{document_id}/metadata")
async def get_document_metadata(document_id: str):
    """Get full document metadata including all extracted data."""
    es_service = get_elasticsearch_service()
    
    metadata = es_service.get_document(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")
    
    key_values = es_service.get_key_values(document_id)
    tables = es_service.get_tables(document_id)
    chunks = es_service.get_chunks(document_id)
    
    return {
        "metadata": metadata.model_dump(),
        "key_value_pairs": key_values,
        "tables": tables,
        "chunk_summary": {
            "total": len(chunks),
            "by_type": _count_by_type(chunks),
            "by_page": _count_by_page(chunks)
        }
    }


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """Full-text search across all documents."""
    es_service = get_elasticsearch_service()
    return es_service.search(request)


@router.get("/documents/{document_id}/chunk/{chunk_id}/context")
async def get_chunk_context(document_id: str, chunk_id: str, window: int = Query(2, ge=1, le=5)):
    """
    Get a chunk with its surrounding context.
    
    Returns the chunk plus previous/next chunks based on linkage.
    """
    es_service = get_elasticsearch_service()
    all_chunks = es_service.get_chunks(document_id)
    
    if not all_chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Find the target chunk
    target_idx = None
    for i, chunk in enumerate(all_chunks):
        if chunk["chunk_id"] == chunk_id:
            target_idx = i
            break
    
    if target_idx is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    # Get context window
    start_idx = max(0, target_idx - window)
    end_idx = min(len(all_chunks), target_idx + window + 1)
    
    context_chunks = all_chunks[start_idx:end_idx]
    
    return {
        "document_id": document_id,
        "target_chunk_id": chunk_id,
        "target_chunk_index": target_idx,
        "window": window,
        "context_chunks": context_chunks,
        "section_hierarchy": all_chunks[target_idx].get("section_hierarchy", [])
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks."""
    es_service = get_elasticsearch_service()
    success = es_service.delete_document(document_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document")
    
    return {"status": "deleted", "document_id": document_id}


def _count_by_type(chunks: list) -> dict:
    """Count chunks by content type."""
    counts = {}
    for chunk in chunks:
        content_type = chunk.get("content_type", "unknown")
        counts[content_type] = counts.get(content_type, 0) + 1
    return counts


def _count_by_page(chunks: list) -> dict:
    """Count chunks by page number."""
    counts = {}
    for chunk in chunks:
        page = str(chunk.get("page_number", 0))
        counts[page] = counts.get(page, 0) + 1
    return counts
