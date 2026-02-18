# Policy Chatbot Makefile
# This file provides convenient commands for local development setup and testing

.PHONY: help install-deps setup-db migrate test-system clean dev run-server run-worker test-search test-chat setup-ollama start-ollama stop-ollama pull-models list-models ollama-status dump-db restore-db create-sample-data inspect-db

# Default target
help:
	@echo "Policy Chatbot - Development Commands"
	@echo "====================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  setup           - Complete local development setup (deps + db + migrate)"
	@echo "  install-deps    - Install Python dependencies for local development"
	@echo "  setup-db        - Create and setup PostgreSQL database with pgvector"
	@echo "  migrate         - Run Django migrations"
	@echo ""
	@echo "Ollama Commands:"
	@echo "  setup-ollama    - Install and setup Ollama with Mistral model"
	@echo "  start-ollama    - Start Ollama server"
	@echo "  stop-ollama     - Stop Ollama server"
	@echo "  pull-models     - Pull required AI models (Mistral)"
	@echo "  list-models     - List installed Ollama models"
	@echo "  ollama-status   - Check if Ollama is running"
	@echo ""
	@echo "Development Commands:"
	@echo "  dev             - Start development servers (Django + Celery + Redis)"
	@echo "  dev-simple      - Start minimal servers (Django only) - no Redis needed"
	@echo "  run-server      - Start Django development server only"
	@echo "  run-worker      - Start Celery worker only"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test-system     - Test search and chat functionality"
	@echo "  test-search     - Test semantic search with sample queries"
	@echo "  test-chat       - Test LangChain chat with conversation history"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  clean           - Clean up Python cache files"
	@echo "  requirements    - Update requirements files"
	@echo ""
	@echo "Database Commands:"
	@echo "  createuser      - Create Django superuser"
	@echo "  shell           - Open Django shell"
	@echo "  dbshell         - Open PostgreSQL shell"

# Complete setup for new developers
setup: install-deps setup-ollama setup-db migrate
	@echo "✅ Complete setup finished! Run 'make dev' to start development servers."

# Install Python dependencies
install-deps:
	@echo "📦 Installing Python dependencies..."
	pip install --upgrade pip
	pip install -r backend/requirements/development.txt
	@echo "✅ Dependencies installed!"

# Setup PostgreSQL database with pgvector
setup-db:
	@echo "🗄️  Setting up PostgreSQL database..."
	@echo "Creating database and user..."
	-psql postgres -c "DROP DATABASE IF EXISTS chatbot_db;"
	-psql postgres -c "DROP USER IF EXISTS chatbot_user;"
	psql postgres -c "CREATE DATABASE chatbot_db;"
	psql postgres -c "CREATE USER chatbot_user WITH PASSWORD 'chatbot_password';"
	psql postgres -c "ALTER USER chatbot_user CREATEDB;"
	psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE chatbot_db TO chatbot_user;"
	@echo "Adding pgvector extension..."
	psql chatbot_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
	@echo "✅ Database setup complete!"

# Run Django migrations
migrate:
	@echo "🔄 Running Django migrations..."
	cd backend && python manage.py makemigrations
	cd backend && python manage.py migrate
	@echo "✅ Migrations complete!"

# Start all development services
dev:
	@echo "🚀 Starting development environment..."
	@echo "This will start:"
	@echo "  - Ollama server for local LLM"
	@echo "  - Django server on http://127.0.0.1:8000"
	@echo "  - Celery worker for document processing"
	@echo "  - Redis server for caching (optional)"
	@echo ""
	@echo "Chat history works in-memory (no Redis required)!"
	@echo "Press Ctrl+C to stop all services"
	@make start-ollama && make run-redis & make run-worker & make run-server

# Start minimal development environment (no Redis needed)
dev-simple:
	@echo "🚀 Starting simple development environment..."
	@echo "This will start:"
	@echo "  - Ollama server for local LLM"
	@echo "  - Django server on http://127.0.0.1:8000"
	@echo ""
	@echo "✅ Chat history works perfectly in-memory!"
	@echo "✅ Document processing available via admin"
	@echo "Press Ctrl+C to stop all services"
	@make start-ollama && make run-server

