# memos-graph v2.0

Agent state and long-term memory engine with PostgreSQL + pgvector + knowledge graph.

## Features

- ✅ **Entity Extraction**: LLM-powered extraction of persons, places, organizations, concepts
- ✅ **Event & Promise Tracking**: Structured event stream and promise management
- ✅ **Agent State Management**: Affinity, mood, energy, relationship stages
- ✅ **Vector Search**: 1024-dimensional embeddings with pgvector
- ✅ **Knowledge Graph**: Entity relationships and graph-based retrieval
- ✅ **Agent Pack Protocol**: Standardized pack format with YAML manifest
- ✅ **Heartbeat Scheduler**: Active message scheduling based on agent state

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Pack Layer (Nako, Work-Coder, etc.)                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   nako/     │  │ work-coder/ │  │   custom/   │          │
│  │  pack.yaml  │  │  pack.yaml  │  │  pack.yaml  │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                   │
│         └────────────────┴────────────────┘                   │
│                   memos-graph API                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Recall  │  │  Ingest  │  │  State   │  │ Heartbeat│      │
│  │  Engine  │  │ Pipeline │  │  Manager │  │ Scheduler│      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
│       └─────────────┴─────────────┴─────────────┘             │
│                    SQLAlchemy ORM                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL 15+ with pgvector                               │
│  - chunks / chunk_vectors / chunk_edges                     │
│  - entities / entity_edges                                  │
│  - agent_state / relationships                              │
│  - events / event_vectors                                   │
│  - promises                                                 │
│  - packs                                                    │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### 1. Install PostgreSQL with pgvector

```bash
# Ubuntu/Debian
sudo apt install postgresql-15 postgresql-15-pgvector

# macOS (Homebrew)
brew install postgresql@15
brew install pgvector
```

### 2. Create Database

```bash
createdb memos_graph
psql -d memos_graph -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. Install Python Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure

```bash
cp config.example.yaml ~/.config/memos-graph/config.yaml
# Edit config.yaml with your actual API keys
```

### 5. Run Migrations

```bash
alembic upgrade head
```

### 6. Start Server

```bash
python3 -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765
```

## API Endpoints

### Memories
- `POST /api/v1/memories` - Create memory with entity extraction
- `GET /api/v1/memories` - List memories
- `POST /api/v1/memories/search` - Semantic search

### Agent State
- `GET /api/v1/agents/:id/state` - Get agent state
- `PUT /api/v1/agents/:id/state` - Update agent state

### Packs
- `GET /api/v1/packs` - List registered packs
- `GET /api/v1/packs/:id` - Get pack details
- `POST /api/v1/packs/install` - Install pack from local path
- `PUT /api/v1/packs/:id/enable` - Enable pack
- `PUT /api/v1/packs/:id/disable` - Disable pack

### Heartbeat
- `POST /api/v1/heartbeat/check` - Check and schedule pending heartbeats
- `GET /api/v1/heartbeat/pending` - Get pending heartbeats
- `POST /api/v1/heartbeat/:id/send` - Mark heartbeat as sent

## Agent Pack Structure

```
my-pack/
├── pack.yaml              # Pack manifest
├── agent/
│   ├── IDENTITY.md        # Agent identity
│   ├── SOUL.md            # Personality & values
│   └── HEARTBEAT.md       # Active message rules
├── skills/                # Skills (optional)
│   └── skill_name/
└── scripts/
    └── start.sh           # Startup script
```

### pack.yaml Example

```yaml
id: nako
name: 野木奈子
version: 0.3.0
runtime: openclaw
description: 战斗女仆型 AI 伴侣
author: Your Name
license: MIT

memos_graph:
  required: true
  pack_agent_id: nako
  shared_user_id: default
  default_scope: shared

heartbeat:
  enabled: true
  schedule_seconds: 1800
  thresholds:
    stage_1_hours: 48
    stage_2_hours: 24
    stage_3_hours: 12
    stage_4_hours: 8
    stage_5_hours: 6
```

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
black src/
flake8 src/
```

## License

MIT License

## Credits

- Built with FastAPI + SQLAlchemy + pgvector
- Entity extraction powered by LLM
- Inspired by MetaPact/Nako project
