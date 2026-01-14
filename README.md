<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Elasticsearch-9.2.4-yellow?style=for-the-badge&logo=elasticsearch" alt="Elasticsearch">
  <img src="https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<h1 align="center">🔍 DocuLens AI</h1>

<p align="center">
  <strong>High-accuracy document AI parser with OCR, table extraction, and 22+ Indian language support</strong>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-architecture">Architecture</a>
</p>

---

## ✨ Features

### 🔤 Multi-Language OCR (22+ Indian Languages)

Powered by **PaddleOCR** with state-of-the-art accuracy:

| Status | Languages |
|--------|-----------|
| **Full Support** | English, Hindi, Bengali, Telugu, Marathi, Tamil, Gujarati, Kannada, Malayalam, Punjabi, Urdu, Nepali |
| **Fallback Support** | Odia, Assamese, Sanskrit, Konkani, Maithili, Dogri, Sindhi, Kashmiri, Manipuri, Bodo |

**Automatic script detection** for Devanagari, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Gurmukhi, and Arabic scripts.

---

### 📊 Intelligent Table Extraction

Uses **Camelot** for 99%+ accuracy on PDF tables:

- **Lattice mode**: Tables with visible borders/lines
- **Stream mode**: Whitespace-separated tables
- Outputs as JSON or structured dictionaries
- Confidence scoring per table

---

### 🔗 Smart Chunking with Bidirectional Linkage

Every chunk maintains context awareness for RAG applications:

```json
{
  "chunk_id": "chunk_abc123",
  "prev_chunk_id": "chunk_xyz789",
  "next_chunk_id": "chunk_def456",
  "parent_section": "Chapter 1: Introduction",
  "section_hierarchy": ["Document", "Chapter 1", "Section 1.1"],
  "sibling_chunks": ["chunk_111", "chunk_222"],
  "is_continuation": true,
  "continues_to_next": true
}
```

**Three chunking strategies:**
- **Semantic**: By paragraphs and sections
- **Fixed-size**: With configurable overlap (default 10%)
- **Layout-aware**: Respects headers, tables, figures

---

### 🔑 Key-Value Pair Extraction

Extracts structured data with patterns in **22+ languages**:

| Category | Fields |
|----------|--------|
| **Common** | Name, Date, Address, Phone, Email, Amount, Age, Gender |
| **Legal (India)** | Case Number, Court, Judge, Petitioner, Respondent, FIR, Section, Police Station, District, State |
| **Hindi Examples** | नाम, पता, तारीख, न्यायालय, याचिकाकर्ता |
| **Bengali Examples** | নাম, ঠিকানা, তারিখ, আদালত |

---

### 📎 Embedded PDF Data Extraction

Extracts hidden metadata and embedded content:

| Data Type | Description |
|-----------|-------------|
| **Hyperlinks** | URLs, mailto:, tel: links with anchor text |
| **Email Addresses** | From links AND text (regex-based) |
| **Phone Numbers** | Indian format (+91) and international |
| **Annotations** | Comments, highlights, notes with author info |
| **Table of Contents** | PDF bookmark structure |
| **Form Fields** | Interactive PDF form values |
| **PDF Metadata** | Title, Author, Creator, Keywords |

---

### 🔍 Elasticsearch-Powered Search

Full-text search with:
- Fuzzy matching for typos
- Highlighting of matched terms
- Faceted filtering (language, document type, state)
- Chunk-level search with context retrieval

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- 4GB+ RAM (8GB recommended for large documents)
- (Optional) NVIDIA GPU for faster OCR

### 1. Clone the Repository

```bash
git clone https://github.com/ShreyashDarade/Doculens-AI.git
cd Doculens-AI
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env to customize settings
```

### 3. Start Services

```bash
docker-compose up -d
```

Wait for Elasticsearch to be ready:

```bash
# Check health
curl http://localhost:9200/_cluster/health?pretty

# Check API
curl http://localhost:8000/api/v1/health
```

### 4. Upload Your First Document

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@your_document.pdf" \
  -F "language=en"
```

### 5. Access the API

- **API Docs**: http://localhost:8000/docs
- **Elasticsearch**: http://localhost:9200

---

## 📖 API Reference

### Document Upload

```bash
POST /api/v1/documents/upload
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | File | Required | PDF or image file |
| `language` | string | `en` | OCR language code |
| `chunking_strategy` | string | `semantic` | `semantic`, `fixed`, `layout` |

