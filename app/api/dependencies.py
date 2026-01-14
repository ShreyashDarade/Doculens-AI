"""Document AI Parser - API Dependencies"""
from fastapi import Depends, HTTPException, UploadFile
from pathlib import Path
import os

from app.config import get_settings
from app.services.elasticsearch_service import get_elasticsearch_service


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def validate_file(file: UploadFile) -> UploadFile:
    """Validate uploaded file."""
    settings = get_settings()
    
    # Check file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {settings.allowed_extensions_list}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset
    
    max_size = settings.max_file_size_mb * 1024 * 1024
    if size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size_mb}MB"
        )
    
    return file


def get_es_service():
    """Get Elasticsearch service dependency."""
    return get_elasticsearch_service()
