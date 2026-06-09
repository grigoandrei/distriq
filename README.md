# Distriq

A distributed job scheduler built with Python. Define jobs with cron schedules via a REST API, and have them executed reliably across multiple worker processes with no duplicate execution.

## Architecture

```
User → FastAPI (API Server) → PostgreSQL (Job Store)
                                    ↓
                            Scheduler (polling loop)
                                    ↓
                              Redis (job queue + locks)
                                    ↓
                            Worker 1, Worker 2, ... Worker N
                                    ↓
                            PostgreSQL (results, logs)
```

Three independent processes coordinate through PostgreSQL and Redis:

- **API Server** — REST API for job CRUD, manual triggers, observability
- **Scheduler** — Evaluates cron expressions, enqueues due jobs every 15 seconds
- **Worker** — Picks up jobs from Redis, acquires distributed locks, executes Python scripts

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Pydantic |
| Database | PostgreSQL + SQLAlchemy (async) |
| Queue/Locking | Redis |
| Migrations | Alembic |
| Containerization | Docker |
| CI/CD | GitHub Actions |

## Getting Started

### Prerequisites

- Python 3.12+
- Docker/Podman (for PostgreSQL and Redis)

### Local Development

```bash
# Clone and set up
git clone <repo-url>
cd distriq
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env
# Edit .env with your database credentials

# Start infrastructure
podman compose up -d postgres redis

# Run database migrations
alembic upgrade head

# Start the API
uvicorn distriq.api.app:app --reload

# Start the scheduler (separate terminal)
python -m distriq.scheduler.main

# Start a worker (separate terminal)
python -m distriq.worker.main
```

### Docker (full system)

```bash
podman compose up -d
```

This starts all 5 services: PostgreSQL, Redis, API, Scheduler, Worker.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Create a job |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{id}` | Get job details |
| DELETE | `/jobs/{id}` | Soft-delete a job |
| POST | `/jobs/{id}/trigger` | Manually trigger a job |
| GET | `/jobs/{id}/runs` | List job runs (paginated) |
| GET | `/jobs/{id}/runs/{run_id}` | Get run details |
| GET | `/health` | Service health check |

### Example: Create a Job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "daily-report",
    "command": "scripts/generate_report.py",
    "cron_expression": "0 8 * * *"
  }'
```

### Example: Trigger a Job Manually

```bash
curl -X POST http://localhost:8000/jobs/<job_id>/trigger
```

## Running Tests

```bash
pytest tests/ -v
```

Tests use a separate test database and mock Redis. Requires PostgreSQL running locally.

## Project Structure

```
src/distriq/
├── api/
│   ├── app.py              # FastAPI application
│   └── routers/
│       ├── jobs.py         # Job CRUD + trigger + observability
│       └── health.py       # Health check endpoint
├── scheduler/
│   └── main.py             # Cron evaluation + enqueue loop
├── worker/
│   └── main.py             # Queue consumer + script executor
├── models/
│   ├── database.py         # SQLAlchemy models
│   └── schema.py           # Pydantic request/response schemas
├── config.py               # Settings from environment
├── database.py             # Async SQLAlchemy engine
└── redis.py                # Async Redis connection
```

## Key Concepts

- **Distributed Locking** — Redis `SET NX EX` prevents duplicate job execution
- **Cron Scheduling** — Jobs fire automatically based on cron expressions
- **Soft Deletes** — Deleted jobs are marked inactive, history preserved
- **Pagination** — Run history is paginated for large datasets
- **Health Checks** — Database connectivity and worker liveness monitoring
