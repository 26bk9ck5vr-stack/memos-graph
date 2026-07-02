# memos-graph

**Agent state and long-term memory engine** — PostgreSQL + pgvector + knowledge graph backend for AI agents.

## Features

- 🧠 **Multi-layer memory** — Chunks (L1) + Events (L2) + User Profile (L3)
- 🔍 **5-stage recall** — FTS → Vector → RRF → MMR → Graph diffusion
- 📊 **Agent state** — Affinity, mood, energy, stage, last interaction
- 💝 **Promise tracking** — Automatic extraction from conversations
- 🎯 **Entity/Relation graph** — Auto-built knowledge graph with pgvector
- 💓 **Heartbeat scheduler** — LLM-generated proactive messages
- 📦 **Agent Pack protocol** — Standard directory structure for role packs
- 🌐 **Viewer UI** — Web dashboard for state, timeline, promises

## Quick Start

```bash
# Install
uv pip install -e .

# Initialize config
memos-graph init

# Run migrations
memos-graph migrate

# Start daemon
memos-graph serve --port 8765

# Start viewer
memos-graph viewer --port 8080
```

## Project Structure

```
memos-graph/
├── src/memos_graph/       # Main package
│   ├── cli.py             # Click CLI
│   ├── server.py          # FastAPI app
│   ├── config.py          # Pydantic settings
│   ├── llm/               # 35B LLM client + prompts
│   ├── db/                # SQLAlchemy models + session
│   ├── storage/           # Repository layer
│   ├── embedding/         # Embedding providers
│   ├── recall/            # 5-stage recall engine
│   ├── pack/              # Agent Pack loader
│   ├── heartbeat/         # Heartbeat scheduler
│   └── viewer/            # Viewer HTTP server
├── packs/                 # Official Agent Packs
│   └── nako/              # MetaPact Nako pack
├── tests/                 # pytest tests
├── scripts/               # Install/deploy scripts
└── systemd/               # systemd unit files
```

## License

MIT
