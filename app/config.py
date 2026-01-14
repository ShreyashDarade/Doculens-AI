"""Document AI Parser - Configuration"""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "documents"
    
    # OCR Configuration
    ocr_language: str = "en"
    use_gpu: bool = False
    
    # Chunking
    chunk_size: int = 512
    chunk_overlap: float = 0.1
    
    # Upload Settings
    max_file_size_mb: int = 50
    allowed_extensions: str = "pdf,png,jpg,jpeg,tiff,bmp"
    
    # Logging
    log_level: str = "INFO"
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]
    
    @property
    def ocr_languages_list(self) -> List[str]:
        return [lang.strip() for lang in self.ocr_language.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