**Response:**
```json
{
  "document_id": "doc_abc123",
  "filename": "contract.pdf",
  "status": "processed",
  "page_count": 15,
  "chunk_count": 42,
  "processing_time_ms": 3500,
  "key_value_pairs_count": 18,
  "tables_count": 3,
  "links_count": 12,
  "emails_count": 5
}
```

---

### Get Document Chunks

```bash
GET /api/v1/documents/{document_id}/chunks?page=1&size=50
```

Returns chunks with full linkage for context-aware retrieval.

---

### Get Key-Value Pairs

```bash
GET /api/v1/documents/{document_id}/key-values
```

Returns all extracted structured data.

---

### Get Embedded Data

```bash
GET /api/v1/documents/{document_id}/embedded
```

Returns hyperlinks, emails, phone numbers, annotations, TOC, and form fields.

---

### Full-Text Search

```bash
POST /api/v1/search
Content-Type: application/json

{
  "query": "petitioner appeal",
  "page": 1,
  "size": 10,
  "filters": {
    "language_detected": "hi"
  }
}
```

---

### Get Chunk with Context

```bash
GET /api/v1/documents/{document_id}/chunk/{chunk_id}/context?window=2
```

Returns the target chunk plus surrounding chunks for RAG context.

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `ELASTICSEARCH_INDEX` | `documents` | Index name |
| `OCR_LANGUAGE` | `en` | Primary OCR language |
| `CHUNK_SIZE` | `512` | Max tokens per chunk |
| `CHUNK_OVERLAP` | `0.1` | Overlap ratio (10%) |
| `USE_GPU` | `false` | Enable GPU acceleration |
| `MAX_FILE_SIZE_MB` | `50` | Max upload size |

### Supported Language Codes

```
en, hi, bn, te, mr, ta, gu, kn, ml, pa, ur, ne,
or, as, sa, kok, mai, doi, sd, ks, mni, sat, brx
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Document Upload                          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PDF/Image Preprocessing                       │
│                        (PyMuPDF)                                 │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
┌─────────┐           ┌─────────────┐         ┌───────────┐
│   OCR   │           │   Layout    │         │  Embedded │
│PaddleOCR│           │  Detection  │         │   Data    │
└────┬────┘           └──────┬──────┘         └─────┬─────┘
     │                       │                      │
     └───────────────────────┼──────────────────────┘
                             ▼
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
┌─────────┐           ┌─────────────┐         ┌───────────┐
│  Table  │           │   Smart     │         │ Key-Value │
│Camelot  │           │  Chunking   │         │ Extraction│
└────┬────┘           └──────┬──────┘         └─────┬─────┘
     │                       │                      │
     └───────────────────────┼──────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Elasticsearch Storage                       │
│                    (Rich Metadata + Chunks)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
doculens-ai/
├── docker-compose.yml      # Elasticsearch + FastAPI
├── Dockerfile             # Python 3.10 + dependencies
├── requirements.txt       # Python packages
├── .env.example          # Configuration template
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Settings management
│   ├── models/           # Pydantic models
│   ├── services/
│   │   ├── ocr_service.py         # PaddleOCR integration
│   │   ├── layout_service.py      # Layout detection
│   │   ├── table_service.py       # Camelot tables
│   │   ├── chunking_service.py    # Smart chunking
│   │   ├── kv_extraction.py       # Key-value extraction
│   │   ├── metadata_service.py    # Embedded data extraction
│   │   └── elasticsearch_service.py
│   ├── pipeline/
│   │   └── document_pipeline.py   # Main orchestrator
│   └── api/
│       └── routes.py             # REST endpoints
└── postman/
    └── DocuLens_AI.postman_collection.json
```

---

## 🧪 Testing

Import the Postman collection for ready-to-use API requests:

```bash
postman/DocuLens_AI.postman_collection.json
```

---

## 🔧 Development

### Local Setup (Without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Start Elasticsearch separately
docker run -d -p 9200:9200 -e "discovery.type=single-node" elasticsearch:9.2.4

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - Multi-language OCR
- [Camelot](https://github.com/camelot-dev/camelot) - Table extraction
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF processing
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python API framework
- [Elasticsearch](https://www.elastic.co/) - Search and storage

---

<p align="center">
  Made with ❤️ for Indian Document Processing
</p>
