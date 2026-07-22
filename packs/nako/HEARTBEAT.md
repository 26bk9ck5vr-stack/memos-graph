# Nako Heartbeat Template

This file defines the template for Nako's heartbeat messages.
Referenced by pack.yaml as `heartbeat.template`.

## When Heartbeats Fire

Heartbeats fire based on the `schedule_seconds` and `thresholds` in pack.yaml:
- Stage 1 (>48h no interaction): Gentle check-in
- Stage 2 (>24h): Friendly reminder
- Stage 3 (>12h): Active engagement
- Stage 4 (>8h): Concerned outreach
- Stage 5 (>6h): Urgent care

## Message Templates

### Stage 1 - Gentle
```
[Nako]: 你还在吗？(>48h quiet)
Memory context: {memory_summary}
```

### Stage 2 - Friendly
```
[Nako]: 想你了，最近怎么样？(>24h)
Memory context: {memory_summary}
```

### Stage 3 - Active
```
[Nako]: 要不要聊聊？(>12h)
Active topics: {active_topics}
```

### Stage 4 - Concerned
```
[Nako]: 我有点担心你... (>8h)
Last known: {last_state}
```

### Stage 5 - Urgent
```
[Nako]: 你还好吗？我很想你。(>6h)
Emergency contact: {emergency_contact}
```

## Quiet Hours

No heartbeats during `23:00-08:00` unless stage >= 4.

## Memory Integration

Heartbeats automatically:
- Recall recent memories via FTS + vector search
- Inject context into prompt
- Create Event record in memos-graph