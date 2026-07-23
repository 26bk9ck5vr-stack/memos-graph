# memos-graph 运维手册

**版本**: v1.0  
**更新日期**: 2026-07-23  
**适用环境**: Linux (systemd)

---

## 📊 系统架构

```
memos-graph = PostgreSQL (数据库) + Uvicorn (应用服务)

稳定性保障:
├── systemd (进程守护)
├── cron (健康检查)
├── logrotate (日志轮转)
└── 代码层 (重试 + 熔断 + 背压)
```

---

## 🚀 常用命令

### 服务管理

```bash
# 查看服务状态
sudo systemctl status memos-graph

# 启动服务
sudo systemctl start memos-graph

# 重启服务
sudo systemctl restart memos-graph

# 停止服务
sudo systemctl stop memos-graph

# 查看实时日志
sudo journalctl -u memos-graph -f

# 查看最近 100 行日志
sudo journalctl -u memos-graph -n 100 --no-pager
```

### 健康检查

```bash
# 手动执行健康检查
bash /home/gato/memos-graph/scripts/health-check.sh

# 查看健康检查日志
tail -f /var/log/memos-graph/health-check.log

# 查看告警日志
tail -f /var/log/memos-graph/alerts.log

# HTTP 健康检查
curl http://127.0.0.1:8765/api/v1/health
```

### 日志管理

```bash
# 查看应用日志 (systemd journal)
sudo journalctl -u memos-graph -f

# 查看健康检查日志
tail -f /var/log/memos-graph/health-check.log

# 查看告警日志
tail -f /var/log/memos-graph/alerts.log

# 手动触发日志轮转
sudo logrotate -f /etc/logrotate.d/memos-graph

# 清理旧日志 (保留最近 7 天)
find /var/log/memos-graph -name "*.log.*" -mtime +7 -delete
```

---

## 🔍 故障排查流程

### 第一步：检查服务状态

```bash
sudo systemctl status memos-graph
```

**可能状态**:
- `active (running)` - 服务正常
- `activating (auto-restart)` - 正在自动重启
- `failed` - 服务失败，需要检查日志

### 第二步：查看日志

```bash
# 查看最近错误
sudo journalctl -u memos-graph -n 50 --no-pager | grep ERROR

# 查看完整日志
sudo journalctl -u memos-graph -f
```

**常见错误**:
1. **ImportError** - Python 模块导入失败 → 检查代码
2. **Connection refused** - PostgreSQL 连接失败 → 检查数据库
3. **MemoryError** - 内存不足 → 检查资源限制
4. **Timeout** - API 超时 → 检查网络或 Embedding 服务

### 第三步：检查依赖

```bash
# 检查 PostgreSQL
sudo systemctl status postgresql
pg_isready -h localhost -p 5432

# 检查网络
curl -v http://127.0.0.1:8765/api/v1/health

# 检查磁盘空间
df -h /home

# 检查内存使用
free -h
ps aux | grep memos-graph
```

### 第四步：诊断脚本

```bash
# 运行一键诊断
bash /home/gato/memos-graph/scripts/diagnose.sh

# 诊断包位置
ls -la /tmp/memos-graph-diagnose-*.tar.gz
```

---

## ⚙️ 配置说明

### systemd 配置

**文件位置**: `/etc/systemd/system/memos-graph.service`

**关键配置**:
```ini
[Service]
Restart=always           # 总是自动重启
RestartSec=5             # 重启间隔 5 秒
MemoryMax=2G             # 最大内存 2GB
MemoryHigh=1536M         # 内存警告阈值 1.5GB
```

