"""Document AI Parser - API Routes (Simplified)"""
import logging
import os
import shutil
import uuid
import time
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.document import HealthResponse, SearchRequest, SearchResponse
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


@router.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    language: str = Query("en", description="OCR language code (en, hi, bn, te, mr, ta, gu, kn, ml, pa, ur)"),
    chunking_strategy: str = Query("semantic", description="Chunking: semantic, fixed, layout"),
    include_raw_text: bool = Query(True, description="Include raw extracted text"),
    include_chunks: bool = Query(True, description="Include text chunks with linkage"),
    store_in_elasticsearch: bool = Query(False, description="Also store in Elasticsearch for search"),
    validated_file: UploadFile = Depends(validate_file)
):
    """
    🔥 MAIN API: Parse document and return complete extracted data.
    
    Upload a file and get everything in one response:
    - OCR extracted text (22+ Indian languages)
    - Key-value pairs (name, date, case number, etc.)
    - Tables with cell data
    - Embedded data (hyperlinks, emails, phone numbers, annotations)
    - Smart chunks with bidirectional linkage for RAG
    - Document metadata
    
    **Supported Languages:**
    en, hi, bn, te, mr, ta, gu, kn, ml, pa, ur, ne, or, as, sa, kok, mai, doi, sd, ks, mni, sat
    
    **Chunking Strategies:**
    - `semantic`: By paragraphs and sections (default)
    - `fixed`: Fixed size with 10% overlap
    - `layout`: Respects headers, tables, figures
    """
    start_time = time.time()
    
    # Save uploaded file
    file_id = uuid.uuid4().hex[:16]
    file_ext = file.filename.rsplit('.', 1)[-1].lower()
    file_path = UPLOAD_DIR / f"{file_id}.{file_ext}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process document
        pipeline = get_document_pipeline()
        
        if store_in_elasticsearch:
            processed_doc = pipeline.process_and_store(
                file_path=file_path,
                filename=file.filename,
                lang=language,
                chunking_strategy=chunking_strategy
            )
        else:
            processed_doc = pipeline.process_document(
                file_path=file_path,
                filename=file.filename,
                lang=language,
                chunking_strategy=chunking_strategy
            )
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Build comprehensive response
        response = {
            "status": "success",
            "document_id": processed_doc.metadata.document_id,
            "filename": processed_doc.metadata.filename,
            "processing_time_ms": processing_time_ms,
            
            # Document info
            "document_info": {
                "file_type": processed_doc.metadata.file_type,
                "file_size_bytes": processed_doc.metadata.file_size_bytes,
                "page_count": processed_doc.metadata.page_count,
                "language_detected": processed_doc.metadata.language_detected,
                "languages": processed_doc.metadata.languages,
            },
            
            # PDF metadata
            "pdf_metadata": {
                "title": processed_doc.metadata.pdf_title,
                "author": processed_doc.metadata.pdf_author,
                "subject": processed_doc.metadata.pdf_subject,
                "keywords": processed_doc.metadata.pdf_keywords,
                "creator": processed_doc.metadata.pdf_creator,
                "has_forms": processed_doc.metadata.has_forms,
                "has_toc": processed_doc.metadata.has_toc,
                "is_encrypted": processed_doc.metadata.is_encrypted,
            },
            
            # Extracted key-value pairs
            "key_value_pairs": [
                {
                    "key": kv.key,
                    "value": kv.value,
                    "confidence": kv.confidence,
                    "page_number": kv.page_number,
                }
                for kv in processed_doc.metadata.key_value_pairs
            ],
            
            # Extracted tables
            "tables": [
                {
                    "table_id": table.table_id,
                    "page_number": table.page_number,
                    "rows": table.rows,
                    "cols": table.cols,
                    "headers": table.headers,
                    "data": table.data_as_dict,
                    "confidence": table.confidence,
                }
                for table in processed_doc.metadata.tables
            ],
            
            # Embedded data
            "embedded_data": {
                "links": processed_doc.metadata.embedded_links,
                "emails": processed_doc.metadata.embedded_emails,
                "phone_numbers": processed_doc.metadata.embedded_phones,
                "annotations": processed_doc.metadata.annotations,
                "table_of_contents": processed_doc.metadata.table_of_contents,
                "form_fields": processed_doc.metadata.form_fields,
            },
            
            # Summary counts
            "extraction_summary": {
                "key_value_pairs_count": len(processed_doc.metadata.key_value_pairs),
                "tables_count": len(processed_doc.metadata.tables),
                "chunks_count": len(processed_doc.chunks),
                "links_count": len(processed_doc.metadata.embedded_links),
                "emails_count": len(processed_doc.metadata.embedded_emails),
                "phones_count": len(processed_doc.metadata.embedded_phones),
                "annotations_count": len(processed_doc.metadata.annotations),
            },
        }
        
        # Optional: include raw text
        if include_raw_text:
            response["raw_text"] = processed_doc.raw_text
        
        # Optional: include chunks with linkage
        if include_chunks:
            response["chunks"] = [
                {
                    "chunk_id": chunk.chunk_id,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "content_type": chunk.content_type.value,
                    "confidence_score": chunk.confidence_score,
                    # Bidirectional linkage for RAG
                    "prev_chunk_id": chunk.prev_chunk_id,
                    "next_chunk_id": chunk.next_chunk_id,
                    "parent_section": chunk.parent_section,
                    "section_hierarchy": chunk.section_hierarchy,
                    "sibling_chunks": chunk.sibling_chunks,
                    "is_continuation": chunk.is_continuation,
                    "continues_to_next": chunk.continues_to_next,
                }
                for chunk in processed_doc.chunks
            ]
        
        return response
        
    except Exception as e:
        logger.error(f"Document parsing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up uploaded file
        for attempt in range(3):
            try:
                if file_path.exists():
                    os.remove(file_path)
                break
            except PermissionError:
                time.sleep(0.5)
            except Exception:
                break


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Full-text search across all stored documents.
    
    Note: Documents must be parsed with `store_in_elasticsearch=true` to be searchable.
    """
    es_service = get_elasticsearch_service()
    return es_service.search(request)


@router.get("/languages")
async def get_supported_languages():
    """Get list of all supported OCR languages."""
    return {
        "supported_languages": [
            {"code": "en", "name": "English", "status": "full"},
            {"code": "hi", "name": "Hindi", "status": "full"},
            {"code": "bn", "name": "Bengali", "status": "full"},
            {"code": "te", "name": "Telugu", "status": "full"},
            {"code": "mr", "name": "Marathi", "status": "full"},
            {"code": "ta", "name": "Tamil", "status": "full"},
            {"code": "gu", "name": "Gujarati", "status": "full"},
            {"code": "kn", "name": "Kannada", "status": "full"},
            {"code": "ml", "name": "Malayalam", "status": "full"},
            {"code": "pa", "name": "Punjabi", "status": "full"},
            {"code": "ur", "name": "Urdu", "status": "full"},
            {"code": "ne", "name": "Nepali", "status": "full"},
            {"code": "or", "name": "Odia", "status": "fallback", "fallback_to": "te"},
            {"code": "as", "name": "Assamese", "status": "fallback", "fallback_to": "bn"},
            {"code": "sa", "name": "Sanskrit", "status": "fallback", "fallback_to": "hi"},
            {"code": "kok", "name": "Konkani", "status": "fallback", "fallback_to": "mr"},
            {"code": "mai", "name": "Maithili", "status": "fallback", "fallback_to": "hi"},
            {"code": "doi", "name": "Dogri", "status": "fallback", "fallback_to": "hi"},
            {"code": "sd", "name": "Sindhi", "status": "fallback", "fallback_to": "ur"},
            {"code": "ks", "name": "Kashmiri", "status": "fallback", "fallback_to": "ur"},
            {"code": "mni", "name": "Manipuri", "status": "fallback", "fallback_to": "bn"},
            {"code": "sat", "name": "Santali", "status": "limited", "fallback_to": "en"},
        ],
        "total": 22
    }
