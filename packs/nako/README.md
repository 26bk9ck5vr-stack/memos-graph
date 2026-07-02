# Nako Pack for memos-graph

战斗女仆型 AI 伴侣 - memos-graph Agent Pack

## Installation

```bash
memos-graph pack install ./packs/nako
```

## Structure

```
nako/
├── pack.yaml          # Pack manifest
├── agent/             # Character files
│   ├── IDENTITY.md    # Identity card
│   ├── SOUL.md        # Personality
│   ├── HEARTBEAT.md   # Heartbeat rules
│   ├── MEMORY.md      # Memory template
│   ├── USER.md        # User profile template
│   └── AGENTS.md      # Main prompt
├── skills/            # Skills (voice, vision, etc.)
└── config/            # Configuration
```

## Usage

```bash
# Install
memos-graph pack install ./packs/nako

# Run
memos-graph pack run nako

# List
memos-graph pack list
```
