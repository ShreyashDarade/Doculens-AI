"""Document AI Parser - FastAPI Main Application"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import router
from app.services.elasticsearch_service import get_elasticsearch_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Document AI Parser...")
    
    # Ensure Elasticsearch index exists
    es_service = get_elasticsearch_service()
    if es_service.is_healthy():
        es_service.ensure_index()
        logger.info("Elasticsearch connected and index ready")
    else:
        logger.warning("Elasticsearch not available - some features may not work")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Document AI Parser...")


# Create FastAPI application
app = FastAPI(
    title="Document AI Parser",
    description="""
    High-end document AI parser with OCR, table extraction, and Elasticsearch storage.
    
    ## Features
    
    * **Multi-language OCR**: PaddleOCR with support for English, Hindi, and other Indian languages
    * **Layout Detection**: Automatic detection of headings, paragraphs, tables, lists
    * **Table Extraction**: High-accuracy table extraction using Camelot
    * **Key-Value Extraction**: Extract structured data from documents
    * **Smart Chunking**: Semantic, fixed-size, or layout-aware chunking with bidirectional linkage
    * **Full-Text Search**: Elasticsearch-powered search with highlighting
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Document AI Parser",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
