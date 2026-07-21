# Known Issues - memos-graph v0.9.0-beta

**Last Updated**: 2026-07-21  
**Severity Legend**: 🔴 Critical | 🟡 High | 🟢 Medium | ⚪ Low

---

## 🔴 Critical (Blocking Production Use)

### 1. Missing `relationships` Table
**Impact**: Nako's core "user↔agent relationship evolution" story cannot be told.  
**Status**: Schema not implemented.  
**Workaround**: None.  
**Fix Target**: v1.0.0

### 2. Pack Runtime Not Implemented
**Impact**: Cannot execute packs (only install/enable/disable).  
**Status**: `pack/runner.py` raises `NotImplementedError`.  
**Workaround**: Manual pack execution.  
**Fix Target**: v1.5.0

### 3. Heartbeat Scheduler Not Implemented
**Impact**: No active message scheduling.  
**Status**: `heartbeat/scheduler.py` is ABC skeleton.  
**Workaround**: Manual heartbeat triggering.  
**Fix Target**: v1.5.0

---

## 🟡 High (Major Features Missing)

### 4. Missing Write API Endpoints
**Impact**: System is read-only for many resources.

**Missing Endpoints**:
- `POST /api/v1/packs/:id/update`
- `POST /api/v1/packs/:id/run`
- `PUT /api/v1/agents/:id/state`
- `PUT /api/v1/promises/:id` (mark fulfilled/broken)
- `PUT /api/v1/users/:id/profile`
- `POST /api/v1/users/:id/merge`

**Status**: API design complete, implementation pending.  
**Fix Target**: v1.0.0 (critical ones)

### 5. Missing Schema Tables (4/16)
**Impact**: Feature degradation.

**Missing Tables**:
- `chunk_edges` (entity co-occurrence)
- `skills` (v1 feature)
- `task_summaries` (v1 feature)
- `relationships` (v2 core - see #1)

**Status**: Migrations not written.  
**Fix Target**: v1.0.0 (`relationships`), v1.5.0 (others)

### 6. Test API Drift
**Impact**: 18/46 tests failing (39% pass rate).

**Failure Types**:
- ImportError (9/20): Missing exports in `__all__`
- API signature drift: `RecallEngine(embedding_service=...)` vs `embedding_provider=...`
- Config drift: `assert 1024 == 768` (embedding dimension mismatch)

**Status**: Tests written for different API than implemented.  
**Fix Target**: v1.0.0

---

## 🟢 Medium (Degraded Functionality)

### 7. context_engine is Dead Code
**Impact**: None (not used).  
**Status**: Syntax error fixed, but module has no imports.  
**Recommendation**: Delete entire module.  
**Fix Target**: v1.0.0 (deletion)

### 8. packs/nako is Empty Shell
**Impact**: No working example pack.  
**Status**: Only `pack.yaml` + `README.md` + `install.sh`.  
**Missing**: `agent/`, `skills/`, `config/`, `scripts/`.  
**Fix Target**: v1.5.0

### 9. Viewer is Static HTML
**Impact**: No dynamic dashboard.  
**Status**: 3 HTML templates, no server-side rendering.  
**Fix Target**: v2.0.0

### 10. Ingest Extractors Missing
**Impact**: Event/promise extraction not automated.  
**Status**: `event_extractor.py` and `promise_extractor.py` not implemented.  
**Fix Target**: v1.5.0

---

## ⚪ Low (Cosmetic/Documentation)

### 11. Version Number Mismatch
**Impact**: Confusion about project maturity.  
**Status**: Corrected from v2.0.0 to v0.9.0-beta.  
**Fix**: README, RELEASE, pyproject.toml updated.

### 12. Config Example Dimension Mismatch
**Impact**: Confusion for new users.  
**Status**: `config.example.yaml` says 768, actual is 1024 (bge-m3).  
**Fix Target**: v1.0.0

---

## Summary by Category

| Category | Issues | Severity |
|----------|--------|----------|
| **Schema** | 4 missing tables | 🔴 Critical |
| **API** | 7 write endpoints missing | 🟡 High |
| **Runtime** | Pack + Heartbeat not implemented | 🔴 Critical |
| **Tests** | 28/46 failing | 🟡 High |
| **Examples** | Nako pack empty | 🟢 Medium |
| **Docs** | Version mismatch fixed | ⚪ Low |

---

## How to Contribute

If you want to help fix these issues:

1. **Pick an issue** from the list above
2. **Check** `REALITY_CHECK.md` for detailed gap analysis
3. **Follow** `docs/TASK_BREAKDOWN.md` for implementation tasks
4. **Submit** a PR with tests

---

## Questions?

- See [REALITY_CHECK.md](REALITY_CHECK.md) for honest completion assessment
- See [AUDIT_RESPONSE.md](AUDIT_RESPONSE.md) for audit findings
- See [docs/DESIGN.md](docs/DESIGN.md) for v2.0 specification

**Last Honest Update**: 2026-07-21
