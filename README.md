# Policy Chatbot - Document Q&A System

An open-source Django application that enables organizations to upload PDF documents, automatically extract and vectorize content, and query documents using semantic search with LLM-powered conversational answers.

## 🎯 Use Cases

- **Internal HR Policy Assistants**: Answer employee questions about benefits, PTO, etc.
- **Compliance Documentation Access**: Quick access to regulatory and compliance docs
- **Corporate Knowledge Management**: Centralized document search and Q&A
- **Enterprise Document Q&A**: Any organization with large document repositories

## ✨ Features

- **📄 Document Management**: Upload PDF files with automatic processing
- **🔍 Semantic Search**: pgvector-powered similarity search for relevant content  
- **🤖 LLM Integration**: Generate contextual answers using Ollama (local) or OpenAI (production)
- **💬 Conversation History**: LangChain-powered chat sessions with context awareness
- **🏢 Multi-tenancy**: Complete organization-level isolation
- **🔐 API Authentication**: Secure API key-based access
- **☁️ AWS Ready**: Production-ready infrastructure for AWS deployment
- **💻 Management Commands**: Built-in commands for testing search and chat

## 🏗️ Architecture

### Technology Stack

**Backend:**
- Django 5.0+ with Django REST Framework
- PostgreSQL 15+ with pgvector extension for vector similarity search
- Celery for async document processing
- Redis for caching and task queue

**Document Processing & AI:**
- PyPDF2/pdfplumber for PDF text extraction
- LangChain for document chunking and conversation management
- Hugging Face sentence-transformers for local embeddings
- Ollama for local LLM inference (Mistral model)
- OpenAI for production embeddings and LLM

**Infrastructure:**
- AWS S3 for document storage (production)
- AWS RDS for PostgreSQL (production)
- Local file storage and PostgreSQL for development

## 🚀 Quick Start

### Prerequisites

Make sure you have these installed:

```bash
# Required
- Python 3.11+
- PostgreSQL 15+ with pgvector extension  
- Redis server
- Git

# For local LLM (recommended)
- Ollama (download from ollama.ai)
```

### MacOS Setup

```bash
# Install PostgreSQL with pgvector
brew install postgresql@15 pgvector

# Install Redis
brew install redis

# Install Ollama for local LLM
brew install ollama

# Start Ollama and pull Mistral model
ollama serve &
ollama pull mistral
```

### Ubuntu Setup

```bash
# Install PostgreSQL and pgvector
sudo apt update
sudo apt install postgresql-15 postgresql-15-pgvector redis-server

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull mistral
```

### Project Setup (All Platforms)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/policy-chatbot.git
cd policy-chatbot

# 2. Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Complete setup with Makefile (recommended)
make setup

# OR manual setup:
# make install-deps
# make setup-db  
# make migrate

# 4. Create a superuser for admin access
make createuser

# 5. Start the development environment
make dev
```

That's it! The system is now running at:
- **Django Admin**: http://127.0.0.1:8000/admin/ 
- **API Base**: http://127.0.0.1:8000/api/v1/
- **Health Check**: http://127.0.0.1:8000/api/v1/chat/health/

## 🧪 Testing Search & Chat

### Test with Makefile (Recommended)

```bash
# Test both search and chat functionality
make test-system

# Test search functionality only
make test-search  

# Test chat with conversation history
make test-chat
```

### Manual API Testing

```bash
# Test semantic search
curl -X POST http://127.0.0.1:8000/api/v1/chat/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "meezan bank", "limit": 3, "min_similarity": 0.3}'

# Test conversational chat
curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is MEEZAN BANK?", "session_id": "test-123", "include_sources": true}'

# Follow-up question (maintains conversation context)
curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What was the fine amount?", "session_id": "test-123", "include_sources": true}'

# Check LangChain session statistics  
curl -X GET http://127.0.0.1:8000/api/v1/chat/stats/
```

### Using Management Commands

```bash
# Test search with command line
cd backend
python manage.py test_search "traffic violation" --limit 5

# Test chat with conversation
python manage.py test_chat "What is MEEZAN BANK?" --session-id "my-session"
python manage.py test_chat "What was the fine?" --session-id "my-session"

# Inspect conversation sessions  
python manage.py inspect_sessions --session-id "my-session"
```

## 📊 Available Makefile Commands

```bash
# Setup Commands
make setup           # Complete local development setup
make install-deps    # Install Python dependencies
make setup-db        # Create PostgreSQL database with pgvector
make migrate         # Run Django migrations

# Development Commands  
make dev             # Start all services (Django + Celery + Redis)
make run-server      # Start Django server only
make run-worker      # Start Celery worker only

# Testing Commands
make test-system     # Test search and chat functionality
make test-search     # Test semantic search with sample queries  
make test-chat       # Test LangChain chat with conversation history

# Utility Commands
make createuser      # Create Django superuser
make shell           # Open Django shell
make dbshell         # Open PostgreSQL shell
make clean           # Clean Python cache files
make help            # Show all available commands
```

## 📖 API Usage Examples

### Document Upload & Processing

```python
import requests

# Upload a document (requires admin setup first)
with open("policy-document.pdf", "rb") as f:
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/documents/upload/",
        files={"file": f}
    )
```

### Search API

```python
# Semantic search
response = requests.post(
    "http://127.0.0.1:8000/api/v1/chat/search/",
    json={
        "query": "employee benefits policy", 
        "limit": 5,
        "min_similarity": 0.7
    }
)
results = response.json()
```

### Chat API with Conversation History

```python
# Start a conversation
response = requests.post(
    "http://127.0.0.1:8000/api/v1/chat/", 
    json={
        "message": "What are the vacation policies?",
        "session_id": "user-123",
        "include_sources": True
    }
)

