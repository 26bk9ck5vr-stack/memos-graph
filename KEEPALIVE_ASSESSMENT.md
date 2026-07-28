# memos-graph v3.0 保活机制评估报告

**评估日期**: 2026-07-30  
**评估范围**: 心跳、监控、自愈、备份、告警  
**结论**: ⚠️ **部分完善，需要增强**

---

## 📊 **保活机制现状**

### ✅ **已实现的功能**

| 机制 | 状态 | 实现位置 | 说明 |
|------|------|---------|------|
| **健康检查** | ✅ 完整 | `api/health.py` | `/health` 和 `/health/ready` 端点 |
| **心跳规则解析** | ✅ 完整 | `heartbeat/rules.py` | 解析 HEARTBEAT.md 规则 |
| **心跳调度器 (MVP)** | ✅ 基础 | `heartbeat/scheduler.py` | 检查心跳间隔，创建事件 |
| **数据库连接池** | ✅ 完整 | `db/session.py` | asyncpg 连接池 (pool_size=10) |
| **异常处理** | ✅ 完整 | 全代码 | 统一的错误处理机制 |

### ⚠️ **不完善的功能**

| 机制 | 状态 | 缺失内容 | 风险 |
|------|------|---------|------|
| **后台心跳调度** | ❌ 未实现 | `scheduler.py` L37-41 | 无法自动发送心跳 |
| **静默时间管理** | ❌ 未实现 | `scheduler.py` L62 | 可能在非工作时间打扰 |
| **分级阈值执行** | ⚠️ 部分 | `rules.py` 有定义，未执行 | 无法根据阶段调整策略 |
| **LLM 内容生成** | ❌ 未实现 | `scheduler.py` L41 | 心跳消息固定，不智能 |
| **进程监控** | ❌ 缺失 | 无 | 进程崩溃无法自动重启 |
| **资源监控** | ❌ 缺失 | 无 | CPU/内存/磁盘无法监控 |
| **自动备份** | ❌ 缺失 | 无 | 数据丢失风险 |
| **告警通知** | ❌ 缺失 | 无 | 故障无法及时通知 |
| **自动恢复** | ❌ 缺失 | 无 | 故障需人工介入 |

---

## 🔍 **详细分析**

### 1. **健康检查** ✅ 完善

**实现位置**: `src/memos_graph/api/health.py`

**功能**:
- ✅ `/health` - 基础健康检查 (服务器是否运行)
- ✅ `/health/ready` - 就绪检查 (DB + LLM + Embedding)

**代码质量**:
```python
@router.get("/health/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    # 检查数据库
    await session.execute("SELECT 1")
    
    # 检查 LLM API
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{config.llm.base_url}/health")
    
    # 检查 Embedding (Ollama)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{config.embedding.base_url}/api/tags")
```

**评估**: ✅ **完善**，覆盖所有关键依赖

---

### 2. **心跳调度器** ⚠️ 不完善

**实现位置**: `src/memos_graph/heartbeat/scheduler.py`

**已实现 (MVP)**:
- ✅ 解析 HEARTBEAT.md 规则
- ✅ 检查心跳间隔
- ✅ 创建心跳事件
- ✅ 默认规则 (24 小时间隔)

**未实现 (TODO v1.5.0)**:
- ❌ 后台异步调度 (`_task` 定义了但未使用)
- ❌ 静默时间管理 (`quiet_hours` 参数未生效)
- ❌ 分级阈值执行 (`stage_thresholds` 未使用)
- ❌ LLM 生成心跳内容

**代码问题**:
```python
# L66: 定义了 task 但从未启动
self._task: Optional[asyncio.Task] = None

# L48-62: 参数定义了但未使用
def __init__(
    self,
    schedule_seconds: int = 3600,  # ✅ 定义了
    quiet_hours: str | None = None,  # ❌ 未使用
) -> None:
    self._quiet_hours = quiet_hours  # 存储了但从未检查

# L37-42: TODO 注释承认未实现
# TODO (v1.5.0):
# - Async background scheduling
# - Quiet hours enforcement
# - Stage-based thresholds
# - LLM-generated content
```

