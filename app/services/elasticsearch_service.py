"""Document AI Parser - Elasticsearch Service"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import NotFoundError

from app.config import get_settings
from app.models.document import (
    DocumentChunk, DocumentMetadata, ProcessedDocument,
    SearchRequest, SearchResult, SearchResponse
)

logger = logging.getLogger(__name__)


# Elasticsearch index mapping
INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop", "snowball"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            # Document metadata
            "document_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "file_type": {"type": "keyword"},
            "file_size_bytes": {"type": "long"},
            "page_count": {"type": "integer"},
            "upload_timestamp": {"type": "date"},
            "processing_time_ms": {"type": "long"},
            "language_detected": {"type": "keyword"},
            "languages": {"type": "keyword"},
            
            # Chunk data
            "chunk_id": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "chunk_total": {"type": "integer"},
            "page_number": {"type": "integer"},
            "content": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                }
            },
            "content_type": {"type": "keyword"},
            "confidence_score": {"type": "float"},
            
            # Bounding box
            "bounding_box": {
                "properties": {
                    "x": {"type": "float"},
                    "y": {"type": "float"},
                    "width": {"type": "float"},
                    "height": {"type": "float"}
                }
            },
            
            # Chunk linkage
            "prev_chunk_id": {"type": "keyword"},
            "next_chunk_id": {"type": "keyword"},
            "parent_section": {"type": "keyword"},
            "section_hierarchy": {"type": "keyword"},
            "sibling_chunks": {"type": "keyword"},
            "overlap_with_prev": {"type": "text"},
            "overlap_with_next": {"type": "text"},
            "is_continuation": {"type": "boolean"},
            "continues_to_next": {"type": "boolean"},
            
            # Document classification
            "document_category": {"type": "keyword"},
            "state": {"type": "keyword"},
            "has_handwriting": {"type": "boolean"},
            "has_stamps": {"type": "boolean"},
            "has_tables": {"type": "boolean"},
            
            # Extracted data
            "key_value_pairs": {
                "type": "nested",
                "properties": {
                    "key": {"type": "keyword"},
                    "value": {"type": "text"},
                    "confidence": {"type": "float"}
                }
            },
            "tables": {
                "type": "nested",
                "properties": {
                    "table_id": {"type": "keyword"},
                    "page_number": {"type": "integer"},
                    "rows": {"type": "integer"},
                    "cols": {"type": "integer"},
                    "headers": {"type": "keyword"},
                    "confidence": {"type": "float"}
                }
            }
        }
    }
}


class ElasticsearchService:
    """Elasticsearch storage and search service."""
    
    def __init__(self):
        settings = get_settings()
        self.es_url = settings.elasticsearch_url
        self.index_name = settings.elasticsearch_index
        self._client: Optional[Elasticsearch] = None
    
    @property
    def client(self) -> Elasticsearch:
        """Get or create Elasticsearch client."""
        if self._client is None:
            self._client = Elasticsearch(
                self.es_url,
                verify_certs=False,
                request_timeout=30
            )
        return self._client
    
    def is_healthy(self) -> bool:
        """Check if Elasticsearch is healthy."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False
    
    def ensure_index(self) -> bool:
        """Ensure the index exists with correct mapping."""
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(
                    index=self.index_name,
                    body=INDEX_MAPPING
                )
                logger.info(f"Created index: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    def index_document(self, processed_doc: ProcessedDocument) -> bool:
        """
        Index a processed document with all its chunks.
        
        Each chunk is stored as a separate document in Elasticsearch
        with shared metadata.
        """
        try:
            self.ensure_index()
            
            metadata = processed_doc.metadata
            actions = []
            
            for chunk in processed_doc.chunks:
                doc = {
                    # Metadata
                    "document_id": metadata.document_id,
                    "filename": metadata.filename,
                    "file_type": metadata.file_type,
                    "file_size_bytes": metadata.file_size_bytes,
                    "page_count": metadata.page_count,
                    "upload_timestamp": metadata.upload_timestamp.isoformat(),
                    "processing_time_ms": metadata.processing_time_ms,
                    "language_detected": metadata.language_detected,
                    "languages": metadata.languages,
                    
                    # Chunk data
                    "chunk_id": chunk.chunk_id,
                    "chunk_index": chunk.chunk_index,
                    "chunk_total": chunk.chunk_total,
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "content_type": chunk.content_type.value,
                    "confidence_score": chunk.confidence_score,
                    
                    # Bounding box
                    "bounding_box": chunk.bounding_box.model_dump() if chunk.bounding_box else None,
                    
                    # Chunk linkage
                    "prev_chunk_id": chunk.prev_chunk_id,
                    "next_chunk_id": chunk.next_chunk_id,
                    "parent_section": chunk.parent_section,
                    "section_hierarchy": chunk.section_hierarchy,
                    "sibling_chunks": chunk.sibling_chunks,
                    "overlap_with_prev": chunk.overlap_with_prev,
                    "overlap_with_next": chunk.overlap_with_next,
                    "is_continuation": chunk.is_continuation,
                    "continues_to_next": chunk.continues_to_next,
                    
                    # Classification
                    "document_category": metadata.document_category,
                    "state": metadata.state,
                    "has_handwriting": metadata.has_handwriting,
                    "has_stamps": metadata.has_stamps,
                    "has_tables": metadata.has_tables,
                    
                    # Key-value pairs (for first chunk only to avoid duplication)
                    "key_value_pairs": [
                        kv.model_dump() for kv in metadata.key_value_pairs
                    ] if chunk.chunk_index == 0 else [],
                    
                    # Tables
                    "tables": [
                        {
                            "table_id": t.table_id,
                            "page_number": t.page_number,
                            "rows": t.rows,
                            "cols": t.cols,
                            "headers": t.headers,
                            "confidence": t.confidence
                        }
                        for t in metadata.tables
                    ] if chunk.chunk_index == 0 else [],
                }
                
                actions.append({
                    "_index": self.index_name,
                    "_id": chunk.chunk_id,
                    "_source": doc
                })
            
            # Bulk index
            if actions:
                helpers.bulk(self.client, actions)
                logger.info(f"Indexed {len(actions)} chunks for document {metadata.document_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return False
    
    def get_document(self, document_id: str) -> Optional[DocumentMetadata]:
        """Get document metadata by ID."""
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"document_id": document_id}},
                                {"term": {"chunk_index": 0}}  # Get first chunk for metadata
                            ]
                        }
                    },
                    "size": 1
                }
            )
            
            hits = response["hits"]["hits"]
            if not hits:
                return None
            
            source = hits[0]["_source"]
            return DocumentMetadata(
                document_id=source["document_id"],
                filename=source["filename"],
                file_type=source["file_type"],
                file_size_bytes=source["file_size_bytes"],
                page_count=source["page_count"],
                upload_timestamp=datetime.fromisoformat(source["upload_timestamp"]),
                processing_time_ms=source["processing_time_ms"],
                language_detected=source.get("language_detected", "en"),
                languages=source.get("languages", []),
                document_category=source.get("document_category"),
                state=source.get("state"),
                has_handwriting=source.get("has_handwriting", False),
                has_stamps=source.get("has_stamps", False),
                has_tables=source.get("has_tables", False),
            )
            
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
    
    def get_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {"term": {"document_id": document_id}},
                    "sort": [{"chunk_index": "asc"}],
                    "size": 1000
                }
            )
            
            return [hit["_source"] for hit in response["hits"]["hits"]]
            
        except Exception as e:
            logger.error(f"Failed to get chunks: {e}")
            return []
    
    def get_key_values(self, document_id: str) -> List[Dict[str, Any]]:
        """Get key-value pairs for a document."""
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"document_id": document_id}},
                                {"term": {"chunk_index": 0}}
                            ]
                        }
                    },
                    "_source": ["key_value_pairs"],
                    "size": 1
                }
            )
            
            hits = response["hits"]["hits"]
            if hits:
                return hits[0]["_source"].get("key_value_pairs", [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get key-values: {e}")
            return []
    
    def get_tables(self, document_id: str) -> List[Dict[str, Any]]:
        """Get tables for a document."""
        try:
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"document_id": document_id}},
                                {"term": {"chunk_index": 0}}
                            ]
                        }
                    },
                    "_source": ["tables"],
                    "size": 1
                }
            )
            
            hits = response["hits"]["hits"]
            if hits:
                return hits[0]["_source"].get("tables", [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []
    
    def search(self, request: SearchRequest) -> SearchResponse:
        """Full-text search across documents."""
        try:
            must_clauses = [
                {
                    "multi_match": {
                        "query": request.query,
                        "fields": ["content^2", "filename", "key_value_pairs.value"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }
            ]
            
            if request.document_id:
                must_clauses.append({"term": {"document_id": request.document_id}})
            
            if request.filters:
                for key, value in request.filters.items():
                    must_clauses.append({"term": {key: value}})
            
            response = self.client.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"must": must_clauses}},
                    "highlight": {
                        "fields": {"content": {}},
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    },
                    "from": (request.page - 1) * request.size,
                    "size": request.size
                }
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                highlights = hit.get("highlight", {}).get("content", [])
                
                results.append(SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    filename=source["filename"],
                    content=source["content"][:500],
                    page_number=source["page_number"],
                    score=hit["_score"],
                    highlights=highlights,
                    prev_chunk_id=source.get("prev_chunk_id"),
                    next_chunk_id=source.get("next_chunk_id"),
                ))
            
            return SearchResponse(
                query=request.query,
                total=response["hits"]["total"]["value"],
                page=request.page,
                size=request.size,
                results=results
            )
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return SearchResponse(
                query=request.query,
                total=0,
                page=request.page,
                size=request.size,
                results=[]
            )
    
    def delete_document(self, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            self.client.delete_by_query(
                index=self.index_name,
                body={"query": {"term": {"document_id": document_id}}}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False


# Singleton instance
_es_service: Optional[ElasticsearchService] = None


def get_elasticsearch_service() -> ElasticsearchService:
    """Get Elasticsearch service singleton."""
    global _es_service
    if _es_service is None:
        _es_service = ElasticsearchService()
    return _es_service
