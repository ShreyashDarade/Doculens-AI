"""Document AI Parser - OCR Service using PaddleOCR with Full Indian Language Support"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import numpy as np
from PIL import Image

from paddleocr import PaddleOCR

from app.config import get_settings
from app.models.document import BoundingBox

logger = logging.getLogger(__name__)


# ============================================================================
# INDIAN LANGUAGE SUPPORT - PaddleOCR Language Codes & Fallbacks
# ============================================================================

# PaddleOCR supported languages for India
PADDLEOCR_LANGUAGES = {
    # Fully supported
    "en": "en",          # English
    "hi": "hi",          # Hindi (Devanagari)
    "mr": "mr",          # Marathi (Devanagari)
    "ne": "ne",          # Nepali (Devanagari)
    "ta": "ta",          # Tamil
    "te": "te",          # Telugu
    "kn": "kn",          # Kannada
    "ml": "ml",          # Malayalam (new in PP-OCRv5)
    "gu": "gu",          # Gujarati (new in PP-OCRv5)
    "pa": "pa",          # Punjabi (Gurmukhi) (new in PP-OCRv5)
    "bn": "bn",          # Bengali (new in PP-OCRv5)
    "ur": "ur",          # Urdu (Arabic script)
    
    # Fallback mappings for unsupported languages
    "sa": "hi",          # Sanskrit -> Hindi (both Devanagari)
    "kok": "mr",         # Konkani -> Marathi (Devanagari)
    "mai": "hi",         # Maithili -> Hindi (Devanagari)
    "doi": "hi",         # Dogri -> Hindi (Devanagari)
    "bho": "hi",         # Bhojpuri -> Hindi (Devanagari)
    "raj": "hi",         # Rajasthani -> Hindi (Devanagari)
    "or": "te",          # Odia -> Telugu (similar script family)
    "as": "bn",          # Assamese -> Bengali (same script)
    "mni": "bn",         # Manipuri (Bengali script) -> Bengali
    "sat": "en",         # Santali (Ol Chiki) -> English (no support)
    "ks": "ur",          # Kashmiri -> Urdu (Perso-Arabic)
    "sd": "ur",          # Sindhi -> Urdu (Arabic script)
    "brx": "hi",         # Bodo -> Hindi (Devanagari)
}

# Unicode ranges for Indian scripts - for language detection
SCRIPT_RANGES = {
    "devanagari": ('\u0900', '\u097F'),      # Hindi, Marathi, Nepali, Sanskrit
    "bengali": ('\u0980', '\u09FF'),          # Bengali, Assamese
    "gurmukhi": ('\u0A00', '\u0A7F'),         # Punjabi
    "gujarati": ('\u0A80', '\u0AFF'),         # Gujarati
    "oriya": ('\u0B00', '\u0B7F'),            # Odia
    "tamil": ('\u0B80', '\u0BFF'),            # Tamil
    "telugu": ('\u0C00', '\u0C7F'),           # Telugu
    "kannada": ('\u0C80', '\u0CFF'),          # Kannada
    "malayalam": ('\u0D00', '\u0D7F'),        # Malayalam
    "arabic": ('\u0600', '\u06FF'),           # Urdu, Sindhi, Kashmiri
    "extended_arabic": ('\u0750', '\u077F'),  # Extended Arabic
}

# Map scripts to primary languages
SCRIPT_TO_LANG = {
    "devanagari": "hi",
    "bengali": "bn",
    "gurmukhi": "pa",
    "gujarati": "gu",
    "oriya": "or",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
    "arabic": "ur",
    "extended_arabic": "ur",
}


class OCRService:
    """
    PaddleOCR-based text extraction service with full Indian language support.
    
    Supports 22+ Indian languages with intelligent fallbacks:
    - Direct support: Hindi, Marathi, Tamil, Telugu, Kannada, Malayalam, 
      Gujarati, Punjabi, Bengali, Urdu, Nepali
    - Fallback support: Sanskrit, Konkani, Maithili, Dogri, Odia, Assamese,
      Manipuri, Kashmiri, Sindhi, Santali, Bodo
    """
    
    def __init__(self):
        settings = get_settings()
        self._ocr_instances: Dict[str, PaddleOCR] = {}
        self.default_lang = settings.ocr_languages_list[0] if settings.ocr_languages_list else "en"
        self.use_gpu = settings.use_gpu
        self.language_map = PADDLEOCR_LANGUAGES
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of all supported languages with their status."""
        return [
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
            {"code": "brx", "name": "Bodo", "status": "fallback", "fallback_to": "hi"},
        ]
    
    def _resolve_language(self, lang: str) -> str:
        """Resolve language code to PaddleOCR supported code."""
        lang = lang.lower().strip()
        if lang in self.language_map:
            resolved = self.language_map[lang]
            if resolved != lang:
                logger.info(f"Language '{lang}' mapped to '{resolved}' (fallback)")
            return resolved
        return "en"  # Default fallback
    
    def _get_ocr(self, lang: str = "en") -> PaddleOCR:
        """Get or create PaddleOCR instance for a language."""
        resolved_lang = self._resolve_language(lang)
        
        if resolved_lang not in self._ocr_instances:
            logger.info(f"Initializing PaddleOCR for language: {resolved_lang}")
            self._ocr_instances[resolved_lang] = PaddleOCR(
                use_angle_cls=True,
                lang=resolved_lang,
                use_gpu=self.use_gpu,
                show_log=False,
            )
        return self._ocr_instances[resolved_lang]
    
    def extract_text_from_image(
        self, 
        image: np.ndarray | Image.Image | str | Path,
        lang: str = None
    ) -> List[Dict[str, Any]]:
        """
        Extract text from an image.
        
        Args:
            image: Image as numpy array, PIL Image, or file path
            lang: Language code (supports all 22 Indian languages)
        
        Returns list of text blocks with:
        - text: extracted text
        - confidence: OCR confidence score
        - bounding_box: location in image
        """
        lang = lang or self.default_lang
        ocr = self._get_ocr(lang)
        
        # Convert PIL Image to numpy if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
        elif isinstance(image, (str, Path)):
            image = np.array(Image.open(image))
        
        try:
            result = ocr.ocr(image, cls=True)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return []
        
        if not result or not result[0]:
            return []
        
        text_blocks = []
        for line in result[0]:
            bbox_points = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line[1][0]
            confidence = float(line[1][1])
            
            # Convert to simple bounding box
            x_coords = [p[0] for p in bbox_points]
            y_coords = [p[1] for p in bbox_points]
            
            bounding_box = BoundingBox(
                x=min(x_coords),
                y=min(y_coords),
                width=max(x_coords) - min(x_coords),
                height=max(y_coords) - min(y_coords)
            )
            
            text_blocks.append({
                "text": text,
                "confidence": confidence,
                "bounding_box": bounding_box,
                "bbox_points": bbox_points,
            })
        
        return text_blocks
    
    def extract_text_from_page(
        self,
        page_image: np.ndarray | Image.Image,
        lang: str = None
    ) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Extract all text from a page image.
        
        Returns:
        - full_text: concatenated text
        - avg_confidence: average confidence score
        - text_blocks: list of individual text blocks
        """
        text_blocks = self.extract_text_from_image(page_image, lang)
        
        if not text_blocks:
            return "", 0.0, []
        
        # Sort by Y position then X position (reading order)
        text_blocks.sort(key=lambda b: (b["bounding_box"].y, b["bounding_box"].x))
        
        full_text = "\n".join([b["text"] for b in text_blocks])
        avg_confidence = sum(b["confidence"] for b in text_blocks) / len(text_blocks)
        
        return full_text, avg_confidence, text_blocks
    
    def detect_language(self, text_blocks: List[Dict[str, Any]]) -> str:
        """
        Detect primary language from extracted text.
        
        Supports detection of all major Indian scripts.
        """
        full_text = " ".join([b["text"] for b in text_blocks])
        
        # Count characters by script
        script_counts = {}
        
        for script_name, (start, end) in SCRIPT_RANGES.items():
            count = sum(1 for c in full_text if start <= c <= end)
            if count > 0:
                script_counts[script_name] = count
        
        # Count Latin characters
        latin_count = sum(1 for c in full_text if 'a' <= c.lower() <= 'z')
        if latin_count > 0:
            script_counts["latin"] = latin_count
        
        if not script_counts:
            return "en"
        
        # Get dominant script
        dominant_script = max(script_counts, key=script_counts.get)
        
        if dominant_script == "latin":
            return "en"
        
        return SCRIPT_TO_LANG.get(dominant_script, "en")
    
    def detect_all_languages(self, text_blocks: List[Dict[str, Any]]) -> List[str]:
        """
        Detect all languages present in the text.
        
        Returns list of language codes found.
        """
        full_text = " ".join([b["text"] for b in text_blocks])
        detected = []
        
        # Check Latin
        latin_count = sum(1 for c in full_text if 'a' <= c.lower() <= 'z')
        if latin_count > 10:
            detected.append("en")
        
        # Check each Indic script
        for script_name, (start, end) in SCRIPT_RANGES.items():
            count = sum(1 for c in full_text if start <= c <= end)
            if count > 10:  # Threshold to avoid false positives
                lang = SCRIPT_TO_LANG.get(script_name)
                if lang and lang not in detected:
                    detected.append(lang)
        
        return detected if detected else ["en"]
    
    def extract_multilingual(
        self,
        page_image: np.ndarray | Image.Image,
        languages: List[str] = None
    ) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Extract text using multiple OCR passes for multilingual documents.
        
        Useful for documents with mixed Hindi-English or other combinations.
        """
        if languages is None:
            languages = ["en", "hi"]  # Default: English + Hindi
        
        all_blocks = []
        
        for lang in languages:
            text_blocks = self.extract_text_from_image(page_image, lang)
            all_blocks.extend(text_blocks)
        
        if not all_blocks:
            return "", 0.0, []
        
        # Deduplicate based on bounding box overlap
        unique_blocks = self._deduplicate_blocks(all_blocks)
        
        # Sort by reading order
        unique_blocks.sort(key=lambda b: (b["bounding_box"].y, b["bounding_box"].x))
        
        full_text = "\n".join([b["text"] for b in unique_blocks])
        avg_confidence = sum(b["confidence"] for b in unique_blocks) / len(unique_blocks)
        
        return full_text, avg_confidence, unique_blocks
    
    def _deduplicate_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate text blocks based on bounding box overlap."""
        if not blocks:
            return []
        
        unique = []
        for block in blocks:
            is_duplicate = False
            for existing in unique:
                if self._boxes_overlap(block["bounding_box"], existing["bounding_box"]):
                    # Keep the one with higher confidence
                    if block["confidence"] > existing["confidence"]:
                        unique.remove(existing)
                        unique.append(block)
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(block)
        
        return unique
    
    def _boxes_overlap(self, box1: BoundingBox, box2: BoundingBox, threshold: float = 0.5) -> bool:
        """Check if two bounding boxes overlap significantly."""
        x1 = max(box1.x, box2.x)
        y1 = max(box1.y, box2.y)
        x2 = min(box1.x + box1.width, box2.x + box2.width)
        y2 = min(box1.y + box1.height, box2.y + box2.height)
        
        if x2 < x1 or y2 < y1:
            return False
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = box1.width * box1.height
        area2 = box2.width * box2.height
        
        overlap_ratio = intersection / min(area1, area2) if min(area1, area2) > 0 else 0
        return overlap_ratio > threshold


# Singleton instance
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """Get OCR service singleton."""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