**评估**: ⚠️ **MVP 状态**，仅能手动调用，无法自动运行

---

### 3. **数据库保活** ✅ 完善

**实现位置**: `src/memos_graph/db/session.py`

**功能**:
- ✅ 连接池 (pool_size=10)
- ✅ 连接回收 (pool_recycle=3600s)
- ✅ 自动重连 (asyncpg 内置)
- ✅ 超时处理 (timeout=30s)

**配置**:
```yaml
database:
  pool_size: 10
  pool_recycle: 3600
```

**评估**: ✅ **完善**，生产级配置

---

### 4. **进程保活** ❌ 缺失

**现状**:
- ❌ 无进程守护 (systemd/supervisor 配置)
- ❌ 无看门狗 (watchdog timer)
- ❌ 无崩溃自动重启
- ❌ 无进程健康检查

**风险**:
- 进程崩溃后需人工重启
- 内存泄漏无法自动恢复
- 长时间运行可能资源耗尽

**评估**: ❌ **严重缺失**，生产环境不可用

---

### 5. **资源监控** ❌ 缺失

**现状**:
- ❌ 无 CPU 监控
- ❌ 无内存监控
- ❌ 无磁盘监控
- ❌ 无网络监控
- ❌ 无数据库连接数监控

**风险**:
- 资源耗尽无法提前预警
- 性能下降无法定位
- 磁盘满导致数据丢失

**评估**: ❌ **严重缺失**

---

### 6. **数据备份** ❌ 缺失

**现状**:
- ❌ 无自动备份脚本
- ❌ 无备份策略 (全量/增量)
- ❌ 无备份验证
- ❌ 无恢复演练

**风险**:
- 数据丢失无法恢复
- 人为误操作无法回滚
- 灾难恢复能力为零

**评估**: ❌ **严重缺失**

---

### 7. **告警通知** ❌ 缺失

**现状**:
- ❌ 无告警规则定义
- ❌ 无通知渠道 (邮件/短信/Slack)
- ❌ 无告警分级 (P0/P1/P2)
- ❌ 无告警聚合

**风险**:
- 故障无法及时感知
- 用户先于运维发现问题
- SLA 无法保障

**评估**: ❌ **严重缺失**

---

## 📈 **保活机制成熟度评估**

| 维度 | 得分 | 说明 |
|------|------|------|
| **健康检查** | ✅ 90% | 覆盖全面，可集成到 K8s |
| **心跳机制** | ⚠️ 40% | MVP 状态，无法自动运行 |
| **进程保活** | ❌ 0% | 完全缺失 |
| **资源监控** | ❌ 0% | 完全缺失 |
| **数据备份** | ❌ 0% | 完全缺失 |
| **告警通知** | ❌ 0% | 完全缺失 |
| **自动恢复** | ❌ 0% | 完全缺失 |
| **数据库保活** | ✅ 100% | 生产级配置 |

**总体得分**: **28/100** ⚠️

**评级**: **开发环境可用，生产环境不可用**

---

## 🛠️ **改进建议**

### P0 (立即实施 - 生产必需)

1. **进程守护** (4h)
   ```bash
   # 添加 systemd 服务配置
   cat > /etc/systemd/system/memos-graph.service << 'EOF'
   [Unit]
   Description=memos-graph v3.0
   After=network.target postgresql.service
   
   [Service]
   Type=simple
   User=gato
   WorkingDirectory=/home/gato/memos-graph
   ExecStart=/home/gato/memos-graph/.venv/bin/python -m uvicorn memos_graph.server:create_app --factory
   Restart=always
   RestartSec=5
   
   [Install]
   WantedBy=multi-user.target
   EOF
   ```

2. **基础监控脚本** (2h)
   ```bash
   # 添加监控脚本
   cat > bin/monitor.sh << 'EOF'
   #!/bin/bash
   # 检查进程
   pgrep -f "memos_graph" || exit 1
   
   # 检查 HTTP 端点
   curl -f http://localhost:8765/api/v1/health/ready || exit 1
   
   # 检查磁盘
   df -h /home | awk 'NR==2 {if ($5 > 90) exit 1}'
   EOF
   ```

