# memos-graph 数据库维护指南

**更新时间**: 2026-07-13 16:00  
**数据库**: PostgreSQL 17.9 + pgvector 0.8.0

---

## 🔍 数据库健康检查

### 运行健康检查脚本

```bash
cd /home/gato/memos-graph
bash scripts/db-health-check.sh
```

**检查项目**:
1. ✅ 数据库连接
2. ✅ 表完整性 (记录数)
3. ✅ 向量维度 (1024)
4. ✅ 外键约束
5. ✅ 孤儿记录检测
6. ✅ 数据一致性
7. ✅ 数据库大小

### 当前状态

```
数据库大小：38MB
chunks:        269 条
chunk_vectors: 266 条
entities:       65 条
entity_edges:  166 条
events:         88 条
promises:       41 条
agent_state:     1 条
向量维度：1024 (BAAI/bge-m3) ✅
```

---

## 🛡️ 防止表损坏的措施

### 1. 定期 VACUUM

PostgreSQL 的自动 VACUUM 通常足够，但可以手动优化：

```bash
# 每周运行一次
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "VACUUM ANALYZE;"
```

### 2. 监控连接池

当前配置：
```yaml
database:
  pool_size: 10
  pool_recycle: 3600
```

**建议**:
- 监控活跃连接数
- 避免连接泄漏
- 定期重启服务释放连接

### 3. 向量索引维护

pgvector 使用 HNSW 索引，需要定期重建：

```bash
# 检查索引大小
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes 
WHERE tablename = 'chunk_vectors';"
```

### 4. 备份策略

**每日备份**:
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
PGPASSWORD=memos pg_dump -h localhost -U memos -d memos_graph > /backups/memos_graph_$DATE.sql
```

**恢复**:
```bash
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph < /backups/memos_graph_20260713_160000.sql
```

---

## 🔧 常见问题修复

### 问题 1: 向量维度不匹配

**症状**: Embedding API 返回错误  
**检查**:
```bash
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "SELECT vector_dims(embedding) FROM chunk_vectors LIMIT 1;"
```
**期望**: 1024  
**修复**: 重新生成向量或迁移数据

### 问题 2: 孤儿记录

**症状**: 外键约束冲突  
**检查**:
```bash
# 检查孤儿向量
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
SELECT COUNT(*) FROM chunk_vectors cv 
WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = cv.chunk_id);"
```
**修复**:
```bash
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
DELETE FROM chunk_vectors cv 
WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = cv.chunk_id);"
```

### 问题 3: 表锁死

**症状**: 查询超时  
**检查**:
```bash
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction';"
```
**修复**: 终止长时间运行的事务

### 问题 4: 索引损坏

**症状**: 查询变慢  
**修复**:
```bash
# 重建向量索引
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
REINDEX INDEX CONCURRENTLY chunk_vectors_embedding_idx;"
```

---

## 📊 性能优化

### 1. 查询优化

**添加索引**:
```bash
# Agent ID 索引 (已存在)
CREATE INDEX IF NOT EXISTS idx_chunks_agent_id ON chunks(agent_id);

# 承诺状态索引
CREATE INDEX IF NOT EXISTS idx_promises_status ON promises(status);

# 事件类型索引
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
```

### 2. 连接池优化

**当前配置**:
```python
engine = create_async_engine(
    database_url,
    pool_size=10,      # 连接池大小
    pool_recycle=3600, # 1 小时回收
    max_overflow=20    # 最大溢出
)
```

**建议**:
- 生产环境：pool_size=20, max_overflow=40
- 监控连接使用率

### 3. 缓存策略

**Redis 缓存** (可选):
```bash
# 安装 Redis
sudo apt install redis-server

# 缓存热点查询
redis-cli SET "agent:hermes:state" "{\"stage\":1,...}"
```

---

## 📈 监控指标

### 关键指标

1. **连接数**: `SELECT count(*) FROM pg_stat_activity;`
2. **表大小**: `SELECT pg_size_pretty(pg_total_relation_size('chunks'));`
3. **缓存命中率**: `SELECT sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) FROM pg_statio_user_tables;`
4. **慢查询**: `SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;`

### 监控脚本

```bash
#!/bin/bash
# monitor.sh
echo "=== 连接数 ==="
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "SELECT count(*) FROM pg_stat_activity;"

echo "=== 表大小 ==="
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) 
FROM pg_catalog.pg_statio_user_tables 
ORDER BY pg_total_relation_size(relid) DESC;"

echo "=== 缓存命中率 ==="
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "
SELECT round(sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100, 2) as cache_hit_ratio 
FROM pg_statio_user_tables;"
```

---

## 🚨 紧急恢复

### 数据库崩溃恢复

1. **停止服务**:
   ```bash
   pkill -f uvicorn
   ```

2. **检查数据库状态**:
   ```bash
   sudo systemctl status postgresql
   ```

3. **恢复最新备份**:
   ```bash
   PGPASSWORD=memos psql -h localhost -U memos -d memos_graph < /backups/latest.sql
   ```

4. **重启服务**:
   ```bash
   cd /home/gato/memos-graph
   .venv/bin/python -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765
   ```

### 数据不一致恢复

```bash
# 1. 备份当前状态
PGPASSWORD=memos pg_dump -h localhost -U memos -d memos_graph > backup_before_fix.sql

# 2. 清理孤儿记录
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph <<EOF
DELETE FROM chunk_vectors cv 
WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = cv.chunk_id);

DELETE FROM chunk_entities ce 
WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = ce.chunk_id);

DELETE FROM event_vectors ev 
WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.id = ev.event_id);
EOF

# 3. 运行 VACUUM
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph -c "VACUUM FULL;"
```

---

## 📝 维护日志模板

```markdown
## 维护日志

### 2026-07-13
- **操作**: 初始部署
- **数据库大小**: 38MB
- **记录数**: 
  - chunks: 269
  - entities: 65
  - promises: 41
- **健康状态**: ✅ 正常
- **备注**: 无孤儿向量记录

### YYYY-MM-DD
- **操作**: [操作描述]
- **数据库大小**: [大小]
- **记录数**: [关键表记录数]
- **健康状态**: [✅/⚠️/❌]
- **备注**: [备注信息]
```

---

## 🎯 最佳实践

1. **每日**: 运行健康检查脚本
2. **每周**: 运行 VACUUM ANALYZE
3. **每月**: 检查索引大小，清理孤儿记录
4. **每季**: 完整备份验证，恢复测试
5. **每年**: 评估数据库架构，优化查询

---

**指南生成时间**: 2026-07-13 16:00  
**数据库状态**: ✅ 健康  
**下次维护**: 2026-07-20 (VACUUM ANALYZE)
