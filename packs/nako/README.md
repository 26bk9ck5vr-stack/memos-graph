# Nako Pack - Basic Implementation

This pack implements a basic "battle maid" AI companion personality with:
- Heartbeat-based proactive messaging
- Memory integration with memos-graph
- Skill loading framework

## Structure

```
nako/
├── pack.yaml          # Pack manifest (already exists)
├── HEARTBEAT.md       # Heartbeat template (NEW)
├── agent/             # Agent personality
│   ├── custom.md      # Custom personality (NEW)
│   └── MEMORY.md      # Agent memory notes (NEW)
├── scripts/           # Executable scripts
│   └── main.sh        # Main entry script (NEW)
└── config/            # Pack configuration
    └── default.yaml   # Default config (NEW)
```

## What Works (v1.0.0-beta)

- ✅ Pack installation (pack/manager.py)
- ✅ Heartbeat scheduling (heartbeat/scheduler.py)
- ✅ Script execution (pack/runner.py)
- ✅ Memory integration (memos-graph API)

## What Doesn't Work Yet (v1.5.0+)

- ❌ Real voice/vision/hearing skills (require OpenClaw runtime)
- ❌ LLM-based personality generation
- ❌ Conversation flow management
- ❌ Cross-pack skill sharing

## Usage

```bash
# Install
memos-graph packs install ./packs/nako

# Enable
memos-graph packs enable nako

# Run interactively
memos-graph packs run nako --interactive "你好"

# View heartbeat
memos-graph heartbeat check --agent nako
```

## Configuration

Edit `config/default.yaml` to customize:
- Heartbeat intervals
- Memory preferences
- Skill activation