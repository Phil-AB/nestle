# Forms Capital OCR System - Implementation Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture](#architecture)
4. [Directory Structure](#directory-structure)
5. [Core Modules](#core-modules)
6. [API Endpoints](#api-endpoints)
7. [Frontend Components](#frontend-components)
8. [Services](#services)
9. [Configuration](#configuration)
10. [Database Schema](#database-schema)
11. [Agent Systems](#agent-systems)
12. [Deployment](#deployment)

---

## Project Overview

**Forms Capital** is a sophisticated **Agentic AI Document Processing System** designed for banking and financial institutions. The system leverages advanced AI technologies (LangChain, LangGraph) to extract, process, analyze, and generate documents with a focus on:

- Banking document processing
- Loan application automation
- Financial document management
- Risk assessment and underwriting
- Automated approval workflows

### Key Capabilities
- Universal document processing (PDF, images, Excel)
- Multi-provider OCR/Extraction (Reducto, Google Document AI)
- AI-powered banking insights generation
- Automated form population with LangGraph agents
- Email automation and notification systems
- Analytics and reporting dashboards

---

## Technology Stack

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.10+ | Core application logic |
| Framework | FastAPI | RESTful API framework |
| Database | PostgreSQL | Primary data storage |
| ORM | SQLAlchemy + asyncpg | Async database operations |
| Cache | Redis | Performance optimization |

### AI/ML
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | LangChain | LLM orchestration |
| Framework | LangGraph | Agentic workflows |
| LLMs | OpenAI GPT | Text generation |
| LLMs | Anthropic Claude | Advanced reasoning |
| LLMs | Google Gemini | Multi-modal processing |

### Document Processing
| Component | Technology | Purpose |
|-----------|-----------|---------|
| OCR | Reducto API | Document extraction |
| OCR | Google Document AI | Enterprise OCR |
| Processing | PyPDF2, pdfplumber | PDF manipulation |

### Frontend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 16 | React framework |
| Language | TypeScript | Type safety |
| Styling | Tailwind CSS | Utility-first CSS |
| State | React Hooks | State management |

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Next.js Frontend                        │
│  (Dashboard, Analytics, Document Management, Insights UI)       │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST API
┌────────────────────────────┴────────────────────────────────────┐
│                         FastAPI Backend                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │   V1     │ │   V2     │ │  Auth    │ │  Admin   │          │
│  │  API     │ │  API     │ │ Middleware│ │  Endpoints│         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
└───────┼────────────┼────────────┼────────────┼─────────────────┘
        │            │            │            │
┌───────┴────────────┴────────────┴────────────┴─────────────────┐
│                      Core Modules Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  Extraction  │ │  Generation  │ │  Population  │           │
│  │   Module     │ │   Module     │ │   Module     │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│  ┌──────────────┐ ┌──────────────┐                            │
│  │  Automation  │ │   Shared     │                            │
│  │   Module     │ │   Utils      │                            │
│  └──────────────┘ └──────────────┘                            │
└───────┬────────────────────────────────────────────────────────┘
        │
┌───────┴─────────────────────────────────────────────────────────┐
│                    External Services Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Reducto  │ │  Google  │ │ OpenAI   │ │Anthropic │          │
│  │   API    │ │  DocAI   │ │   API    │ │   API    │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐                                     │
│  │PostgreSQL│ │  Redis   │                                     │
│  │ Database │ │  Cache   │                                     │
│  └──────────┘ └──────────┘                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Module Architecture

The system follows a **modular, provider-agnostic architecture**:

1. **Extraction Module** - Universal document extraction with pluggable providers
2. **Generation Module** - Template-based document generation
3. **Population Module** - AI-powered form population
4. **Automation Module** - Agentic workflows for automation
5. **Shared Layer** - Common utilities and contracts

---

## Directory Structure

```
/home/ubuntu/Projects/ocr/
├── config/                          # Centralized configuration
│   ├── llm.yaml                    # LLM provider configs
│   ├── document_config.yaml        # Document type definitions
│   ├── providers.yaml              # OCR provider configs
│   ├── generation/                 # Generation module configs
│   └── storage/                    # Storage backend configs
│
├── modules/                        # Core processing modules
│   ├── extraction/                # Document extraction
│   │   ├── parser/               # Extraction providers
│   │   ├── storage/              # Document storage
│   │   ├── validation/           # Data validation
│   │   ├── ground_truth/         # Accuracy validation
│   │   └── agents/               # Extraction agents
│   │
│   ├── generation/                # Document generation
│   │   ├── core/                 # Core interfaces
│   │   ├── templates/            # Document templates
│   │   ├── renderers/            # Output renderers
│   │   ├── data_providers/       # Data sources
│   │   ├── mappers/              # Template mappers
│   │   └── services/             # Generation services
│   │
│   ├── population/                # Form population
│   │   ├── core/                 # Population engine
│   │   ├── agents/               # LangGraph agents
│   │   ├── form_filler/          # PDF filling
│   │   ├── mappers/              # Field mapping
│   │   └── data_providers/       # Data providers
│   │
│   └── automation/                # Automation workflows
│       ├── agents/               # Automation agents
│       └── services/             # Email & approval services
│
├── shared/                        # Shared utilities
│   ├── contracts/                # Pydantic schemas
│   ├── providers/                # LLM providers
│   └── utils/                    # Common utilities
│
├── src/                           # Source code
│   ├── api/                      # API endpoints
│   │   ├── v1/                  # Legacy API
│   │   └── v2/                  # Modern API
│   ├── database/                 # Database models
│   └── ui/                       # Next.js frontend
│
├── tests/                         # Test suite
├── migrations/                    # Database migrations
├── templates/                     # Document templates
├── uploads/                       # File storage
├── static/                        # Static assets
└── logs/                          # Application logs
```

---

## Core Modules

### 1. Extraction Module (`/modules/extraction/`)

**Purpose**: Universal document extraction with provider-agnostic architecture

#### Parser (`/modules/extraction/parser/`)
- `base_parser.py` - Abstract base for all parsers
- `reducto_parser.py` - Reducto API integration
- `google_parser.py` - Google Document AI integration
- `parser_factory.py` - Registry pattern for provider selection

#### Storage (`/modules/extraction/storage/`)
- `storage_service.py` - Universal document storage with backends
- `backends/` - Storage backend implementations

#### Validation (`/modules/extraction/validation/`)
- `validation_engine.py` - Validates extracted data against schemas
- `schema_validators/` - Document-type-specific validators

#### Ground Truth (`/modules/extraction/ground_truth/`)
- `ground_truth_service.py` - Accuracy validation against ground truth
- `comparison.py` - Extracted vs ground truth comparison

#### Agents (`/modules/extraction/agents/`)
- LangGraph-based extraction agents
- Multi-step extraction workflows

### 2. Generation Module (`/modules/generation/`)

**Purpose**: Template-based document generation

#### Core (`/modules/generation/core/`)
- `interfaces.py` - Abstract interfaces
- `registry.py` - Component registration system
- `exceptions.py` - Generation-specific exceptions

#### Templates (`/modules/generation/templates/`)
- `template_manager.py` - Template loading and management
- `mappings/` - Field to template mappings

#### Renderers (`/modules/generation/renderers/`)
- `pdf_renderer.py` - PDF output generation
- `docx_renderer.py` - DOCX output generation
- `html_renderer.py` - HTML output generation

#### Data Providers (`/modules/generation/data_providers/`)
- `database_provider.py` - Database data source
- `api_provider.py` - API data source

#### Mappers (`/modules/generation/mappers/`)
- Data to template field mapping

#### Services (`/modules/generation/services/`)
- `banking_insights_service.py` - AI-powered banking analysis
- `approval_letter_service.py` - Approval document generation
- `models/insights_models.py` - Banking domain models
- `prompts/insights_prompts.py` - LLM prompts for insights

### 3. Population Module (`/modules/population/`)

**Purpose**: AI-powered PDF form population

#### Core (`/modules/population/core/`)
- `population_engine.py` - Main population orchestration
- `types.py` - Population type definitions
- `exceptions.py` - Population-specific exceptions

#### Agents (`/modules/population/agents/`)
- `population_agent.py` - LangGraph-based population agent
- Field mapping intelligence
- Multi-document data merging

#### Form Filler (`/modules/population/form_filler/`)
- `pdf_filler.py` - PDF field filling logic
- Form validation

#### Mappers (`/modules/population/mappers/`)
- `field_mapper.py` - Intelligent field mapping
- Confidence scoring

#### Data Providers (`/modules/population/data_providers/`)
- Various data sources for form population

### 4. Automation Module (`/modules/automation/`)

**Purpose**: Agentic AI workflows for business automation

#### Agents (`/modules/automation/agents/`)
- `base_automation_agent.py` - Base automation agent
- `automated_approval_agent.py` - Loan approval automation
  - Eligibility checking (risk score >= 70)
  - Approval letter generation
  - Status updates
  - Email notifications

#### Services (`/modules/automation/services/`)
- `email_service.py` - Email sending service
- `approval_letter_service.py` - Approval document generation

### 5. Shared Layer (`/shared/`)

#### Contracts (`/shared/contracts/`)
- Pydantic schemas for API contracts
- Request/response models
- Domain models

#### Providers (`/shared/providers/`)
- `llm_provider.py` - LLM abstraction
- `openai_provider.py` - OpenAI implementation
- `anthropic_provider.py` - Anthropic implementation
- `gemini_provider.py` - Google Gemini implementation

#### Utils (`/shared/utils/`)
- `config.py` - Configuration utilities
- `logging.py` - Logging setup
- `helpers.py` - Common helper functions

---

## API Endpoints

### V1 API (Legacy)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/documents/upload` | POST | Upload documents |
| `/api/v1/documents/{id}` | GET | Get document details |
| `/api/v1/extract` | POST | Extract data from documents |
| `/api/v1/validate` | POST | Validate extracted data |

### V2 API (Modern)

#### Generation Endpoints (`/api/v2/generation/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Generate documents from templates |
| `/batch` | POST | Batch document generation |
| `/templates` | GET | List available templates |
| `/download/{job_id}` | GET | Download generated documents |
| `/status/{job_id}` | GET | Check generation status |

#### Population Endpoints (`/api/v2/population/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/populate` | POST | Populate PDF forms with AI agents |
| `/forms` | GET | List available form templates |
| `/health` | GET | Health check |

#### Insights Endpoints (`/api/v2/insights/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customer` | POST | Generate banking customer insights |
| `/risk-assessment` | POST | Assess customer risk |
| `/eligibility` | POST | Check product eligibility |
| `/recommendations` | POST | Get personalized recommendations |

#### Automation Endpoints (`/api/v2/automation/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/approval/start` | POST | Start automated approval workflow |
| `/approval/status/{id}` | GET | Check approval status |
| `/email/send` | POST | Send notification email |

#### Profiles Endpoints (`/api/v2/profiles/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | List document profiles |
| `/{id}` | GET | Get profile details |
| `/create` | POST | Create new profile |
| `/{id}/documents` | GET | Get profile documents |

#### Analytics Endpoints (`/api/v2/analytics/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Dashboard metrics |
| `/performance` | GET | Performance metrics |
| `/documents` | GET | Document statistics |

#### Integration Endpoints (`/api/v2/integration/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/pre-loan` | POST | Pre-loan integration |
| `/status/{id}` | GET | Integration status |

---

## Frontend Components

### Pages (`/src/ui/app/`)

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `page.tsx` | Dashboard with stats and quick actions |
| `/documents` | `documents/page.tsx` | Document management |
| `/upload` | `upload/page.tsx` | File upload interface |
| `/generation` | `generation/page.tsx` | Document generation |
| `/insights` | `insights/page.tsx` | Banking insights dashboard |
| `/analytics` | `analytics/page.tsx` | Analytics and reporting |
| `/validation` | `validation/page.tsx` | Document validation |
| `/shipments` | `shipments/page.tsx` | Shipment management |
| `/ground-truth` | `ground-truth/page.tsx` | Ground truth entry |

### Key Components (`/src/ui/components/`)

| Component | Description |
|-----------|-------------|
| `dashboard.tsx` | Main dashboard with statistics cards |
| `document-viewer.tsx` | Document preview component |
| `pdf-viewer.tsx` | PDF rendering component |
| `analytics-dashboard.tsx` | Analytics visualization |
| `automation-panel.tsx` | Automation control panel |
| `profile-selector.tsx` | Document profile selector |
| `risk-reasoning-viewer.tsx` | AI risk assessment display |
| `pre-loan-status-badge.tsx` | Pre-loan status indicator |
| `sidebar.tsx` | Navigation sidebar |

---

## Services

### BankingInsightsService

**Location**: `/modules/generation/services/banking_insights_service.py`

**Purpose**: AI-powered banking customer analysis

**Features**:
- Risk assessment using LLMs
- Product eligibility determination
- Personalized recommendations
- Automated underwriting decisions
- Performance caching with Redis

**Methods**:
- `generate_customer_insights()` - Generate comprehensive customer analysis
- `assess_risk()` - Assess customer risk profile
- `check_eligibility()` - Check product eligibility
- `get_recommendations()` - Get personalized product recommendations

### UniversalDocumentStorageService

**Location**: `/modules/extraction/storage/storage_service.py`

**Purpose**: Provider-agnostic document storage

**Features**:
- Works with any extraction provider
- Universal data format transformation
- Configurable document type handling
- Duplicate detection and updating

### PopulationEngine

**Location**: `/modules/population/core/population_engine.py`

**Purpose**: AI-powered PDF form population

**Features**:
- LangGraph-based intelligent field mapping
- Multi-document data merging
- Confidence scoring
- Form validation

### AutomatedApprovalAgent

**Location**: `/modules/automation/agents/automated_approval_agent.py`

**Purpose**: Automated loan approval workflows

**Features**:
- Eligibility checking (risk score >= 70)
- Approval letter generation
- Email notifications
- Status updates

### ProviderFactory

**Location**: `/modules/extraction/parser/parser_factory.py`

**Purpose**: Provider-agnostic parser creation

**Features**:
- Registry pattern for plug-and-play providers
- Support for Reducto, Google Document AI
- Easy addition of new providers

---

## Configuration

### Configuration Files

#### `/config/llm.yaml`
LLM provider configurations with fallbacks
```yaml
providers:
  - name: openai
    model: gpt-4-turbo
    api_key_env: OPENAI_API_KEY
  - name: anthropic
    model: claude-3-opus-20240229
    api_key_env: ANTHROPIC_API_KEY
  - name: gemini
    model: gemini-pro
    api_key_env: GEMINI_API_KEY
```

#### `/config/document_config.yaml`
Document type definitions and validation rules
```yaml
document_types:
  - name: invoice
    fields: [invoice_number, date, amount, vendor]
    required: [invoice_number, amount]
  - name: bill_of_entry
    fields: [...]
```

#### `/config/providers.yaml`
OCR provider configurations
```yaml
extraction_providers:
  - name: reducto
    enabled: true
  - name: google_docai
    enabled: true
```

#### `/config/storage/backends.yaml`
Storage backend configurations
```yaml
backends:
  - type: s3
    bucket: documents
  - type: local
    path: /uploads
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `REDUCTO_API_KEY` | Reducto API key |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | Application secret key |
| `DEBUG` | Debug mode flag |
| `LOG_LEVEL` | Logging level |

---

## Database Schema

### Core Tables

#### Documents
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `shipment_id` | UUID | Shipment reference |
| `document_type` | VARCHAR | Document type |
| `file_path` | VARCHAR | File storage path |
| `status` | VARCHAR | Processing status |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Update timestamp |

#### Shipments
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `reference_number` | VARCHAR | Shipment reference |
| `status` | VARCHAR | Shipment status |
| `created_at` | TIMESTAMP | Creation timestamp |

#### ExtractedData
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Document reference |
| `field_name` | VARCHAR | Field name |
| `field_value` | TEXT | Extracted value |
| `confidence` | FLOAT | Confidence score |

#### ValidationResults
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `document_id` | UUID | Document reference |
| `is_valid` | BOOLEAN | Validation result |
| `errors` | JSONB | Validation errors |
| `validated_at` | TIMESTAMP | Validation timestamp |

#### DocumentProfiles
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR | Profile name |
| `document_type` | VARCHAR | Document type |
| `config` | JSONB | Profile configuration |

#### GenerationJobs
| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `template_id` | VARCHAR | Template used |
| `status` | VARCHAR | Job status |
| `output_path` | VARCHAR | Generated file path |
| `created_at` | TIMESTAMP | Creation timestamp |

---

## Agent Systems

### LangGraph Agents

The system uses **LangGraph** for building stateful, multi-actor AI agents.

#### Population Agent
**Location**: `/modules/population/agents/population_agent.py`

**Workflow**:
1. Analyze form fields
2. Extract relevant data from documents
3. Map data to form fields
4. Fill form with confidence scoring
5. Validate and return result

#### Automated Approval Agent
**Location**: `/modules/automation/agents/automated_approval_agent.py`

**Workflow**:
1. Check customer risk score
2. Verify eligibility (risk >= 70)
3. Generate approval letter
4. Send email notification
5. Update system status

---

## Deployment

### Docker Support

```dockerfile
# Multi-stage build
FROM python:3.10-slim as builder
# ... build steps ...

FROM python:3.10-slim
# ... runtime steps ...
```

### Environment Configurations

- **Development**: `.env.development`
- **Staging**: `.env.staging`
- **Production**: `.env.production`

### Scaling Capabilities

- **Horizontal Scaling**: Stateless API design allows multiple instances
- **Vertical Scaling**: Optimized for resource efficiency
- **Load Balancing**: Compatible with standard load balancers
- **Microservices**: Modular architecture enables service separation

---

## Security Features

- API key authentication
- Secure file upload handling
- Input validation and sanitization
- Audit logging for all actions
- Configurable CORS policies
- Environment-based configuration
- SQL injection prevention (ORM)
- XSS protection

---

## Testing

### Test Structure

```
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
├── e2e/              # End-to-end tests
└── fixtures/         # Test fixtures
```

### Test Coverage

- Module unit tests
- API endpoint tests
- Database integration tests
- Agent workflow tests

---

## Performance Optimization

- **Redis Caching**: Cached LLM responses and database queries
- **Async Processing**: Async/await for I/O operations
- **Connection Pooling**: Database connection pooling
- **Parallel Execution**: Concurrent document processing
- **Lazy Loading**: On-demand resource loading

---

## Development Tools

- **Black**: Code formatting
- **MyPy**: Type checking
- **Ruff**: Fast linting
- **Pytest**: Testing framework
- **Docker**: Containerization

---

## Changelog and Version History

### Recent Branch: `forms-capital`

**New Features Added**:
1. Automation module with approval agent
2. Analytics dashboard with visualization
3. Pre-loan integration endpoints
4. Document profile management
5. Risk reasoning viewer component
6. Pre-loan status badge component

**Modified**:
1. Banking insights service enhancement
2. Insights models and prompts update
3. V2 router updates
4. Dashboard component updates
5. Sidebar navigation updates
6. Global styles updates

### Recent Commits
- `2149c5e` - before enhancement
- `e145b96` - fixing stuff
- `cba177e` - making waves
- `ff957aa` - creating population
- `41a44cf` - creating population

---

## Future Enhancements

### Planned Features
1. Real-time document processing with WebSocket
2. Advanced analytics with ML-based predictions
3. Mobile application support
4. Additional language support
5. More document type templates
6. Enhanced security with 2FA

### Scalability Roadmap
1. Kubernetes deployment guides
2. Message queue integration (RabbitMQ/Kafka)
3. Distributed caching (Redis Cluster)
4. Database read replicas
5. CDN integration for static assets

---

## Contributing

### Code Style Guidelines
- Follow PEP 8 for Python
- Use TypeScript for frontend
- Write descriptive commit messages
- Add tests for new features
- Update documentation

### Git Workflow
1. Create feature branch from `main`
2. Implement with tests
3. Create pull request
4. Code review
5. Merge to main

---

## Support and Documentation

For additional information:
- API Documentation: `/docs/api`
- Architecture Docs: `/docs/architecture`
- Deployment Guide: `/docs/deployment`
- Contributing: `/CONTRIBUTING.md`

---

*Document Generated: 2026-02-02*
*Version: 1.0.0*
*Project: Forms Capital OCR System*
