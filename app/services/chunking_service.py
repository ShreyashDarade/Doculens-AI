"""Document AI Parser - Smart Chunking Service with Linkage"""
import logging
from typing import List, Optional, Tuple
import uuid
import re

from app.config import get_settings
from app.models.document import DocumentChunk, ContentType, BoundingBox
from app.services.layout_service import LayoutElement, LayoutType

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Smart text chunking service with chunk linkage.
    
    Supports multiple chunking strategies:
    - Semantic: by paragraph/section
    - Fixed-size with overlap
    - Layout-aware: respects headers, tables
    """
    
    def __init__(self):
        settings = get_settings()
        self.chunk_size = settings.chunk_size
        self.overlap_ratio = settings.chunk_overlap
    
    def chunk_document(
        self,
        document_id: str,
        layout_elements: List[LayoutElement],
        strategy: str = "semantic"
    ) -> List[DocumentChunk]:
        """
        Chunk document content with full linkage.
        
        Args:
            document_id: Document identifier
            layout_elements: Detected layout elements with text
            strategy: "semantic", "fixed", or "layout"
            
        Returns:
            List of chunks with bidirectional linkage
        """
        if strategy == "fixed":
            chunks = self._fixed_size_chunking(document_id, layout_elements)
        elif strategy == "layout":
            chunks = self._layout_aware_chunking(document_id, layout_elements)
        else:
            chunks = self._semantic_chunking(document_id, layout_elements)
        
        # Add linkage
        chunks = self._add_chunk_linkage(chunks)
        
        return chunks
    
    def _semantic_chunking(
        self,
        document_id: str,
        layout_elements: List[LayoutElement]
    ) -> List[DocumentChunk]:
        """Chunk by semantic boundaries (paragraphs, sections)."""
        chunks = []
        current_section = None
        section_hierarchy = []
        
        for elem in layout_elements:
            # Track section headers
            if elem.element_type in [LayoutType.TITLE, LayoutType.SECTION_HEADER]:
                current_section = elem.text[:50] if elem.text else None
                if elem.element_type == LayoutType.TITLE:
                    section_hierarchy = [current_section]
                else:
                    # Add to hierarchy
                    if len(section_hierarchy) > 3:
                        section_hierarchy = section_hierarchy[:2]
                    section_hierarchy.append(current_section)
            
            # Skip empty elements
            if not elem.text or len(elem.text.strip()) < 3:
                continue
            
            # Create chunk
            chunk = DocumentChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                document_id=document_id,
                chunk_index=len(chunks),
                chunk_total=0,  # Will be updated later
                page_number=1,  # Will be updated by caller
                content=elem.text.strip(),
                content_type=self._layout_to_content_type(elem.element_type),
                confidence_score=elem.confidence,
                bounding_box=elem.bounding_box,
                parent_section=current_section,
                section_hierarchy=list(section_hierarchy),
            )
            chunks.append(chunk)
        
        # Update total count
        for chunk in chunks:
            chunk.chunk_total = len(chunks)
        
        return chunks
    
    def _fixed_size_chunking(
        self,
        document_id: str,
        layout_elements: List[LayoutElement]
    ) -> List[DocumentChunk]:
        """Chunk by fixed token/character size with overlap."""
        # Combine all text
        full_text = "\n".join([
            elem.text for elem in layout_elements 
            if elem.text and elem.element_type not in [LayoutType.HEADER, LayoutType.FOOTER]
        ])
        
        chunks = []
        overlap_size = int(self.chunk_size * self.overlap_ratio)
        
        # Split into sentences first
        sentences = self._split_into_sentences(full_text)
        
        current_chunk_text = ""
        current_chunk_sentences = []
        
        for sentence in sentences:
            if len(current_chunk_text) + len(sentence) > self.chunk_size:
                if current_chunk_text:
                    # Store overlap for next chunk
                    overlap_text = " ".join(current_chunk_sentences[-2:]) if len(current_chunk_sentences) >= 2 else ""
                    
                    chunk = DocumentChunk(
                        chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        chunk_index=len(chunks),
                        chunk_total=0,
                        page_number=1,
                        content=current_chunk_text.strip(),
                        content_type=ContentType.PARAGRAPH,
                        confidence_score=1.0,
                        overlap_with_next=overlap_text[:overlap_size] if overlap_text else None,
                    )
                    
                    # Set overlap from previous chunk
                    if chunks:
                        chunk.overlap_with_prev = chunks[-1].overlap_with_next
                        chunk.is_continuation = True
                        chunks[-1].continues_to_next = True
                    
                    chunks.append(chunk)
                    
                    # Start new chunk with overlap
                    current_chunk_text = overlap_text + " " + sentence if overlap_text else sentence
                    current_chunk_sentences = current_chunk_sentences[-2:] + [sentence] if current_chunk_sentences else [sentence]
            else:
                current_chunk_text += " " + sentence if current_chunk_text else sentence
                current_chunk_sentences.append(sentence)
        
        # Add final chunk
        if current_chunk_text:
            chunk = DocumentChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                document_id=document_id,
                chunk_index=len(chunks),
                chunk_total=0,
                page_number=1,
                content=current_chunk_text.strip(),
                content_type=ContentType.PARAGRAPH,
                confidence_score=1.0,
            )
            if chunks:
                chunk.overlap_with_prev = chunks[-1].overlap_with_next
                chunk.is_continuation = True
            chunks.append(chunk)
        
        # Update total count
        for chunk in chunks:
            chunk.chunk_total = len(chunks)
        
        return chunks
    
    def _layout_aware_chunking(
        self,
        document_id: str,
        layout_elements: List[LayoutElement]
    ) -> List[DocumentChunk]:
        """Chunk respecting layout boundaries (keep tables, sections together)."""
        chunks = []
        current_section = None
        section_hierarchy = []
        pending_paragraphs = []
        
        for elem in layout_elements:
            # Track sections
            if elem.element_type in [LayoutType.TITLE, LayoutType.SECTION_HEADER]:
                # Flush pending paragraphs
                if pending_paragraphs:
                    chunk = self._merge_paragraphs(
                        document_id, pending_paragraphs, len(chunks),
                        current_section, section_hierarchy
                    )
                    if chunk:
                        chunks.append(chunk)
                    pending_paragraphs = []
                
                current_section = elem.text[:50] if elem.text else None
                section_hierarchy.append(current_section)
                
                # Create heading chunk
                if elem.text:
                    chunks.append(DocumentChunk(
                        chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        chunk_index=len(chunks),
                        chunk_total=0,
                        page_number=1,
                        content=elem.text.strip(),
                        content_type=ContentType.HEADING,
                        confidence_score=elem.confidence,
                        bounding_box=elem.bounding_box,
                        parent_section=current_section,
                        section_hierarchy=list(section_hierarchy),
                    ))
            
            elif elem.element_type == LayoutType.TABLE:
                # Flush pending paragraphs
                if pending_paragraphs:
                    chunk = self._merge_paragraphs(
                        document_id, pending_paragraphs, len(chunks),
                        current_section, section_hierarchy
                    )
                    if chunk:
                        chunks.append(chunk)
                    pending_paragraphs = []
                
                # Create table chunk
                if elem.text:
                    chunks.append(DocumentChunk(
                        chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                        document_id=document_id,
                        chunk_index=len(chunks),
                        chunk_total=0,
                        page_number=1,
                        content=elem.text,
                        content_type=ContentType.TABLE,
                        confidence_score=elem.confidence,
                        bounding_box=elem.bounding_box,
                        parent_section=current_section,
                        section_hierarchy=list(section_hierarchy),
                    ))
            
            elif elem.element_type == LayoutType.TEXT and elem.text:
                pending_paragraphs.append(elem)
                
                # Flush if accumulated text is too long
                total_len = sum(len(p.text) for p in pending_paragraphs)
                if total_len > self.chunk_size:
                    chunk = self._merge_paragraphs(
                        document_id, pending_paragraphs, len(chunks),
                        current_section, section_hierarchy
                    )
                    if chunk:
                        chunks.append(chunk)
                    pending_paragraphs = []
        
        # Flush remaining paragraphs
        if pending_paragraphs:
            chunk = self._merge_paragraphs(
                document_id, pending_paragraphs, len(chunks),
                current_section, section_hierarchy
            )
            if chunk:
                chunks.append(chunk)
        
        # Update total count
        for chunk in chunks:
            chunk.chunk_total = len(chunks)
        
        return chunks
    
    def _merge_paragraphs(
        self,
        document_id: str,
        paragraphs: List[LayoutElement],
        chunk_index: int,
        current_section: Optional[str],
        section_hierarchy: List[str]
    ) -> Optional[DocumentChunk]:
        """Merge multiple paragraphs into one chunk."""
        if not paragraphs:
            return None
        
        content = "\n".join([p.text for p in paragraphs if p.text])
        avg_confidence = sum(p.confidence for p in paragraphs) / len(paragraphs)
        
        return DocumentChunk(
            chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
            document_id=document_id,
            chunk_index=chunk_index,
            chunk_total=0,
            page_number=1,
            content=content,
            content_type=ContentType.PARAGRAPH,
            confidence_score=avg_confidence,
            parent_section=current_section,
            section_hierarchy=list(section_hierarchy),
        )
    
    def _add_chunk_linkage(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Add bidirectional linkage to chunks."""
        # Group by section
        section_chunks = {}
        
        for i, chunk in enumerate(chunks):
            # Previous/Next links
            if i > 0:
                chunk.prev_chunk_id = chunks[i - 1].chunk_id
            if i < len(chunks) - 1:
                chunk.next_chunk_id = chunks[i + 1].chunk_id
            
            # Group by section
            section = chunk.parent_section or "root"
            if section not in section_chunks:
                section_chunks[section] = []
            section_chunks[section].append(chunk.chunk_id)
        
        # Add sibling links
        for chunk in chunks:
            section = chunk.parent_section or "root"
            chunk.sibling_chunks = [
                cid for cid in section_chunks.get(section, [])
                if cid != chunk.chunk_id
            ]
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentence_enders = r'(?<=[.!?।])\s+'
        sentences = re.split(sentence_enders, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _layout_to_content_type(self, layout_type: LayoutType) -> ContentType:
        """Map layout type to content type."""
        mapping = {
            LayoutType.TEXT: ContentType.PARAGRAPH,
            LayoutType.TITLE: ContentType.HEADING,
            LayoutType.SECTION_HEADER: ContentType.HEADING,
            LayoutType.LIST: ContentType.LIST,
            LayoutType.TABLE: ContentType.TABLE,
            LayoutType.FIGURE: ContentType.FIGURE,
            LayoutType.HEADER: ContentType.HEADER,
            LayoutType.FOOTER: ContentType.FOOTER,
        }
        return mapping.get(layout_type, ContentType.PARAGRAPH)


# Singleton instance
_chunking_service: Optional[ChunkingService] = None


def get_chunking_service() -> ChunkingService:
    """Get chunking service singleton."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service
