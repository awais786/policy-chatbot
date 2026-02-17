# Django Policy Chatbot - Implementation Plan

## Project Overview

An open-source Django application for document-based Q&A using RAG (Retrieval Augmented Generation) with multi-tenant support and embeddable widgets.

## Core Features

1. **Document Management**: PDF upload, extraction, chunking, and vectorization
2. **Semantic Search**: pgvector-powered similarity search
3. **LLM Integration**: Contextual answer generation
4. **Multi-tenancy**: Organization-level isolation
5. **Authentication**: API key-based access
6. **Deployment**: AWS-ready infrastructure
7. **Widget**: Embeddable JavaScript chat interface

---

## System Architecture

### Technology Stack

**Backend:**
- Django 5.0+ (Python 3.11+)
- PostgreSQL 15+ with pgvector extension
- Celery for async task processing
- Redis for caching and task queue
- Django REST Framework for API

**Document Processing:**
- PyPDF2 / pdfplumber for PDF extraction
- LangChain for chunking and embeddings
- OpenAI / Anthropic / Open-source LLM APIs
- Sentence Transformers for embeddings

**Infrastructure:**
- AWS S3 for document storage
- AWS RDS for PostgreSQL
- AWS ElastiCache for Redis
- AWS ECS/EC2 for application hosting
- CloudFront for CDN (widget delivery)

**Frontend Widget:**
- Vanilla JavaScript (no framework dependencies)
- Shadow DOM for style isolation
- WebSocket or SSE for streaming responses

---

## Database Schema

### Core Models

#### 1. Organization
```python
- id (UUID, primary key)
- name (string)
- slug (string, unique)
- api_key (string, unique, indexed)
- created_at (datetime)
- updated_at (datetime)
- is_active (boolean)
- settings (JSON) # widget customization, LLM config
```

#### 2. Document
```python
- id (UUID, primary key)
- organization (FK to Organization)
- title (string)
- file_path (string) # S3 key
- file_hash (string) # for deduplication
- status (enum: pending, processing, completed, failed)
- metadata (JSON) # original filename, size, upload_date
- created_at (datetime)
- updated_at (datetime)
- created_by (FK to User, nullable)
```

#### 3. DocumentChunk
```python
- id (UUID, primary key)
- document (FK to Document)
- organization (FK to Organization) # denormalized for query performance
- content (text)
- embedding (vector(1536)) # pgvector, dimension depends on model
- chunk_index (integer)
- metadata (JSON) # page_number, section, etc.
- created_at (datetime)
```

#### 4. Conversation
```python
- id (UUID, primary key)
- organization (FK to Organization)
- session_id (UUID, indexed)
- user_identifier (string, nullable) # for tracking
- created_at (datetime)
- updated_at (datetime)
```

#### 5. Message
```python
- id (UUID, primary key)
- conversation (FK to Conversation)
- role (enum: user, assistant, system)
- content (text)
- sources (JSON) # list of relevant chunks
- tokens_used (integer)
- created_at (datetime)
```

#### 6. User (extend Django User)
```python
- organization (FK to Organization)
- role (enum: admin, editor, viewer)
```

---

## API Design

### Authentication
- Header: `X-API-Key: <organization_api_key>`
- All endpoints require valid API key
- Rate limiting per organization

### Core Endpoints

#### Document Management
```
POST   /api/v1/documents/upload/
GET    /api/v1/documents/
GET    /api/v1/documents/{id}/
DELETE /api/v1/documents/{id}/
GET    /api/v1/documents/{id}/status/
POST   /api/v1/documents/{id}/reprocess/
```

#### Search & Query
```
POST   /api/v1/query/
POST   /api/v1/search/ # semantic search only
GET    /api/v1/conversations/
GET    /api/v1/conversations/{id}/messages/
```

#### Widget Endpoints
```
GET    /widget/v1/config/ # widget initialization
POST   /widget/v1/chat/ # send message
GET    /widget/v1/stream/{conversation_id}/ # SSE for streaming
```

#### Admin Endpoints
```
POST   /api/v1/organizations/
GET    /api/v1/organizations/{id}/stats/
PATCH  /api/v1/organizations/{id}/settings/
POST   /api/v1/organizations/{id}/regenerate-key/
```

---

## Document Processing Pipeline

### Phase 1: Upload
1. Validate file (type, size)
2. Upload to S3 with organization prefix
3. Create Document record with status=pending
4. Return document_id immediately
5. Trigger async processing task

### Phase 2: Processing (Celery Task)
1. Download PDF from S3
2. Extract text using pdfplumber
3. Clean and normalize text
4. Split into chunks (LangChain RecursiveCharacterTextSplitter)
   - chunk_size: 1000 tokens
   - chunk_overlap: 200 tokens