# Start Django development server
run-server:
	@echo "🌐 Starting Django development server..."
	cd backend && python manage.py runserver

# Start Celery worker
run-worker:
	@echo "⚙️  Starting Celery worker..."
	cd backend && celery -A config worker -l info

# Start Redis server
run-redis:
	@echo "📦 Starting Redis server..."
	redis-server

# Ollama setup and management commands
setup-ollama:
	@echo "🤖 Setting up Ollama for local LLM..."
	@echo "Detecting operating system..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "📱 macOS detected - installing Ollama via Homebrew..."; \
		if ! command -v ollama > /dev/null 2>&1; then \
			if command -v brew > /dev/null 2>&1; then \
				brew install ollama; \
			else \
				echo "❌ Homebrew not found. Installing Ollama manually..."; \
				curl -fsSL https://ollama.ai/install.sh | sh; \
			fi; \
		else \
			echo "✅ Ollama already installed"; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		echo "🐧 Linux detected - installing Ollama..."; \
		if ! command -v ollama > /dev/null 2>&1; then \
			curl -fsSL https://ollama.ai/install.sh | sh; \
		else \
			echo "✅ Ollama already installed"; \
		fi; \
	else \
		echo "❓ Unsupported OS. Please install Ollama manually from https://ollama.ai"; \
		exit 1; \
	fi
	@echo "🚀 Starting Ollama server..."
	@make start-ollama
	@sleep 3
	@echo "📥 Pulling Mistral model..."
	@make pull-models
	@echo "✅ Ollama setup complete!"

start-ollama:
	@echo "🚀 Starting Ollama server..."
	@if ! pgrep -f "ollama serve" > /dev/null; then \
		ollama serve > /dev/null 2>&1 & \
		echo "✅ Ollama server started in background"; \
		sleep 2; \
	else \
		echo "✅ Ollama server is already running"; \
	fi

stop-ollama:
	@echo "🛑 Stopping Ollama server..."
	@pkill -f "ollama serve" || echo "Ollama server was not running"
	@echo "✅ Ollama server stopped"

pull-models:
	@echo "📥 Pulling required AI models..."
	@echo "Pulling Mistral model (recommended for local development)..."
	@ollama pull mistral
	@echo "✅ Models pulled successfully!"
	@echo ""
	@echo "Available commands to pull additional models:"
	@echo "  ollama pull llama2      # Alternative model"
	@echo "  ollama pull codellama   # Code-focused model"
	@echo "  ollama pull llama2:7b   # Specific version"

list-models:
	@echo "📚 Installed Ollama models:"
	@ollama list || echo "❌ Ollama not running or not installed"

ollama-status:
	@echo "🔍 Checking Ollama status..."
	@if command -v ollama > /dev/null 2>&1; then \
		echo "✅ Ollama is installed"; \
		if pgrep -f "ollama serve" > /dev/null; then \
			echo "✅ Ollama server is running"; \
			echo "📡 Server URL: http://localhost:11434"; \
			echo "🧠 Testing connection..."; \
			curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama API is responding" || echo "❌ Ollama API not responding"; \
		else \
			echo "❌ Ollama server is not running - run 'make start-ollama'"; \
		fi; \
	else \
		echo "❌ Ollama is not installed - run 'make setup-ollama'"; \
	fi

# Test the complete system
test-system: test-search test-chat
	@echo "✅ System testing complete!"

# Test search functionality
test-search:
	@echo "🔍 Testing semantic search functionality..."
	@echo ""
	@echo "Testing search for 'meezan bank':"
	@curl -X POST http://127.0.0.1:8000/api/v1/chat/search/ \
		-H "Content-Type: application/json" \
		-d '{"query": "meezan bank", "limit": 3, "min_similarity": 0.3}' | python3 -m json.tool
	@echo ""
	@echo "Testing search for 'traffic fine':"
	@curl -X POST http://127.0.0.1:8000/api/v1/chat/search/ \
		-H "Content-Type: application/json" \
		-d '{"query": "traffic fine", "limit": 3, "min_similarity": 0.3}' | python3 -m json.tool
	@echo ""