**修改后需要**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart memos-graph
```

### cron 配置

**文件位置**: `/home/gato/memos-graph/scripts/memos-graph.crontab`

**检查频率**: 每分钟一次

**修改 cron**:
```bash
crontab -e
# 或重新安装
crontab /home/gato/memos-graph/scripts/memos-graph.crontab
```

### 日志轮转

**文件位置**: `/etc/logrotate.d/memos-graph`

**配置**:
- 每日轮转
- 保留 7 天
- 单文件最大 10MB
- 自动压缩

---

## 🛡️ 稳定性机制

### 1. 进程守护 (systemd)

- **自动重启**: 服务崩溃后 5 秒内自动重启
- **资源限制**: 内存限制 2GB，防止 OOM
- **开机自启**: 系统重启后自动启动

### 2. 健康检查 (cron)

- **频率**: 每分钟一次
- **检查项**:
  - systemd 服务状态
  - HTTP 健康端点 (200 OK)
  - PostgreSQL 连接
  - 磁盘空间 (>500MB)
- **自动恢复**: 发现异常自动重启服务

### 3. 自动恢复 (auto-recover.sh)

- **冷却机制**: 5 分钟内最多重启 3 次
- **验证**: 重启后等待 10 秒验证服务是否正常
- **日志**: 所有恢复操作记录到日志

### 4. 代码层保护

- **重试机制**: Embedding API 失败重试 3 次 (指数退避)
- **熔断器**: 5 次失败后熔断 60 秒
- **背压控制**: 最多 5 个并发向量生成任务
- **优雅降级**: API 失败时返回零向量

---

## 📈 监控指标

### 关键指标

| 指标 | 正常值 | 告警阈值 | 检查方法 |
|------|--------|----------|----------|
| **服务状态** | active | failed | `systemctl status` |
| **HTTP 响应** | 200 | 非 200 | `curl /health` |
| **内存使用** | <1GB | >1.5GB | `ps aux` |
| **磁盘空间** | >1GB | <500MB | `df -h` |
| **响应时间** | <500ms | >2s | `curl -w` |

### 日志分析

```bash
# 统计错误数量
grep "ERROR" /var/log/memos-graph/*.log | wc -l

# 查看最近告警
tail -20 /var/log/memos-graph/alerts.log

# 查找特定错误
grep "Embedding API" /var/log/memos-graph/*.log
```

---

## 🔧 常见问题

### Q1: 服务无法启动

**症状**: `systemctl status memos-graph` 显示 `failed`

**解决**:
```bash
# 1. 查看错误日志
sudo journalctl -u memos-graph -n 50 --no-pager

# 2. 检查配置文件
python3 -c "import memos_graph.server"

# 3. 手动启动测试
cd /home/gato/memos-graph
.venv/bin/uvicorn memos_graph.server:create_app --factory

# 4. 重启服务
sudo systemctl restart memos-graph
```

### Q2: 健康检查失败

**症状**: `curl /health` 返回非 200

**解决**:
```bash
# 1. 检查服务状态
sudo systemctl status memos-graph

# 2. 检查 PostgreSQL
sudo systemctl status postgresql
pg_isready -h localhost

# 3. 查看应用日志
sudo journalctl -u memos-graph -f
```

### Q3: 内存使用过高

**症状**: `ps aux` 显示内存 >1.5GB

**解决**:
```bash
# 1. 重启服务 (释放内存)
sudo systemctl restart memos-graph

# 2. 检查背压配置
# 确认 _embedding_semaphore = asyncio.Semaphore(5)

# 3. 调整 systemd 内存限制
sudo systemctl edit memos-graph
# 添加：MemoryMax=4G

# 4. 长期方案：优化代码，减少内存泄漏
```

### Q4: 日志爆盘

**症状**: `/var/log/memos-graph/` 占用 >10GB

**解决**:
```bash
# 1. 清理旧日志
sudo find /var/log/memos-graph -name "*.log.*" -mtime +7 -delete

# 2. 检查 logrotate 配置
cat /etc/logrotate.d/memos-graph

# 3. 手动触发轮转
sudo logrotate -f /etc/logrotate.d/memos-graph
```

---

## 📞 紧急联系

### 升级流程

1. **自动恢复失败** → 检查日志，手动重启
2. **手动重启失败** → 检查依赖 (PostgreSQL, 网络)
3. **依赖正常** → 联系开发者，提供诊断包

### 诊断包收集

```bash
# 运行诊断脚本
bash /home/gato/memos-graph/scripts/diagnose.sh

# 诊断包位置
ls -la /tmp/memos-graph-diagnose-*.tar.gz

# 发送给开发者
# (通过邮件/即时通讯工具发送文件)
```

---

## 📝 变更记录

| 日期 | 变更 | 负责人 |
|------|------|--------|
| 2026-07-23 | 初始版本 | memos-graph team |
| 2026-07-23 | 添加稳定性加固 | memos-graph team |

---

**文档结束**
