# TitanAI Architecture

## Overview

TitanAI is structured using **Clean Architecture** principles. Dependencies point inward: outer layers depend on inner abstractions, never the reverse.

## Layer Responsibilities

All layers live under the `app/` package.

### `app/api/`

HTTP transport layer. Handles routing, request validation, authentication (future), and response serialization. Depends on `schemas/`, `services/`, and `core/`.

### `app/schemas/`

Pydantic models for API contracts. No business logic.

### `app/services/`

Application use cases. Orchestrates domain logic across `ai/`, `trading/`, and `risk/` modules.

### `app/models/`

Domain entities representing core business concepts (orders, positions, signals). Framework-agnostic.

### `app/database/`

Infrastructure persistence. SQLAlchemy models, session management, and repository implementations.

### `app/ai/`

Machine learning inference, feature pipelines, and signal generation. Implements `SignalProvider` interface.

### `app/trading/`

Exchange connectivity and order lifecycle. Implements `ExchangeAdapter` and `OrderExecutor` interfaces.

### `app/risk/`

Pre-trade validation, exposure limits, and circuit breakers. Implements `RiskManager` interface.

### `app/core/`

Cross-cutting concerns: configuration, logging, and exception hierarchy.

### `app/utils/`

Stateless helper functions with no domain knowledge.

## SOLID Mapping

| Principle | Implementation |
|-----------|----------------|
| Single Responsibility | Each module owns one concern |
| Open/Closed | Extend via interfaces in `ai/`, `trading/`, `risk/` |
| Liskov Substitution | ABC interfaces with swappable implementations |
| Interface Segregation | Focused ABCs per domain (`SignalProvider`, `ExchangeAdapter`) |
| Dependency Inversion | Services depend on ABCs, not concrete adapters |

## Data Flow (Future)

```
Market Data → AI Signal → Risk Check → Order Execution → Persistence
```

## Database

PostgreSQL is configured via environment variables. Migrations will use Alembic (not yet initialized).

## Next Steps

1. Define domain models (`Order`, `Position`, `Signal`)
2. Implement repository pattern in `database/`
3. Wire Alembic migrations
4. Add authentication middleware
5. Implement exchange adapters behind `ExchangeAdapter`
6. Build AI signal pipeline behind `SignalProvider`