3. **自动备份脚本** (2h)
   ```bash
   # 添加备份脚本
   cat > bin/backup.sh << 'EOF'
   #!/bin/bash
   BACKUP_DIR="/backup/memos-graph"
   DATE=$(date +%Y%m%d_%H%M%S)
   
   # 备份数据库
   pg_dump memos_graph | gzip > $BACKUP_DIR/db_$DATE.sql.gz
   
   # 保留最近 7 天
   find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
   EOF
   ```

### P1 (短期实施 - 生产增强)

4. **完善心跳调度器** (8h)
   - 实现后台异步调度
   - 启用静默时间管理
   - 执行分级阈值
   - LLM 生成心跳内容

5. **资源监控集成** (4h)
   - 集成 Prometheus + Grafana
   - 监控 CPU/内存/磁盘/网络
   - 监控数据库连接数
   - 监控 API 响应时间

6. **告警通知系统** (4h)
   - 集成钉钉/企业微信/Slack
   - 定义告警规则 (CPU>90%, 磁盘>85%, API 错误率>5%)
   - 告警分级 (P0/P1/P2)
   - 告警聚合 (避免风暴)

### P2 (长期实施 - 生产优化)

7. **自动恢复机制** (8h)
   - 进程崩溃自动重启 (systemd)
   - 数据库连接自动重连
   - API 超时自动重试
   - 内存泄漏自动检测 + 重启

8. **日志聚合** (4h)
   - 集成 ELK/Loki
   - 结构化日志 (JSON)
   - 日志分级 (INFO/WARN/ERROR)
   - 日志保留策略

9. **性能分析** (4h)
   - 集成 APM (如 Jaeger)
   - 慢查询分析
   - 性能瓶颈定位
   - 容量规划

---

## 📋 **实施清单**

### 立即实施 (P0 - 本周)

- [ ] 创建 systemd 服务配置
- [ ] 创建监控脚本 (`bin/monitor.sh`)
- [ ] 创建备份脚本 (`bin/backup.sh`)
- [ ] 配置 cron 定时任务 (每分钟监控，每天备份)
- [ ] 测试崩溃自动重启
- [ ] 测试备份恢复流程

### 短期实施 (P1 - 本月)

- [ ] 完善心跳调度器 (后台运行)
- [ ] 集成 Prometheus + Grafana
- [ ] 配置告警通知 (钉钉/企业微信)
- [ ] 定义告警规则
- [ ] 部署监控仪表盘

### 长期实施 (P2 - 下季度)

- [ ] 实现自动恢复机制
- [ ] 集成日志聚合 (ELK/Loki)
- [ ] 集成 APM (Jaeger)
- [ ] 性能基准测试
- [ ] 容量规划文档

---

## 🎯 **结论**

### 当前状态

**memos-graph v3.0 的保活机制处于 MVP 状态**:

✅ **优势**:
- 健康检查完善
- 数据库连接池配置专业
- 心跳规则解析完整

❌ **劣势**:
- 心跳调度器无法自动运行
- 进程守护缺失
- 资源监控缺失
- 数据备份缺失
- 告警通知缺失

### 生产就绪度

| 环境 | 就绪度 | 说明 |
|------|--------|------|
| **开发环境** | ✅ 100% | 可以正常使用 |
| **测试环境** | ⚠️ 60% | 需要手动监控 |
| **生产环境** | ❌ 30% | 需要 P0 改进才能使用 |

### 建议

**立即行动** (本周内):
1. 配置 systemd 进程守护
2. 添加基础监控脚本
3. 添加自动备份脚本
4. 配置 cron 定时任务

**短期目标** (本月内):
1. 完善心跳调度器
2. 集成 Prometheus 监控
3. 配置告警通知

**memos-graph v3.0 功能完整，但保活机制需要加强才能达到生产标准！** ⚠️
