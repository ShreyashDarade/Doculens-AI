<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Elasticsearch-9.2.4-yellow?style=for-the-badge&logo=elasticsearch" alt="Elasticsearch">
  <img src="https://img.shields.io/badge/PaddleOCR-3.x-orange?style=for-the-badge" alt="PaddleOCR">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<h1 align="center">🔍 DocuLens AI</h1>

<p align="center">
  <strong>High-accuracy Document AI Parser with 22+ Indian Language OCR</strong>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api">API</a> •
  <a href="#-features">Features</a> •
  <a href="#-languages">Languages</a>
</p>

---

## 🚀 Quick Start

### 1. Start Services

```bash
# Clone
git clone https://github.com/ShreyashDarade/Doculens-AI.git
cd Doculens-AI

# Start Elasticsearch (Docker)
docker run -d --name elasticsearch -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:9.2.4

# Install dependencies
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install paddlepaddle

# Configure
copy .env.example .env

# Run
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Parse a Document

```bash
curl -X POST "http://localhost:8000/api/v1/parse" \
  -F "file=@document.pdf" \
  -F "language=en"
```

### 3. View API Docs

Open: **http://localhost:8000/docs**

---

## 🔥 API

### `POST /api/v1/parse` — Main Endpoint

Upload a document and get complete parsed output in one response.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `file` | File | Required | PDF, PNG, JPG, TIFF, BMP |
| `language` | string | `en` | OCR language code |
| `chunking_strategy` | string | `semantic` | `semantic`, `fixed`, `layout` |
| `include_raw_text` | bool | `true` | Include full extracted text |
| `include_chunks` | bool | `true` | Include smart chunks |
| `store_in_elasticsearch` | bool | `false` | Store for later search |

**Response:**

```json
{
  "status": "success",
  "document_id": "doc_abc123",
  "processing_time_ms": 3500,
  
  "document_info": {
    "page_count": 5,
    "file_type": "pdf",
    "language_detected": "en"
  },
  
  "key_value_pairs": [
    {"key": "Name", "value": "John Doe", "confidence": 0.95},
    {"key": "Date", "value": "14-01-2026", "confidence": 0.92}
  ],
  
  "tables": [
    {"table_id": "...", "rows": 5, "cols": 3, "data": [...]}
  ],
  
  "embedded_data": {
    "links": [{"url": "https://...", "text": "click here"}],
    "emails": [{"email": "info@example.com"}],
    "phone_numbers": [{"number": "+919876543210"}],
    "annotations": [{"type": "Comment", "content": "..."}]
  },
  
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "content": "...",
      "prev_chunk_id": null,
      "next_chunk_id": "chunk_002",
      "section_hierarchy": ["Chapter 1", "Section 1.1"]
    }
  ],
  
  "raw_text": "Full extracted text..."
}
```

### Other Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/search` | POST | Search stored documents |
| `/api/v1/languages` | GET | List supported languages |

---

## ✨ Features

### 📄 Document Parsing
- **OCR**: PaddleOCR v5 with 22+ Indian languages
- **Tables**: Camelot extraction with 99%+ accuracy
- **Key-Value Pairs**: Regex patterns for common & legal fields
- **Embedded Data**: Links, emails, phones, annotations, TOC

### 🔗 Smart Chunking
- **Semantic**: By paragraphs and sections
- **Fixed**: 512 tokens with 10% overlap
- **Layout-aware**: Respects headers, tables, figures
- **Bidirectional Linkage**: `prev_chunk_id`, `next_chunk_id`, `section_hierarchy`

### 🔍 Search (Optional)
- Elasticsearch-powered full-text search
- Fuzzy matching, highlighting
- Enable with `store_in_elasticsearch=true`

---

## 🌐 Supported Languages

| Status | Languages |
|--------|-----------|
| **Full** | English, Hindi, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Nepali |
| **Fallback** | Odia→Telugu, Assamese→Bengali, Sanskrit→Hindi, Konkani→Marathi, Maithili→Hindi, Dogri→Hindi, Sindhi→Urdu, Kashmiri→Urdu, Manipuri→Bengali |

```bash
# Hindi document
curl -X POST "http://localhost:8000/api/v1/parse" -F "file=@doc.pdf" -F "language=hi"

# Tamil document  
curl -X POST "http://localhost:8000/api/v1/parse" -F "file=@doc.pdf" -F "language=ta"
```

---

## 📁 Project Structure

```
doculens-ai/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings
│   ├── api/routes.py           # API endpoints
│   ├── pipeline/               # Document pipeline
│   └── services/
│       ├── ocr_service.py      # PaddleOCR
│       ├── table_service.py    # Camelot
│       ├── kv_extraction.py    # Key-value extraction
│       ├── chunking_service.py # Smart chunking
│       └── metadata_service.py # Embedded data
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── postman/                    # API collection
```

---

## ⚙️ Configuration

```env
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=documents
OCR_LANGUAGE=en
CHUNK_SIZE=512
CHUNK_OVERLAP=0.1
```

---

## 📄 License

MIT License

---

<p align="center">Made with ❤️ for Indian Document Processing</p>
