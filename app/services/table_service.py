"""Document AI Parser - Table Extraction Service using Camelot"""
import logging
from typing import List, Optional
from pathlib import Path
import tempfile
import uuid

from app.models.document import ExtractedTable, TableCell, BoundingBox

logger = logging.getLogger(__name__)

# Try to import camelot - it's optional
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("Camelot not available. Table extraction will be limited.")


class TableService:
    """
    Table extraction service using Camelot.
    
    Supports both lattice (tables with lines) and stream (whitespace-separated) modes.
    """
    
    def __init__(self):
        self.camelot_available = CAMELOT_AVAILABLE
    
    def extract_tables_from_pdf(
        self,
        pdf_path: str | Path,
        pages: str = "all",
        flavor: str = "lattice"
    ) -> List[ExtractedTable]:
        """
        Extract tables from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            pages: Pages to process ("all", "1", "1,2,3", "1-3")
            flavor: "lattice" for tables with lines, "stream" for whitespace-separated
            
        Returns:
            List of extracted tables
        """
        if not self.camelot_available:
            logger.warning("Camelot not available. Returning empty tables.")
            return []
        
        pdf_path = str(pdf_path)
        extracted_tables = []
        
        try:
            # Try lattice first (tables with clear lines)
            tables = camelot.read_pdf(
                pdf_path,
                pages=pages,
                flavor=flavor,
                suppress_stdout=True
            )
            
            # If no tables found with lattice, try stream
            if len(tables) == 0 and flavor == "lattice":
                tables = camelot.read_pdf(
                    pdf_path,
                    pages=pages,
                    flavor="stream",
                    suppress_stdout=True
                )
            
            for idx, table in enumerate(tables):
                extracted_table = self._convert_camelot_table(table, idx)
                if extracted_table:
                    extracted_tables.append(extracted_table)
                    
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
        
        return extracted_tables
    
    def _convert_camelot_table(self, table, table_idx: int) -> Optional[ExtractedTable]:
        """Convert a Camelot table to our ExtractedTable model."""
        try:
            df = table.df
            
            if df.empty:
                return None
            
            rows, cols = df.shape
            cells = []
            
            for row_idx in range(rows):
                for col_idx in range(cols):
                    cell_value = str(df.iloc[row_idx, col_idx])
                    cells.append(TableCell(
                        row=row_idx,
                        col=col_idx,
                        text=cell_value.strip()
                    ))
            
            # Extract headers (first row)
            headers = [str(df.iloc[0, col]).strip() for col in range(cols)]
            
            # Convert to list of dicts (assuming first row is header)
            data_as_dict = []
            if rows > 1:
                for row_idx in range(1, rows):
                    row_dict = {}
                    for col_idx, header in enumerate(headers):
                        row_dict[header] = str(df.iloc[row_idx, col_idx]).strip()
                    data_as_dict.append(row_dict)
            
            # Get parsing accuracy from Camelot
            accuracy = table.parsing_report.get("accuracy", 100) / 100.0
            
            return ExtractedTable(
                table_id=f"table_{uuid.uuid4().hex[:8]}",
                page_number=table.page,
                rows=rows,
                cols=cols,
                cells=cells,
                headers=headers,
                data_as_dict=data_as_dict,
                confidence=accuracy
            )
            
        except Exception as e:
            logger.error(f"Failed to convert table: {e}")
            return None
    
    def extract_tables_from_image(
        self,
        image_path: str | Path
    ) -> List[ExtractedTable]:
        """
        Extract tables from an image.
        
        Note: Camelot doesn't support images directly.
        This would require a different approach (Table Transformer, etc.)
        """
        logger.info("Image-based table extraction not yet implemented")
        return []


# Singleton instance
_table_service: Optional[TableService] = None


def get_table_service() -> TableService:
    """Get table service singleton."""
    global _table_service
    if _table_service is None:
        _table_service = TableService()
    return _table_service