# Test chat functionality with LangChain
test-chat:
	@echo "💬 Testing LangChain chat functionality..."
	@echo ""
	@echo "Question 1: What is MEEZAN BANK?"
	@curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
		-H "Content-Type: application/json" \
		-d '{"message": "What is MEEZAN BANK?", "session_id": "makefile-test", "include_sources": true}' | python3 -m json.tool
	@echo ""
	@echo "Question 2 (Follow-up): What was the fine amount?"
	@curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
		-H "Content-Type: application/json" \
		-d '{"message": "What was the fine amount?", "session_id": "makefile-test", "include_sources": true}' | python3 -m json.tool
	@echo ""
	@echo "Question 3 (Follow-up): What happens if I dont pay the traffic fine?"
	@curl -X POST http://127.0.0.1:8000/api/v1/chat/ \
		-H "Content-Type: application/json" \
		-d '{"message": "What happens if I dont pay the traffic fine?", "session_id": "makefile-test", "include_sources": true}' | python3 -m json.tool
	@echo ""
	@echo "Checking LangChain session stats:"
	@curl -X GET http://127.0.0.1:8000/api/v1/chat/stats/ | python3 -m json.tool

# Django management commands
createuser:
	@echo "👤 Creating Django superuser..."
	cd backend && python manage.py createsuperuser

shell:
	@echo "🐍 Opening Django shell..."
	cd backend && python manage.py shell

dbshell:
	@echo "🗄️  Opening PostgreSQL shell..."
	psql chatbot_db

# Utility commands
clean:
	@echo "🧹 Cleaning Python cache files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	@echo "✅ Cleanup complete!"

requirements:
	@echo "📝 Updating requirements files..."
	pip freeze > backend/requirements/current-env.txt
	@echo "✅ Current environment saved to backend/requirements/current-env.txt"

# Development workflow commands
fresh-start: clean setup-db migrate
	@echo "🆕 Fresh development environment ready!"

quick-test:
	@echo "⚡ Quick system test..."
	@curl -s http://127.0.0.1:8000/api/v1/chat/health/ | python3 -m json.tool

# Database inspection
inspect-db:
	@echo "🔍 Database inspection..."
	@echo "Documents:"
	@psql chatbot_db -c "SELECT COUNT(*) as total_documents FROM documents;"
	@echo "Document chunks:"
	@psql chatbot_db -c "SELECT COUNT(*) as total_chunks, COUNT(embedding) as chunks_with_embeddings FROM document_chunks;"
	@echo "Organizations:"
	@psql chatbot_db -c "SELECT id, name FROM organizations;"

# Logs
logs:
	@echo "📋 Recent Django logs..."
	@tail -n 50 backend/logs/django.log || echo "No log file found"

# Help for new contributors
onboarding:
	@echo "🎓 Policy Chatbot - New Developer Onboarding"
	@echo "============================================"
	@echo ""
	@echo "Welcome! Here's how to get started:"
	@echo ""
	@echo "1. Prerequisites:"
	@echo "   - Python 3.11+"
	@echo "   - PostgreSQL 15+ with pgvector extension"
	@echo "   - Ollama (for local LLM) - download from ollama.ai"
	@echo "   - Redis server (optional - only needed for caching)"
	@echo ""
	@echo "2. Run complete setup:"
	@echo "   make setup"
	@echo ""
	@echo "3. Start development environment:"
	@echo "   make dev-simple    # Simple setup (recommended)"
	@echo "   make dev          # Full setup with Redis"
	@echo ""
	@echo "4. Test the system:"
	@echo "   make test-system"
	@echo ""
	@echo "5. Create a superuser to access admin:"
	@echo "   make createuser"
	@echo ""
	@echo "6. Access the admin at: http://127.0.0.1:8000/admin/"
	@echo ""
	@echo "✅ Chat history works perfectly without Redis!"
	@echo "Need help? Check 'make help' for all available commands!"
