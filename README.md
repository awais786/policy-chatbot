# Policy Chatbot - Document Q&A System

An open-source Django application that enables organizations to upload PDF documents, automatically extract and vectorize content, and query documents using semantic search with LLM-powered conversational answers.

## ✨ Features

- **📄 Document Management**: Upload PDF files with automatic processing
- **🔍 Semantic Search**: pgvector-powered similarity search for relevant content  
- **🤖 LLM Integration**: Generate contextual answers using Ollama (local) or OpenAI (production)
- **💬 Conversation History**: LangChain-powered chat sessions with automatic context retention
- **🧠 Smart Context**: Maintains conversation context across multiple exchanges (understands "it", "that", etc.)
- **⚡ High Performance**: In-memory chat history for instant response times  
- **🔧 Zero Configuration**: No Redis or external chat storage needed - works out of the box
- **🏢 Multi-tenancy**: Complete organization-level isolation

## 🚀 Quick Start

### Prerequisites

```bash
# Required
- Python 3.11+
- PostgreSQL 15+ with pgvector extension  
- Git

# For local LLM (recommended)
- Ollama (download from ollama.ai)
```

### MacOS Setup

```bash
# Install dependencies
brew install postgresql@15 pgvector ollama

# Start Ollama and pull model
ollama serve &
ollama pull mistral
```

### Ubuntu Setup

```bash
# Install dependencies
sudo apt update
sudo apt install postgresql-15 postgresql-15-pgvector
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull mistral
```

### Project Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/policy-chatbot.git
cd policy-chatbot
python3.11 -m venv venv
source venv/bin/activate

# Complete setup
make setup
make createuser
make dev-simple
```

**That's it!** Access at:
- **Admin**: http://127.0.0.1:8000/admin/ 
- **API**: http://127.0.0.1:8000/api/v1/
- **Chat Widget**: http://127.0.0.1:8000/static/chat_widget.html

## 📊 Available Commands

```bash
# Setup & Development
make setup           # Complete local development setup
make dev-simple      # Start minimal servers (recommended)
make dev             # Start all services including Redis

# Testing  
make test-system     # Test search and chat functionality
make test-search     # Test semantic search
make test-chat       # Test LangChain chat with conversation history

# Ollama Management
make setup-ollama    # Install and setup Ollama with Mistral
make ollama-status   # Check if Ollama is running
make list-models     # List installed models

# Utilities
make createuser      # Create Django superuser
make clean           # Clean Python cache files
make help            # Show all commands
```

## 🧪 Testing

```bash
# Test search
curl -X POST http://127.0.0.1:8000/api/v1/chat/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "your search term", "limit": 3}'

# Test chat with conversation history
curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this about?", "session_id": "test-123"}'

# Follow-up (maintains context)
curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me more about it", "session_id": "test-123"}'
```

## 🔧 Configuration

Key settings in `config/settings/local.py`:

```python
# Embedding Provider (Hugging Face for local)
EMBEDDING_PROVIDER = 'huggingface'
EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

# LLM Provider (Ollama for local) 
CHATBOT_LLM_PROVIDER = 'ollama'
CHATBOT_LLM_MODEL = 'mistral'
OLLAMA_BASE_URL = 'http://localhost:11434'

# Chat History (LangChain + In-Memory)
CHATBOT_ENABLE_CHAT_HISTORY = True
```

## 🏗️ Architecture

- **Backend**: Django 5.0+ with DRF
- **Database**: PostgreSQL 15+ with pgvector extension
- **Document Processing**: PyPDF2/pdfplumber + LangChain
- **Embeddings**: Hugging Face sentence-transformers (local)
- **LLM**: Ollama (local) or OpenAI (production)
- **Chat History**: LangChain + In-Memory storage
- **Search**: pgvector similarity search

## 🔍 How It Works

1. **Upload**: PDF documents via Django admin
2. **Process**: Text extraction → Chunking → Embedding generation
3. **Store**: Chunks and vectors in PostgreSQL with pgvector
4. **Query**: User question → Vector search → LLM generation
5. **Context**: LangChain maintains conversation history

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes and test: `make test-system`
4. Commit and push: `git commit -m "Add feature" && git push`
5. Create pull request

## 📄 License

MIT License - see [LICENSE](./LICENSE) file for details.

---

**🚀 Ready to get started? Run `make setup && make dev-simple`**
