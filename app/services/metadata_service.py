"""Document AI Parser - PDF Metadata & Embedded Data Extraction Service"""
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class EmbeddedLink:
    """Embedded hyperlink in PDF."""
    url: str
    link_type: str  # "uri", "goto", "email", "phone"
    page_number: int
    text: Optional[str] = None
    rect: Optional[Dict[str, float]] = None


@dataclass
class EmbeddedEmail:
    """Embedded email address."""
    email: str
    source: str  # "link", "text", "annotation"
    page_number: int
    context: Optional[str] = None


@dataclass
class PDFAnnotation:
    """PDF annotation/comment."""
    annotation_type: str
    content: str
    page_number: int
    author: Optional[str] = None
    created: Optional[datetime] = None
    rect: Optional[Dict[str, float]] = None


@dataclass
class PDFMetadata:
    """Full PDF metadata."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    file_size_bytes: int = 0
    is_encrypted: bool = False
    has_forms: bool = False
    has_toc: bool = False


@dataclass
class EmbeddedData:
    """All embedded data extracted from PDF."""
    metadata: PDFMetadata
    links: List[EmbeddedLink] = field(default_factory=list)
    emails: List[EmbeddedEmail] = field(default_factory=list)
    phone_numbers: List[Dict[str, Any]] = field(default_factory=list)
    annotations: List[PDFAnnotation] = field(default_factory=list)
    table_of_contents: List[Dict[str, Any]] = field(default_factory=list)
    bookmarks: List[Dict[str, Any]] = field(default_factory=list)
    form_fields: List[Dict[str, Any]] = field(default_factory=list)
    images_info: List[Dict[str, Any]] = field(default_factory=list)


class PDFMetadataService:
    """
    Service to extract embedded data from PDFs.
    
    Extracts:
    - Hyperlinks (URLs, mailto, phone)
    - Email addresses (from links and text)
    - Phone numbers
    - Annotations/Comments
    - Document metadata
    - Table of contents
    - Form fields
    - Bookmarks
    - Image information
    """
    
    # Regex patterns
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        re.IGNORECASE
    )
    
    PHONE_PATTERN = re.compile(
        r'(?:\+91[\s-]?)?(?:\d{5}[\s-]?\d{5}|\d{10}|\d{4}[\s-]?\d{3}[\s-]?\d{3}|\d{3}[\s-]?\d{3}[\s-]?\d{4})',
        re.IGNORECASE
    )
    
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )
    
    def extract_all(self, pdf_path: str | Path) -> EmbeddedData:
        """
        Extract all embedded data from a PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            EmbeddedData with all extracted information
        """
        pdf_path = Path(pdf_path)
        
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            return EmbeddedData(metadata=PDFMetadata())
        
        try:
            # Extract metadata
            metadata = self._extract_metadata(doc, pdf_path)
            
            # Extract links, emails, phones
            links, emails, phones = self._extract_links_and_contacts(doc)
            
            # Extract annotations
            annotations = self._extract_annotations(doc)
            
            # Extract TOC
            toc = self._extract_toc(doc)
            
            # Extract form fields
            form_fields = self._extract_form_fields(doc)
            
            # Extract image info
            images_info = self._extract_images_info(doc)
            
            return EmbeddedData(
                metadata=metadata,
                links=links,
                emails=emails,
                phone_numbers=phones,
                annotations=annotations,
                table_of_contents=toc,
                form_fields=form_fields,
                images_info=images_info,
            )
            
        finally:
            doc.close()
    
    def _extract_metadata(self, doc: fitz.Document, pdf_path: Path) -> PDFMetadata:
        """Extract PDF document metadata."""
        meta = doc.metadata
        
        # Parse dates
        creation_date = None
        mod_date = None
        
        if meta.get("creationDate"):
            creation_date = self._parse_pdf_date(meta["creationDate"])
        if meta.get("modDate"):
            mod_date = self._parse_pdf_date(meta["modDate"])
        
        return PDFMetadata(
            title=meta.get("title"),
            author=meta.get("author"),
            subject=meta.get("subject"),
            keywords=meta.get("keywords"),
            creator=meta.get("creator"),
            producer=meta.get("producer"),
            creation_date=creation_date,
            modification_date=mod_date,
            page_count=len(doc),
            file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
            is_encrypted=doc.is_encrypted,
            has_forms=doc.is_form_pdf,
            has_toc=len(doc.get_toc()) > 0,
        )
    
    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """Parse PDF date string (D:YYYYMMDDHHmmSS format)."""
        try:
            if date_str.startswith("D:"):
                date_str = date_str[2:]
            # Take first 14 characters (YYYYMMDDHHmmSS)
            date_str = date_str[:14].ljust(14, '0')
            return datetime.strptime(date_str, "%Y%m%d%H%M%S")
        except Exception:
            return None
    
    def _extract_links_and_contacts(
        self, doc: fitz.Document
    ) -> tuple[List[EmbeddedLink], List[EmbeddedEmail], List[Dict]]:
        """Extract hyperlinks, email addresses, and phone numbers."""
        links = []
        emails = []
        phones = []
        seen_emails = set()
        seen_phones = set()
        seen_urls = set()
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_number = page_num + 1
            
            # Extract links from PDF link annotations
            for link in page.get_links():
                link_type = link.get("kind", 0)
                uri = link.get("uri", "")
                
                # Get text at link location
                rect = link.get("from")
                link_text = None
                if rect:
                    try:
                        link_text = page.get_text("text", clip=rect).strip()
                    except:
                        pass
                
                rect_dict = None
                if rect:
                    rect_dict = {
                        "x": rect.x0,
                        "y": rect.y0,
                        "width": rect.x1 - rect.x0,
                        "height": rect.y1 - rect.y0,
                    }
                
                if uri:
                    # Email link
                    if uri.startswith("mailto:"):
                        email = uri[7:].split("?")[0]  # Remove mailto: and query params
                        if email and email not in seen_emails:
                            seen_emails.add(email)
                            emails.append(EmbeddedEmail(
                                email=email,
                                source="link",
                                page_number=page_number,
                                context=link_text
                            ))
                            links.append(EmbeddedLink(
                                url=uri,
                                link_type="email",
                                page_number=page_number,
                                text=link_text,
                                rect=rect_dict
                            ))
                    
                    # Phone link
                    elif uri.startswith("tel:"):
                        phone = uri[4:]
                        if phone and phone not in seen_phones:
                            seen_phones.add(phone)
                            phones.append({
                                "number": phone,
                                "source": "link",
                                "page_number": page_number,
                                "context": link_text
                            })
                            links.append(EmbeddedLink(
                                url=uri,
                                link_type="phone",
                                page_number=page_number,
                                text=link_text,
                                rect=rect_dict
                            ))
                    
                    # Regular URL
                    elif uri.startswith(("http://", "https://")):
                        if uri not in seen_urls:
                            seen_urls.add(uri)
                            links.append(EmbeddedLink(
                                url=uri,
                                link_type="uri",
                                page_number=page_number,
                                text=link_text,
                                rect=rect_dict
                            ))
                    
                    # Other links (internal, file, etc.)
                    else:
                        links.append(EmbeddedLink(
                            url=uri,
                            link_type="other",
                            page_number=page_number,
                            text=link_text,
                            rect=rect_dict
                        ))
            
            # Extract emails and phones from page text
            page_text = page.get_text("text")
            
            # Find emails in text
            for match in self.EMAIL_PATTERN.finditer(page_text):
                email = match.group(0)
                if email not in seen_emails:
                    seen_emails.add(email)
                    # Get surrounding context
                    start = max(0, match.start() - 30)
                    end = min(len(page_text), match.end() + 30)
                    context = page_text[start:end].strip()
                    
                    emails.append(EmbeddedEmail(
                        email=email,
                        source="text",
                        page_number=page_number,
                        context=context
                    ))
            
            # Find phone numbers in text
            for match in self.PHONE_PATTERN.finditer(page_text):
                phone = match.group(0)
                normalized = re.sub(r'[\s-]', '', phone)
                if len(normalized) >= 10 and normalized not in seen_phones:
                    seen_phones.add(normalized)
                    start = max(0, match.start() - 30)
                    end = min(len(page_text), match.end() + 30)
                    context = page_text[start:end].strip()
                    
                    phones.append({
                        "number": phone,
                        "normalized": normalized,
                        "source": "text",
                        "page_number": page_number,
                        "context": context
                    })
            
            # Find URLs in text that might not be links
            for match in self.URL_PATTERN.finditer(page_text):
                url = match.group(0)
                if url not in seen_urls:
                    seen_urls.add(url)
                    links.append(EmbeddedLink(
                        url=url,
                        link_type="uri",
                        page_number=page_number,
                        text=None,
                        rect=None
                    ))
        
        return links, emails, phones
    
    def _extract_annotations(self, doc: fitz.Document) -> List[PDFAnnotation]:
        """Extract PDF annotations/comments."""
        annotations = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            for annot in page.annots() or []:
                annot_type = annot.type[1] if annot.type else "Unknown"
                
                # Get annotation content
                content = annot.info.get("content", "") or ""
                
                # Skip if no content
                if not content.strip():
                    continue
                
                rect = annot.rect
                rect_dict = {
                    "x": rect.x0,
                    "y": rect.y0,
                    "width": rect.x1 - rect.x0,
                    "height": rect.y1 - rect.y0,
                } if rect else None
                
                # Parse creation date
                created = None
                if annot.info.get("creationDate"):
                    created = self._parse_pdf_date(annot.info["creationDate"])
                
                annotations.append(PDFAnnotation(
                    annotation_type=annot_type,
                    content=content,
                    page_number=page_num + 1,
                    author=annot.info.get("title"),  # 'title' is often author in annotations
                    created=created,
                    rect=rect_dict
                ))
        
        return annotations
    
    def _extract_toc(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract table of contents."""
        toc = doc.get_toc()
        return [
            {
                "level": item[0],
                "title": item[1],
                "page_number": item[2],
            }
            for item in toc
        ]
    
    def _extract_form_fields(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract form field values."""
        form_fields = []
        
        if not doc.is_form_pdf:
            return form_fields
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            for widget in page.widgets() or []:
                field = {
                    "name": widget.field_name,
                    "type": widget.field_type_string,
                    "value": widget.field_value,
                    "page_number": page_num + 1,
                }
                
                # Add additional info for specific types
                if widget.field_type_string == "CheckBox":
                    field["checked"] = widget.field_value == "Yes"
                elif widget.field_type_string == "ComboBox":
                    field["options"] = widget.choice_values
                
                form_fields.append(field)
        
        return form_fields
    
    def _extract_images_info(self, doc: fitz.Document) -> List[Dict[str, Any]]:
        """Extract information about embedded images."""
        images_info = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                width = img[2]
                height = img[3]
                
                images_info.append({
                    "page_number": page_num + 1,
                    "image_index": img_index,
                    "xref": xref,
                    "width": width,
                    "height": height,
                    "colorspace": img[4],
                })
        
        return images_info
    
    def extract_to_dict(self, pdf_path: str | Path) -> Dict[str, Any]:
        """Extract all data and return as dictionary."""
        data = self.extract_all(pdf_path)
        
        return {
            "metadata": {
                "title": data.metadata.title,
                "author": data.metadata.author,
                "subject": data.metadata.subject,
                "keywords": data.metadata.keywords,
                "creator": data.metadata.creator,
                "producer": data.metadata.producer,
                "creation_date": data.metadata.creation_date.isoformat() if data.metadata.creation_date else None,
                "modification_date": data.metadata.modification_date.isoformat() if data.metadata.modification_date else None,
                "page_count": data.metadata.page_count,
                "file_size_bytes": data.metadata.file_size_bytes,
                "is_encrypted": data.metadata.is_encrypted,
                "has_forms": data.metadata.has_forms,
                "has_toc": data.metadata.has_toc,
            },
            "links": [
                {
                    "url": link.url,
                    "type": link.link_type,
                    "page_number": link.page_number,
                    "text": link.text,
                    "rect": link.rect,
                }
                for link in data.links
            ],
            "emails": [
                {
                    "email": email.email,
                    "source": email.source,
                    "page_number": email.page_number,
                    "context": email.context,
                }
                for email in data.emails
            ],
            "phone_numbers": data.phone_numbers,
            "annotations": [
                {
                    "type": annot.annotation_type,
                    "content": annot.content,
                    "page_number": annot.page_number,
                    "author": annot.author,
                    "created": annot.created.isoformat() if annot.created else None,
                }
                for annot in data.annotations
            ],
            "table_of_contents": data.table_of_contents,
            "form_fields": data.form_fields,
            "images_info": data.images_info,
        }


# Singleton instance
_pdf_metadata_service: Optional[PDFMetadataService] = None


def get_pdf_metadata_service() -> PDFMetadataService:
    """Get PDF metadata service singleton."""
    global _pdf_metadata_service
    if _pdf_metadata_service is None:
        _pdf_metadata_service = PDFMetadataService()
    return _pdf_metadata_service