5. Generate embeddings for each chunk
   - Batch processing for efficiency
   - Use sentence-transformers or OpenAI API
6. Store chunks with embeddings in DocumentChunk
7. Update Document status=completed

### Phase 3: Error Handling
- Retry logic for transient failures
- Dead letter queue for permanent failures
- Webhook notifications for status updates

---

## Query Flow

### Semantic Search Pipeline
1. Receive user query via API/widget
2. Generate query embedding
3. Perform pgvector similarity search:
   ```sql
   SELECT * FROM document_chunks
   WHERE organization_id = ?
   ORDER BY embedding <=> query_embedding
   LIMIT 5
   ```
4. Retrieve top-k relevant chunks (k=5)
5. Format context for LLM

### LLM Answer Generation
1. Build prompt:
   ```
   Context: {retrieved_chunks}
   Question: {user_query}
   Instructions: Answer based on context only...
   ```
2. Call LLM API (OpenAI, Anthropic, etc.)
3. Stream response back to client
4. Store conversation in database
5. Track token usage for billing

### Caching Strategy
- Cache embeddings for common queries (Redis)
- Cache LLM responses for identical queries (1 hour TTL)
- Cache organization settings

---

## Multi-Organization Isolation

### Database Level
- All queries filtered by `organization_id`
- Row-level security (RLS) in PostgreSQL
- Separate S3 prefixes: `{org_id}/documents/`

### Application Level
- Middleware extracts org from API key
- Attach to request context
- All ORM queries automatically filtered
- Custom manager: `Document.objects.for_organization(org)`

### Security Measures
- API keys hashed in database
- Rate limiting per organization
- Resource quotas (documents, queries/month)
- Audit logging for sensitive operations

---

## Embeddable Widget

### Architecture
```javascript
// Load script
<script src="https://cdn.yourapp.com/widget.js" 
        data-api-key="pk_xxx"></script>

// Widget initializes in Shadow DOM
// Isolated styles, no conflicts with host page
```

### Features
- Customizable theme (colors, position, size)
- Chat history persistence (localStorage)
- Markdown rendering for responses
- Source citations with links
- Mobile responsive
- Accessibility (ARIA labels, keyboard nav)

### Implementation
```javascript
class PolicyChatWidget {
  constructor(apiKey, options) {
    this.apiKey = apiKey;
    this.config = options;
    this.shadowRoot = this.createShadowDOM();
    this.init();
  }
  
  async sendMessage(query) {
    // POST to /widget/v1/chat/
    // Handle streaming response
    // Render in chat UI
  }
}
```

### CDN Delivery
- CloudFront distribution
- Versioned releases: `widget-v1.2.3.js`
- Automatic updates: `widget-latest.js`
- Minified and gzipped

---

## AWS Deployment Architecture

### Infrastructure Components

#### Compute
- **ECS Fargate**: Django application (auto-scaling)
- **EC2 (optional)**: Celery workers (spot instances)
- **Lambda**: Webhook handlers, cleanup tasks

#### Storage
- **RDS PostgreSQL**: Primary database (Multi-AZ)
- **ElastiCache Redis**: Caching and Celery broker
- **S3**: Document storage (encrypted, versioned)

#### Networking
- **VPC**: Private subnets for app/db, public for ALB
- **ALB**: Application Load Balancer with SSL
- **CloudFront**: CDN for widget and static files
- **Route53**: DNS management

#### Monitoring & Logging
- **CloudWatch**: Logs, metrics, alarms
- **X-Ray**: Distributed tracing
- **CloudWatch Dashboards**: Performance monitoring

### Deployment Pipeline
1. GitHub Actions / GitLab CI
2. Build Docker image
3. Push to ECR
4. Update ECS task definition
5. Rolling deployment (blue-green)
6. Run migrations via ECS task
7. Health checks and rollback capability

### Environment Configuration
```
Development: Local Docker Compose
Staging: AWS (small instances)
Production: AWS (auto-scaling, multi-AZ)
```

---

## Implementation Phases

### Phase 1: Core Backend (Weeks 1-2)
- [ ] Django project setup with best practices
- [ ] Database models and migrations
- [ ] PostgreSQL + pgvector configuration
- [ ] Organization and API key authentication
- [ ] Document upload API
- [ ] S3 integration
- [ ] Basic admin interface

### Phase 2: Document Processing (Weeks 3-4)
- [ ] Celery setup with Redis
- [ ] PDF extraction pipeline
- [ ] Text chunking implementation
- [ ] Embedding generation (OpenAI or sentence-transformers)
- [ ] Vector storage in pgvector
- [ ] Processing status tracking
- [ ] Error handling and retries