# Continue conversation (maintains context)
response = requests.post(
    "http://127.0.0.1:8000/api/v1/chat/",
    json={
        "message": "How many days per year?", 
        "session_id": "user-123",  # Same session
        "include_sources": True
    }
)
```

## 🔧 Configuration

### Local Development Settings

The system uses environment-specific settings:

- **Local Development**: `config/settings/local.py`
- **Production**: `config/settings/production.py`

Key local settings:
```python
# Embedding Provider (Hugging Face for local)
EMBEDDING_PROVIDER = 'huggingface'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_DIMENSIONS = 384

# LLM Provider (Ollama for local) 
CHATBOT_LLM_PROVIDER = 'ollama'
CHATBOT_LLM_MODEL = 'mistral'
OLLAMA_BASE_URL = 'http://localhost:11434'

# Chat History (LangChain)
CHATBOT_ENABLE_CHAT_HISTORY = True
```

## 🏢 Multi-Tenancy

The system supports multiple organizations:

1. **Upload Documents**: Via Django admin at `/admin/`
2. **Organization Isolation**: All data is organization-scoped
3. **API Access**: Future API key authentication per organization

## 🔍 How It Works

### Document Processing Pipeline

1. **Upload**: PDF uploaded via Django admin
2. **Text Extraction**: PyPDF2 extracts text content  
3. **Chunking**: LangChain splits text into overlapping chunks
4. **Embedding**: Hugging Face generates 384-dimensional vectors
5. **Storage**: Chunks and embeddings stored in PostgreSQL with pgvector

### Search & Chat Pipeline

1. **Query Processing**: User question converted to embedding
2. **Vector Search**: pgvector finds similar document chunks
3. **Context Building**: Relevant chunks formatted for LLM
4. **LLM Generation**: Ollama generates contextual response
5. **Conversation History**: LangChain maintains session context

## 🚀 Advanced Usage

### Custom LLM Configuration

```bash
# Use different Ollama model
ollama pull llama2
# Update CHATBOT_LLM_MODEL = 'llama2' in settings

# Use OpenAI for production
# Set CHATBOT_LLM_PROVIDER = 'openai'  
# Set OPENAI_API_KEY in environment
```

### Database Inspection

```bash
# Check database contents
make inspect-db

# Direct PostgreSQL access
make dbshell

# Check vector dimensions
psql chatbot_db -c "SELECT vector_dims(embedding) FROM document_chunks LIMIT 1;"
```

## 🧪 Testing & Development

### Running Tests

```bash
# Quick system test
make quick-test

# Full test suite (when implemented)
pytest

# Test with coverage
pytest --cov=apps --cov-report=html
```

### Development Workflow

```bash
# Start fresh environment
make fresh-start

# View recent logs  
make logs

# Clean up cache files
make clean
```

## 🔒 Security Features

- **Organization Isolation**: Row-level security for multi-tenancy
- **Input Validation**: Comprehensive request validation
- **File Upload Security**: PDF validation and virus scanning ready
- **Rate Limiting**: Built-in API rate limiting
- **HTTPS Ready**: SSL/TLS configuration for production

## 📚 Project Structure

```
policy-chatbot/
├── Makefile                 # Development commands
├── README.md               # This file
├── backend/                # Django application
│   ├── manage.py          # Django management
│   ├── config/            # Django settings
│   ├── apps/              # Django apps
│   │   ├── core/          # Core models (Organization, User)
│   │   ├── documents/     # Document processing
│   │   └── chatbot/       # Search and chat APIs
│   └── requirements/      # Python dependencies
├── IMPLEMENTATION_PLAN.md  # Detailed technical plan
└── models_blueprint.py    # Database schema blueprint
```

## 🤖 LangChain Integration

The system uses LangChain for:

- **Message History**: `BaseChatMessageHistory` for session management
- **Conversation Chains**: `RunnableWithMessageHistory` for context
- **Prompt Templates**: `ChatPromptTemplate` with `MessagesPlaceholder`  
- **Message Types**: `HumanMessage` and `AIMessage` for proper typing

## 📊 Monitoring & Stats

```bash
# Check system health
curl http://127.0.0.1:8000/api/v1/chat/health/

# View chat session statistics
curl http://127.0.0.1:8000/api/v1/chat/stats/

# Inspect active sessions
python manage.py inspect_sessions
```

## 🎯 Production Deployment

For production deployment on AWS:

1. **Review**: `IMPLEMENTATION_PLAN.md` for infrastructure details
2. **Configure**: Production settings with OpenAI API keys
3. **Deploy**: Using Docker + ECS/Fargate
4. **Monitor**: CloudWatch integration and error tracking

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and test: `make test-system`
4. Commit changes: `git commit -m "Add feature"`
5. Push and create PR: `git push origin feature-name`

## 📄 License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) file for details.

## 🙏 Acknowledgments

- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search for PostgreSQL
- [LangChain](https://github.com/langchain-ai/langchain) - LLM application framework  
- [Ollama](https://ollama.ai/) - Local LLM inference
- [Hugging Face](https://huggingface.co/) - Transformer models and embeddings
- Django and DRF communities

## 📧 Support & Resources

- **Documentation**: Complete implementation details in planning documents
- **Issues**: [GitHub Issues](https://github.com/yourusername/policy-chatbot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/policy-chatbot/discussions)

---

**Built with ❤️ for organizations that want AI-powered document search and conversational Q&A**

**🚀 Ready to get started? Run `make setup` and `make dev` to launch your local development environment!**

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
