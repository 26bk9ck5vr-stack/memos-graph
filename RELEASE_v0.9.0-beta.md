# Release v0.9.0-beta

**Date**: 2026-07-21  
**Status**: Beta Release - Core Features Functional

## What's New

### ✅ Completed (Core Loop)
- Real-time sync API (35-50ms write latency)
- 7-stage recall pipeline (FTS + RRF + MMR + Time Decay)
- pg_jieba Chinese FTS integration (100% trigger rate)
- BAAI/bge-m3 embedding via SiliconFlow
- SiliconFlow rerank API (BAAI/bge-reranker-v2-m3)
- Basic API endpoints (25 routes, 85% read operations)

### ⚠️ In Progress (v2.0 Roadmap)
- Relationships system (schema missing - core Nako feature)
- Pack runtime (ABC interfaces defined)
- Heartbeat scheduler (skeleton implemented)
- Nako pack example (placeholder only)

### 🔧 Fixed
- `context_engine/__init__.py` syntax error
- `requirements.txt` - rewritten with core Python dependencies

## Known Issues

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for complete list.

## Upgrade Notes

This is a beta release. Not recommended for production use.

### Breaking Changes
- Version changed from v2.0.0 to v0.9.0-beta (honest versioning)
- API endpoints may change before v1.0.0

## Roadmap to v1.0.0

- [ ] Implement `relationships` table + migration
- [ ] Implement critical write APIs (promises/:id PUT, events/search)
- [ ] Complete heartbeat scheduler
- [ ] Complete pack runner
- [ ] Fix test API drift (18/46 → 40/46 pass)

## Roadmap to v2.0.0

See [REALITY_CHECK.md](REALITY_CHECK.md) for complete gap analysis.

---

**Previous Version**: v2.0.0 (overstated, corrected to v0.9.0-beta)  
**Next Version**: v1.0.0 (target: 2 weeks)