### Phase 3: Search & Query (Weeks 5-6)
- [ ] Semantic search implementation
- [ ] LLM integration (OpenAI/Anthropic)
- [ ] Prompt engineering and templates
- [ ] Conversation management
- [ ] Source citation system
- [ ] Response streaming
- [ ] Caching layer

### Phase 4: API & Security (Week 7)
- [ ] REST API with DRF
- [ ] API documentation (Swagger)
- [ ] Rate limiting
- [ ] Input validation and sanitization
- [ ] CORS configuration
- [ ] Audit logging
- [ ] Unit and integration tests

### Phase 5: Widget (Weeks 8-9)
- [ ] JavaScript widget core
- [ ] Shadow DOM implementation
- [ ] Chat UI components
- [ ] Theme customization
- [ ] Markdown rendering
- [ ] Streaming response handling
- [ ] Mobile responsiveness
- [ ] Browser compatibility testing

### Phase 6: AWS Deployment (Week 10)
- [ ] Terraform/CloudFormation IaC
- [ ] Docker containerization
- [ ] ECS service configuration
- [ ] RDS and ElastiCache setup
- [ ] CloudFront distribution
- [ ] CI/CD pipeline
- [ ] Environment variables management
- [ ] SSL certificates

### Phase 7: Monitoring & Polish (Week 11-12)
- [ ] CloudWatch dashboards
- [ ] Error tracking (Sentry)
- [ ] Performance optimization
- [ ] Load testing
- [ ] Documentation
- [ ] Sample applications
- [ ] Open-source preparation (LICENSE, CONTRIBUTING)

---

## Key Technical Decisions

### 1. Embedding Model Choice
**Options:**
- OpenAI text-embedding-3-small (1536 dims, $0.02/1M tokens)
- Sentence-Transformers all-MiniLM-L6-v2 (384 dims, free, self-hosted)
- Cohere embed-english-v3.0 (1024 dims, $0.10/1M tokens)

**Recommendation**: Start with OpenAI for quality, offer self-hosted option for cost-conscious users.

### 2. LLM Provider
**Options:**
- OpenAI GPT-4 (best quality, expensive)
- Anthropic Claude (good quality, competitive pricing)
- Open-source (Llama 3, Mistral - self-hosted)

**Recommendation**: Support multiple providers via configuration, default to OpenAI.

### 3. Chunking Strategy
**Recommendation**: 
- RecursiveCharacterTextSplitter with 1000 token chunks
- 200 token overlap for context preservation
- Respect paragraph boundaries
- Store metadata (page, section) for citations

### 4. Search Algorithm
**Recommendation**:
- Cosine similarity for initial retrieval
- Re-ranking with cross-encoder for top results (optional)
- Hybrid search (vector + keyword) for better recall (future)

### 5. Multi-tenancy Pattern
**Recommendation**:
- Shared database with organization_id filtering
- Avoid separate databases (operational complexity)
- Use PostgreSQL RLS for defense-in-depth

---

## Performance Considerations

### Optimization Strategies
1. **Database Indexing**
   - B-tree on organization_id, created_at
   - IVFFlat index on embeddings (pgvector)
   - Composite indexes for common queries

2. **Query Optimization**
   - Limit vector search to organization's documents
   - Use approximate nearest neighbor (IVFFlat/HNSW)
   - Prefilter before vector search when possible

3. **Caching**
   - Redis for query embeddings (24h TTL)
   - Redis for LLM responses (1h TTL)
   - CDN for widget and static files

4. **Async Processing**
   - All document processing async (Celery)
   - Webhook notifications for status updates
   - Batch embedding generation

5. **Connection Pooling**
   - pgBouncer for PostgreSQL
   - Redis connection pool
   - HTTP connection pooling for LLM APIs

---

## Security Checklist

- [ ] API key rotation mechanism
- [ ] HTTPS only (enforce)
- [ ] SQL injection prevention (ORM, parameterized queries)
- [ ] XSS protection in widget
- [ ] CSRF tokens for web interface
- [ ] Rate limiting (per org, per IP)
- [ ] Input validation and sanitization
- [ ] File upload size limits
- [ ] Allowed file types whitelist
- [ ] S3 bucket policies (private by default)
- [ ] IAM roles for AWS services (least privilege)
- [ ] Secrets management (AWS Secrets Manager)
- [ ] Audit logging
- [ ] GDPR compliance (data deletion)
- [ ] Regular dependency updates

---

## Cost Estimation (Monthly)

### AWS Infrastructure (Production, Medium Scale)
- ECS Fargate (2 tasks, 2 vCPU, 4GB): ~$100
- RDS PostgreSQL (db.t3.medium, Multi-AZ): ~$150
- ElastiCache Redis (cache.t3.small): ~$30
- S3 storage (100GB): ~$2.30
- Data transfer: ~$50
- CloudFront: ~$20
- **Total Infrastructure**: ~$350/month

