"""Document AI Parser - Main Document Processing Pipeline"""
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from app.models.document import (
    ProcessedDocument, DocumentMetadata, DocumentChunk,
    ExtractedTable, KeyValuePair
)
from app.services.ocr_service import get_ocr_service
from app.services.layout_service import get_layout_service, LayoutElement
from app.services.table_service import get_table_service
from app.services.chunking_service import get_chunking_service
from app.services.kv_extraction import get_kv_extraction_service
from app.services.elasticsearch_service import get_elasticsearch_service
from app.services.metadata_service import get_pdf_metadata_service

logger = logging.getLogger(__name__)


class DocumentPipeline:
    """
    Main document processing pipeline.
    
    Orchestrates:
    1. PDF/Image loading
    2. OCR extraction
    3. Layout detection
    4. Table extraction
    5. Key-value extraction
    6. Embedded data extraction (links, emails, annotations)
    7. Smart chunking
    8. Elasticsearch indexing
    """
    
    def __init__(self):
        self.ocr_service = get_ocr_service()
        self.layout_service = get_layout_service()
        self.table_service = get_table_service()
        self.chunking_service = get_chunking_service()
        self.kv_service = get_kv_extraction_service()
        self.es_service = get_elasticsearch_service()
        self.metadata_service = get_pdf_metadata_service()
    
    def process_document(
        self,
        file_path: str | Path,
        filename: str,
        lang: str = "en",
        chunking_strategy: str = "semantic"
    ) -> ProcessedDocument:
        """
        Process a document through the full pipeline.
        
        Args:
            file_path: Path to the document file
            filename: Original filename
            lang: OCR language
            chunking_strategy: "semantic", "fixed", or "layout"
            
        Returns:
            ProcessedDocument with all extracted data
        """
        start_time = time.time()
        
        file_path = Path(file_path)
        document_id = f"doc_{uuid.uuid4().hex[:16]}"
        
        # Determine file type
        file_type = file_path.suffix.lower().lstrip('.')
        file_size = file_path.stat().st_size
        
        # Process based on file type
        if file_type == 'pdf':
            result = self._process_pdf(file_path, document_id, lang, chunking_strategy)
        else:
            result = self._process_image(file_path, document_id, lang, chunking_strategy)
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Create metadata
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            page_count=result['page_count'],
            upload_timestamp=datetime.now(timezone.utc),
            processing_time_ms=processing_time_ms,
            language_detected=result.get('language', lang),
            languages=result.get('languages', [lang]),
            document_category=result.get('category'),
            state=result.get('state'),
            has_handwriting=result.get('has_handwriting', False),
            has_stamps=result.get('has_stamps', False),
            has_tables=len(result.get('tables', [])) > 0,
            has_forms=result.get('has_forms', False),
            has_toc=result.get('has_toc', False),
            is_encrypted=result.get('is_encrypted', False),
            # PDF Metadata
            pdf_title=result.get('pdf_title'),
            pdf_author=result.get('pdf_author'),
            pdf_subject=result.get('pdf_subject'),
            pdf_keywords=result.get('pdf_keywords'),
            pdf_creator=result.get('pdf_creator'),
            # Extracted data
            key_value_pairs=result.get('key_value_pairs', []),
            tables=result.get('tables', []),
            # Embedded data
            embedded_links=result.get('embedded_links', []),
            embedded_emails=result.get('embedded_emails', []),
            embedded_phones=result.get('embedded_phones', []),
            annotations=result.get('annotations', []),
            table_of_contents=result.get('table_of_contents', []),
            form_fields=result.get('form_fields', []),
        )
        
        processed_doc = ProcessedDocument(
            metadata=metadata,
            chunks=result['chunks'],
            raw_text=result.get('raw_text', '')
        )
        
        return processed_doc
    
    def _process_pdf(
        self,
        file_path: Path,
        document_id: str,
        lang: str,
        chunking_strategy: str
    ) -> dict:
        """Process a PDF document."""
        all_chunks = []
        all_text_blocks = []
        raw_text_parts = []
        all_key_values = []
        all_tables = []
        
        # Open PDF
        pdf_doc = fitz.open(str(file_path))
        page_count = len(pdf_doc)
        
        for page_num in range(page_count):
            page = pdf_doc[page_num]
            
            # Convert page to image for OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better OCR
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_array = np.array(img)
            
            # OCR extraction
            full_text, avg_confidence, text_blocks = self.ocr_service.extract_text_from_page(
                img_array, lang
            )
            
            raw_text_parts.append(full_text)
            
            # Layout detection
            layout_elements = self.layout_service.detect_layout(img_array, text_blocks)
            
            # Update text blocks with page number
            for block in text_blocks:
                block['page_number'] = page_num + 1
            all_text_blocks.extend(text_blocks)
            
            # Chunk this page
            page_chunks = self.chunking_service.chunk_document(
                document_id, layout_elements, chunking_strategy
            )
            
            # Update page numbers
            for chunk in page_chunks:
                chunk.page_number = page_num + 1
            
            all_chunks.extend(page_chunks)
        
        pdf_doc.close()
        
        # Re-index chunks and update linkage
        for i, chunk in enumerate(all_chunks):
            chunk.chunk_index = i
            chunk.chunk_total = len(all_chunks)
            if i > 0:
                chunk.prev_chunk_id = all_chunks[i-1].chunk_id
                all_chunks[i-1].next_chunk_id = chunk.chunk_id
        
        # Extract tables from PDF
        all_tables = self.table_service.extract_tables_from_pdf(str(file_path))
        
        # Extract embedded data (links, emails, phones, annotations)
        embedded_data = self.metadata_service.extract_to_dict(file_path)
        
        # Extract key-value pairs from full text
        raw_text = "\n\n".join(raw_text_parts)
        all_key_values = self.kv_service.extract_from_text(raw_text, include_legal=True)
        
        # Also extract from layout
        layout_kv = self.kv_service.extract_from_layout(all_text_blocks)
        for kv in layout_kv:
            if not any(existing.key == kv.key for existing in all_key_values):
                all_key_values.append(kv)
        
        # Detect language
        detected_lang = self.ocr_service.detect_language(all_text_blocks)
        
        # Try to extract state from key-values
        state = None
        for kv in all_key_values:
            if kv.key.lower() == 'state':
                state = kv.value
                break
        
        return {
            'page_count': page_count,
            'chunks': all_chunks,
            'raw_text': raw_text,
            'tables': all_tables,
            'key_value_pairs': all_key_values,
            'language': detected_lang,
            'languages': [detected_lang],
            'state': state,
            'has_handwriting': False,
            'has_stamps': False,
            # PDF metadata
            'has_forms': embedded_data['metadata'].get('has_forms', False),
            'has_toc': embedded_data['metadata'].get('has_toc', False),
            'is_encrypted': embedded_data['metadata'].get('is_encrypted', False),
            'pdf_title': embedded_data['metadata'].get('title'),
            'pdf_author': embedded_data['metadata'].get('author'),
            'pdf_subject': embedded_data['metadata'].get('subject'),
            'pdf_keywords': embedded_data['metadata'].get('keywords'),
            'pdf_creator': embedded_data['metadata'].get('creator'),
            # Embedded data
            'embedded_links': embedded_data.get('links', []),
            'embedded_emails': embedded_data.get('emails', []),
            'embedded_phones': embedded_data.get('phone_numbers', []),
            'annotations': embedded_data.get('annotations', []),
            'table_of_contents': embedded_data.get('table_of_contents', []),
            'form_fields': embedded_data.get('form_fields', []),
        }
    
    def _process_image(
        self,
        file_path: Path,
        document_id: str,
        lang: str,
        chunking_strategy: str
    ) -> dict:
        """Process an image document."""
        # Load image
        img = Image.open(str(file_path))
        img_array = np.array(img)
        
        # OCR extraction
        full_text, avg_confidence, text_blocks = self.ocr_service.extract_text_from_page(
            img_array, lang
        )
        
        # Update with page number
        for block in text_blocks:
            block['page_number'] = 1
        
        # Layout detection
        layout_elements = self.layout_service.detect_layout(img_array, text_blocks)
        
        # Chunking
        chunks = self.chunking_service.chunk_document(
            document_id, layout_elements, chunking_strategy
        )
        
        for chunk in chunks:
            chunk.page_number = 1
        
        # Extract key-values
        key_values = self.kv_service.extract_from_text(full_text, include_legal=True)
        layout_kv = self.kv_service.extract_from_layout(text_blocks)
        for kv in layout_kv:
            if not any(existing.key == kv.key for existing in key_values):
                key_values.append(kv)
        
        # Detect language
        detected_lang = self.ocr_service.detect_language(text_blocks)
        
        return {
            'page_count': 1,
            'chunks': chunks,
            'raw_text': full_text,
            'tables': [],  # Table extraction from images not yet implemented
            'key_value_pairs': key_values,
            'language': detected_lang,
            'languages': [detected_lang],
            'state': None,
            'has_handwriting': False,
            'has_stamps': False,
        }
    
    def process_and_store(
        self,
        file_path: str | Path,
        filename: str,
        lang: str = "en",
        chunking_strategy: str = "semantic"
    ) -> ProcessedDocument:
        """
        Process document and store in Elasticsearch.
        
        Returns the processed document.
        """
        processed_doc = self.process_document(
            file_path, filename, lang, chunking_strategy
        )
        
        # Store in Elasticsearch
        success = self.es_service.index_document(processed_doc)
        if not success:
            logger.error(f"Failed to store document {processed_doc.metadata.document_id}")
        
        return processed_doc


# Singleton instance
_pipeline: Optional[DocumentPipeline] = None


def get_document_pipeline() -> DocumentPipeline:
    """Get document pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = DocumentPipeline()
    return _pipeline
