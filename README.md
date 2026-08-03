# TitanAI

Production-ready AI cryptocurrency trading platform foundation.

## Architecture

TitanAI follows **Clean Architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│  api/          HTTP layer (FastAPI routes, deps)        │
├─────────────────────────────────────────────────────────┤
│  schemas/      Request/response DTOs (Pydantic)         │
│  services/     Application / use-case orchestration     │
├─────────────────────────────────────────────────────────┤
│  ai/           AI inference & signal generation         │
│  trading/      Order execution & market interaction     │
│  risk/         Risk management & position limits        │
├─────────────────────────────────────────────────────────┤
│  models/       Domain entities                          │
│  database/     Persistence (SQLAlchemy, repositories)   │
├─────────────────────────────────────────────────────────┤
│  core/         Config, logging, shared exceptions       │
│  utils/        Cross-cutting helpers                    │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer    | Technology              |
|----------|-------------------------|
| Backend  | FastAPI, Python 3.11+   |
| Frontend | React (placeholder)   |
| Database | PostgreSQL (placeholder) |
| Container| Docker & Compose      |

## Project Structure

```
TitanAI/
├── app/              FastAPI application
├── frontend/         React placeholder
├── docs/             Documentation
├── docker/           Dockerfiles & compose overrides
├── scripts/          Dev & ops scripts
├── tests/            Integration & unit tests
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- Node.js 18+ (for frontend, when implemented)

### Local Development (Backend)

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend (placeholder): http://localhost:3000

### Run Tests

```bash
pytest tests/ -v
```

## Environment Variables

See [.env.example](.env.example) for all supported configuration options.

## Status

This repository contains the **project foundation only**. Trading logic, AI models, and exchange integrations are not yet implemented.

## License

Proprietary — All rights reserved.