### API Costs (Per 10,000 queries)
- OpenAI embeddings (10k queries): ~$0.20
- OpenAI GPT-4 (10k queries, 1k tokens avg): ~$100
- Total API: ~$100/10k queries

### Scaling Factors
- Add ElastiCache/RDS capacity at 100k queries/month
- Add ECS tasks at high traffic
- Consider reserved instances for 40% savings

---

## Testing Strategy

### Unit Tests
- Model methods
- Chunking algorithms
- Embedding generation
- Search functions

### Integration Tests
- API endpoints
- Document processing pipeline
- Multi-tenancy isolation
- Authentication

### End-to-End Tests
- Upload → Process → Query flow
- Widget integration
- Streaming responses

### Performance Tests
- Load testing with Locust
- Vector search benchmarks
- Concurrent processing

### Security Tests
- Penetration testing
- API fuzzing
- XSS/CSRF validation

---

## Open Source Strategy

### Repository Structure
```
policy-chatbot/
├── backend/          # Django app
├── widget/           # JavaScript widget
├── infrastructure/   # Terraform/CloudFormation
├── docs/            # Documentation
├── examples/        # Sample implementations
└── tests/           # Test suite
```

### Documentation
- README with quick start
- API documentation
- Deployment guides (AWS, GCP, self-hosted)
- Widget integration examples
- Contributing guidelines
- Security policy

### License
- **Recommendation**: MIT or Apache 2.0 for maximum adoption

### Community
- GitHub Issues for bugs/features
- Discussions for Q&A
- Contributing guidelines
- Code of conduct

---

## Future Enhancements

### Phase 2 Features
- [ ] Multi-file search (Word, Excel, PowerPoint)
- [ ] OCR for scanned documents
- [ ] Hybrid search (vector + keyword)
- [ ] Advanced filtering (date, department, document type)
- [ ] Analytics dashboard
- [ ] User feedback on answers (thumbs up/down)
- [ ] Fine-tuning on organization's data
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Slack/Teams integration
- [ ] SSO authentication (SAML, OIDC)
- [ ] Webhooks for events
- [ ] GraphQL API
- [ ] Mobile SDK (iOS, Android)

### Scalability Enhancements
- [ ] Dedicated vector database (Pinecone, Weaviate, Qdrant)
- [ ] Distributed processing (multiple Celery workers)
- [ ] Read replicas for database
- [ ] Elasticsearch for keyword search
- [ ] Kubernetes deployment option

---

## Success Metrics

### Key Performance Indicators
1. **Answer Quality**: User satisfaction score (thumbs up %)
2. **Response Time**: P95 latency < 3 seconds
3. **Document Processing**: < 5 minutes per 100-page PDF
4. **Uptime**: 99.9% availability
5. **Cost Efficiency**: < $0.05 per query
6. **Adoption**: Active organizations, queries/month

---

## Risk Mitigation

### Technical Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM API downtime | High | Fallback providers, error messages |
| Database performance | High | Indexing, caching, monitoring |
| Large document processing | Medium | Async processing, timeouts, chunking |
| Widget conflicts with host sites | Medium | Shadow DOM, namespace isolation |
| Multi-tenancy data leaks | Critical | RLS, thorough testing, audit logs |

### Business Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM costs exceed budget | High | Caching, rate limiting, usage monitoring |
| Low adoption | Medium | Great docs, examples, easy setup |
| Security vulnerability | Critical | Regular audits, dependency updates, bug bounty |

---

## Next Steps

1. **Setup Project**: Initialize Django project with best practices
2. **Database**: Setup PostgreSQL with pgvector
3. **Core Models**: Implement Organization, Document, Chunk models
4. **Document Pipeline**: Build upload → extract → chunk → embed flow
5. **Search**: Implement semantic search with pgvector
6. **LLM**: Integrate OpenAI/Anthropic for answer generation
7. **API**: Build REST API with authentication
8. **Widget**: Develop embeddable JavaScript widget
9. **Deploy**: Setup AWS infrastructure with Terraform
10. **Launch**: Documentation, examples, open-source release

---

## Questions to Resolve

1. **Embedding Model**: OpenAI vs self-hosted? (affects cost and deployment)
2. **LLM Provider**: Single provider or multi-provider support?
3. **Authentication**: API key only or also support OAuth for web UI?
4. **Pricing Model**: Free tier? Usage-based billing?
5. **Data Retention**: How long to keep conversations? GDPR compliance?
6. **Rate Limits**: What limits per organization tier?
7. **Widget Customization**: How much control over appearance?
8. **Document Size Limits**: Max PDF size? Max pages?

---

*This plan is a living document and will be updated as decisions are made and implementation progresses.*
