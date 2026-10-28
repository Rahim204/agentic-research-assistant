# Agentic Research Assistant

> A Multi-Agent LLM-RAG Framework for Autonomous Scientific Literature Mining, Research Gap Discovery, and Evidence-Grounded Knowledge Synthesis

![Pipeline](https://img.shields.io/badge/pipeline-7_agents-brand) ![Python](https://img.shields.io/badge/python-3.11+-blue) ![React](https://img.shields.io/badge/react-18-61dafb)

## Overview

The Agentic Research Assistant automatically retrieves scientific papers from arXiv and Semantic Scholar, routes them through a seven-agent pipeline, and produces a fully structured, citation-grounded literature review — all from a single research query.

### Agent Pipeline

```
Search → Classify → Summarize → Extract → Gap Discovery → Synthesize → Cite
```

| Agent | Task |
|-------|------|
| **SearchAgent** | Concurrent retrieval from arXiv + Semantic Scholar |
| **ClassificationAgent** | Embedding-based relevance scoring + topic labelling |
| **SummarizationAgent** | RAG-grounded structured paper summaries |
| **MethodologyExtractionAgent** | Methods, datasets, and metric extraction |
| **GapDiscoveryAgent** | Cross-corpus research gap identification |
| **SynthesisAgent** | 5-section literature review narrative |
| **CitationAgent** | APA 7th / IEEE / BibTeX formatting |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- **[Ollama](https://ollama.ai)** — free local LLM server (required)

No paid API keys. No cloud services. Everything runs on your machine.

---

## Local Setup

### 1. Install and start Ollama

```bash
# Download from https://ollama.ai and install, then:
ollama pull llama3.2          # recommended model (~2 GB, fast)
ollama serve                  # start the server (runs on port 11434)
```

> Ollama is free and runs fully offline after the initial model download.

### 2. Clone and configure environment

```bash
git clone <your-repo-url>
cd agentic-research-assistant
cp .env.example .env
# .env is ready to go — no keys needed!
# Edit OLLAMA_MODEL if you want a different model (default: llama3.2)
```

### 3. Backend

```bash
# Create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# sentence-transformers downloads the embedding model on first run (~90 MB)
# You can pre-download it now:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Start the backend server
uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` and OpenAPI docs at `http://localhost:8000/docs`.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

The app will open at `http://localhost:5173`.

---

## Docker Compose (full stack)

```bash
# Copy and fill in your .env
cp .env.example .env

# Build and start all services (backend + frontend + postgres)
docker-compose up --build
```

Visit `http://localhost` for the frontend, `http://localhost:8000/docs` for the API.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_BASE_URL` | **Yes** | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3.2` | Model for all LLM tasks (also try `mistral`, `gemma2`) |
| `SENTENCE_TRANSFORMER_MODEL` | No | `all-MiniLM-L6-v2` | Local embedding model (downloads ~90 MB on first run) |
| `DATABASE_URL` | No | SQLite | Async DB URL. Use `postgresql+asyncpg://...` for production |
| `ENVIRONMENT` | No | `development` | Set to `production` to use PostgreSQL |
| `DATA_DIR` | No | `./data` | Root directory for uploads, exports, and FAISS indexes |
| `MAX_UPLOAD_SIZE_MB` | No | `50` | Maximum PDF upload size in megabytes |
| `SEMANTIC_SCHOLAR_API_KEY` | No | — | Optional — increases Semantic Scholar rate limits (free to register) |

> **Cost: $0** — Ollama is free and open-source. sentence-transformers runs locally. arXiv and Semantic Scholar are free APIs.

---

## Example API Calls

### Start a new research session

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "query": "transformer models for named entity recognition",
    "paper_limit": 30,
    "relevance_threshold": 0.35
  }'
```

### Check pipeline progress

```bash
curl http://localhost:8000/api/v1/sessions/<session_id>
```

### Get full results

```bash
curl http://localhost:8000/api/v1/sessions/<session_id>/results
```

### Export as PDF

```bash
curl -OJ "http://localhost:8000/api/v1/sessions/<session_id>/export?format=pdf&citation_style=ieee"
```

### Upload PDFs

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@my_paper.pdf" \
  -F "files=@another_paper.pdf"
```

---

## Running Tests

```bash
# Backend tests with coverage
pytest

# Frontend tests
cd frontend && npm test
```

---

## Project Structure

```
agentic-research-assistant/
├── backend/
│   ├── agents/          # 7 specialist agents + contracts
│   ├── api/             # FastAPI routers and Pydantic schemas
│   ├── db/              # SQLAlchemy models + Alembic migrations
│   ├── exporters/       # Markdown, PDF, JSON, knowledge graph
│   ├── llm/             # LLM client (OpenAI + Ollama fallback)
│   ├── orchestrator/    # Pipeline state machine
│   ├── parsers/         # arXiv client, Semantic Scholar client, PDF parser
│   ├── rag/             # Chunker, embedder, FAISS store, retriever
│   ├── utils/           # Deduplication helpers
│   ├── config.py        # Settings from environment variables
│   └── main.py          # FastAPI app factory
├── frontend/
│   └── src/
│       ├── pages/       # QueryPage, SessionPage, DashboardPage
│       ├── components/  # KnowledgeGraphView
│       ├── services/    # Axios API client
│       └── store/       # Zustand state
├── tests/
│   ├── unit/            # Unit tests per module
│   └── integration/     # Full pipeline integration tests
├── data/                # Runtime data (gitignored)
│   ├── uploads/
│   ├── exports/
│   └── faiss/
├── .env.example
├── pyproject.toml
├── docker-compose.yml
└── README.md
```

---

## Known Limitations

1. **Ollama speed**: Local LLMs are slower than cloud APIs, especially on CPU. A 50-paper pipeline takes longer on CPU-only machines. A GPU significantly improves throughput.
2. **Model quality vs. GPT-4**: Local models like `llama3.2` and `mistral` are very capable but may produce less polished prose than GPT-4o in some cases. `llama3.2:latest` or `mistral` are good defaults.
3. **First run**: `sentence-transformers` downloads `all-MiniLM-L6-v2` (~90 MB) on first use. Subsequent runs are instant.
4. **arXiv rate limits**: arXiv requests should be spaced to comply with their 3-second delay policy; the client uses exponential back-off.
5. **PDF scans**: Scanned (image-only) PDFs yield no text. Use OCR-processed PDFs for best results.
6. **Synthesis quality**: Always review AI-generated content before academic use.
7. **Single-user scale**: Designed for personal/lab use. No multi-user auth.

---

## License

MIT — built as a final-year major project showcase.
