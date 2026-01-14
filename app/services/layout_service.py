"""Document AI Parser - Layout Detection Service"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from PIL import Image

from app.models.document import BoundingBox, ContentType

logger = logging.getLogger(__name__)


class LayoutType(str, Enum):
    """Types of layout elements detected."""
    TEXT = "text"
    TITLE = "title"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    HEADER = "header"
    FOOTER = "footer"
    SECTION_HEADER = "section_header"


@dataclass
class LayoutElement:
    """Detected layout element."""
    element_type: LayoutType
    bounding_box: BoundingBox
    confidence: float
    text: Optional[str] = None
    order: int = 0


class LayoutService:
    """
    Layout detection service.
    
    Uses heuristics-based approach for layout detection.
    Can be extended to use LayoutParser with deep learning models.
    """
    
    def __init__(self):
        self._model = None
        
    def detect_layout(
        self,
        page_image: np.ndarray | Image.Image,
        text_blocks: List[Dict[str, Any]]
    ) -> List[LayoutElement]:
        """
        Detect layout elements from page image and OCR results.
        
        Args:
            page_image: Page image as numpy array or PIL Image
            text_blocks: OCR extracted text blocks with bounding boxes
            
        Returns:
            List of detected layout elements
        """
        if isinstance(page_image, np.ndarray):
            page_height, page_width = page_image.shape[:2]
        else:
            page_width, page_height = page_image.size
        
        layout_elements = []
        
        for idx, block in enumerate(text_blocks):
            bbox = block["bounding_box"]
            text = block["text"]
            confidence = block["confidence"]
            
            # Classify based on position and characteristics
            element_type = self._classify_element(
                text, bbox, page_width, page_height, idx, len(text_blocks)
            )
            
            layout_elements.append(LayoutElement(
                element_type=element_type,
                bounding_box=bbox,
                confidence=confidence,
                text=text,
                order=idx
            ))
        
        # Sort by reading order (top to bottom, left to right)
        layout_elements.sort(key=lambda e: (e.bounding_box.y, e.bounding_box.x))
        
        # Update order after sorting
        for idx, elem in enumerate(layout_elements):
            elem.order = idx
        
        return layout_elements
    
    def _classify_element(
        self,
        text: str,
        bbox: BoundingBox,
        page_width: float,
        page_height: float,
        block_idx: int,
        total_blocks: int
    ) -> LayoutType:
        """Classify a text block based on heuristics."""
        
        # Check if header (top 10% of page)
        if bbox.y < page_height * 0.10:
            if len(text) < 100:
                return LayoutType.HEADER
        
        # Check if footer (bottom 10% of page)
        if bbox.y + bbox.height > page_height * 0.90:
            if len(text) < 100:
                return LayoutType.FOOTER
        
        # Check if title (large text, usually at top, short)
        if block_idx < 5 and len(text) < 150:
            if bbox.height > page_height * 0.03:  # Larger than average text
                return LayoutType.TITLE
        
        # Check if section header
        if self._is_section_header(text):
            return LayoutType.SECTION_HEADER
        
        # Check if list item
        if self._is_list_item(text):
            return LayoutType.LIST
        
        # Default to text
        return LayoutType.TEXT
    
    def _is_section_header(self, text: str) -> bool:
        """Check if text is a section header."""
        text = text.strip()
        
        # Numbered sections
        if any(text.startswith(f"{i}.") or text.startswith(f"{i})") for i in range(1, 100)):
            if len(text) < 100 and text.isupper() or text.istitle():
                return True
        
        # Common header patterns
        header_patterns = [
            "CHAPTER", "SECTION", "ARTICLE", "PART",
            "ORDER", "JUDGMENT", "PETITION", "PRAYER",
            "अध्याय", "धारा", "खंड",  # Hindi
        ]
        
        for pattern in header_patterns:
            if text.upper().startswith(pattern):
                return True
        
        # Short uppercase text
        if len(text) < 80 and text.isupper():
            return True
        
        return False
    
    def _is_list_item(self, text: str) -> bool:
        """Check if text is a list item."""
        text = text.strip()
        
        # Bullet points
        if text.startswith(("•", "-", "–", "—", "*", "○", "●")):
            return True
        
        # Numbered lists
        if any(text.startswith(f"{i}.") or text.startswith(f"({i})") or text.startswith(f"{i})") 
               for i in range(1, 100)):
            return True
        
        # Lettered lists
        if any(text.startswith(f"{c}.") or text.startswith(f"({c})") or text.startswith(f"{c})")
               for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            return True
        
        return False
    
    def detect_tables_regions(
        self,
        page_image: np.ndarray | Image.Image,
        layout_elements: List[LayoutElement]
    ) -> List[BoundingBox]:
        """
        Detect potential table regions in the page.
        Returns bounding boxes of detected table regions.
        """
        # Simple heuristic: look for grid-like patterns
        # This is a placeholder - real implementation would use deep learning
        return []
    
    def map_to_content_type(self, layout_type: LayoutType) -> ContentType:
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
_layout_service: Optional[LayoutService] = None


def get_layout_service() -> LayoutService:
    """Get layout service singleton."""
    global _layout_service
    if _layout_service is None:
        _layout_service = LayoutService()
    return _layout_service
