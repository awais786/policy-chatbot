# Policy Chatbot - Document Q&A System

An open-source Django application that enables organizations to upload PDF documents, automatically extract and vectorize content, and query documents using semantic search with LLM-powered answers.

## 🎯 Use Cases

- **Internal HR Policy Assistants**: Answer employee questions about benefits, PTO, etc.
- **Compliance Documentation Access**: Quick access to regulatory and compliance docs
- **Corporate Knowledge Management**: Centralized document search and Q&A
- **Enterprise Document Q&A**: Any organization with large document repositories

## ✨ Features

- **📄 Document Management**: Upload PDF files with automatic processing
- **🔍 Semantic Search**: pgvector-powered similarity search for relevant content
- **🤖 LLM Integration**: Generate contextual answers using OpenAI/Anthropic
- **🏢 Multi-tenancy**: Complete organization-level isolation
- **🔐 API Authentication**: Secure API key-based access
- **☁️ AWS Ready**: Production-ready infrastructure for AWS deployment
- **💬 Embeddable Widget**: JavaScript widget for easy website integration

## 🏗️ Architecture

### Technology Stack

**Backend:**
- Django 5.0+ with Django REST Framework
- PostgreSQL 15+ with pgvector extension
- Celery for async document processing
- Redis for caching and task queue

**Document Processing:**
- PyPDF2/pdfplumber for PDF extraction
- LangChain for chunking and embeddings
- OpenAI/Anthropic for LLM responses
- Sentence Transformers for embeddings

**Infrastructure:**
- AWS S3 for document storage
- AWS RDS for PostgreSQL
- AWS ECS/Fargate for application hosting
- CloudFront for widget CDN

**Widget:**
- Vanilla JavaScript (framework-agnostic)
- Shadow DOM for style isolation
- SSE for streaming responses

## 📋 Planning Documents

This repository includes three comprehensive planning documents:

1. **`IMPLEMENTATION_PLAN.md`** - Complete implementation roadmap
   - Detailed architecture and design decisions
   - Database schema and API design
   - Document processing pipeline
   - 12-week implementation phases
   - AWS deployment architecture
   - Security considerations
   - Cost estimation

2. **`models_blueprint.py`** - Django models with full implementation
   - Organization, User, Document models
   - DocumentChunk with pgvector integration
   - Conversation and Message models
   - Custom managers for multi-tenancy
   - Usage tracking and analytics
   - Complete with example usage

3. **`project_setup.py`** - Setup guide and project structure
   - Complete project directory structure
   - All dependencies and requirements
   - Django settings configuration
   - Docker and Celery setup
   - API usage examples
   - Widget integration examples
   - Testing examples

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis
- AWS account (for S3 storage)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/policy-chatbot.git
cd policy-chatbot

# 2. Install pgvector extension
# macOS:
brew install pgvector

# Ubuntu:
sudo apt install postgresql-15-pgvector

# 3. Create PostgreSQL database
psql postgres
CREATE DATABASE policy_chatbot;
CREATE USER policy_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE policy_chatbot TO policy_user;
\c policy_chatbot
CREATE EXTENSION IF NOT EXISTS vector;
\q

# 4. Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 5. Install dependencies (once project is set up)
pip install -r backend/requirements/development.txt

# 6. Configure environment
cp backend/.env.example backend/.env
# Edit .env with your settings

# 7. Run migrations
cd backend
python manage.py migrate
python manage.py createsuperuser

# 8. Run the application
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery worker
celery -A config worker -l info

# Terminal 3: Redis
redis-server
```

### Docker Setup

```bash
# Run with Docker Compose
docker-compose up -d

# Access at http://localhost:8000
```

## 📖 API Usage

```python
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "pk_your_api_key_here"
HEADERS = {"X-API-Key": API_KEY}

# Upload document
with open("handbook.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/v1/documents/upload/",
        headers=HEADERS,
        files={"file": f}
    )
document = response.json()

# Query documents
response = requests.post(
    f"{BASE_URL}/api/v1/query/",
    headers=HEADERS,
    json={"question": "What are the company benefits?"}
)
answer = response.json()
print(answer["answer"])
```

## 🎨 Widget Integration

```html
<!-- Add to your website -->
<script 
    src="https://cdn.yourapp.com/widget.js"
    data-api-key="pk_your_api_key_here"
    data-theme="light"
    data-primary-color="#007bff">
</script>
```

## 📊 Implementation Phases

### Phase 1: Core Backend (Weeks 1-2)
- Django project setup
- Database models with pgvector
- API key authentication
- Document upload API

### Phase 2: Document Processing (Weeks 3-4)
- Celery task processing
- PDF extraction and chunking
- Embedding generation
- Vector storage

### Phase 3: Search & Query (Weeks 5-6)
- Semantic search implementation
- LLM integration
- Conversation management
- Response streaming

### Phase 4: API & Security (Week 7)
- REST API completion
- Rate limiting
- Input validation
- Testing

### Phase 5: Widget (Weeks 8-9)
- JavaScript widget development
- UI components
- Theme customization
- Mobile responsiveness

### Phase 6: AWS Deployment (Week 10)
- Infrastructure as Code
- Docker containerization
- CI/CD pipeline
- Production configuration

### Phase 7: Monitoring & Polish (Weeks 11-12)
- Monitoring and logging
- Performance optimization
- Documentation
- Open-source preparation

## 🔒 Security

- API key-based authentication with hashing
- Row-level security for multi-tenancy
- HTTPS enforcement
- Input validation and sanitization
- Rate limiting per organization
- Audit logging
- S3 bucket encryption

## 💰 Cost Estimation

### Monthly AWS Infrastructure (Medium Scale)
- ECS Fargate: ~$100
- RDS PostgreSQL: ~$150
- ElastiCache Redis: ~$30
- S3 Storage: ~$2-20
- **Total**: ~$300-350/month

### API Costs (Per 10,000 queries)
- OpenAI embeddings: ~$0.20
- OpenAI GPT-4: ~$100
- **Total**: ~$100/10k queries

## 📚 Documentation

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) - Comprehensive technical plan
- [Models Blueprint](./models_blueprint.py) - Database schema and models
- [Project Setup](./project_setup.py) - Setup guide and examples
- API Documentation (coming soon)
- Deployment Guide (coming soon)

## 🧪 Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=apps --cov-report=html

# Run specific test
pytest apps/documents/tests/test_processing.py
```

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search for PostgreSQL
- [LangChain](https://github.com/langchain-ai/langchain) - LLM application framework
- [OpenAI](https://openai.com/) - Embedding and LLM APIs
- Django and DRF communities

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/policy-chatbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/policy-chatbot/discussions)
- **Email**: support@yourapp.com

## 🗺️ Roadmap

- [ ] Phase 1: Core Backend (Q1 2026)
- [ ] Phase 2-3: Document Processing & Search (Q1 2026)
- [ ] Phase 4-5: API & Widget (Q2 2026)
- [ ] Phase 6-7: Deployment & Launch (Q2 2026)
- [ ] Multi-format support (Word, Excel, PowerPoint)
- [ ] OCR for scanned documents
- [ ] Advanced analytics dashboard
- [ ] Mobile SDKs
- [ ] Slack/Teams integrations

---

**Built with ❤️ for organizations that want AI-powered document search**
