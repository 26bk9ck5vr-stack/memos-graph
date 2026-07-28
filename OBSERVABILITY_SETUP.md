# memos-graph 可观测性方案安装指南

**版本**: 1.0  
**更新日期**: 2026-07-22

---

## 一、方案概述

本方案为 memos-graph 提供完整的可观测性支持，包括：

1. **日志系统**: 结构化日志 + 自动轮转，防止爆盘
2. **诊断工具**: 一键收集系统、PostgreSQL、应用状态
3. **健康检查**: HTTP 端点 + 脚本，支持监控系统集成
4. **故障排查**: 详细手册 + 流程图，快速定位问题
5. **监控告警**: 定时检查 + 自动恢复

---

## 二、文件清单

| 文件 | 用途 | 安装位置 |
|------|------|---------|
| `logging_config.py` | Python 日志配置模块 | `/home/gato/memos-graph/` |
| `logging.conf` | INI 格式日志配置 | `/home/gato/memos-graph/` |
| `logrotate.conf` | 日志轮转配置 | `/etc/logrotate.d/` |
| `diagnose.py` | 诊断脚本 | `/home/gato/memos-graph/` |
| `health_check.py` | 健康检查脚本 | `/home/gato/memos-graph/` |
| `monitor.sh` | 监控脚本 (cron) | `/home/gato/memos-graph/` |
| `TROUBLESHOOTING.md` | 故障排查手册 | `/home/gato/memos-graph/` |
| `memos-graph.service` | systemd 服务配置 | `/etc/systemd/system/` |

---

## 三、安装步骤

### 3.1 日志配置

#### 方式 A: Python 应用内配置 (推荐)

在 memos-graph 应用入口文件 (如 `main.py` 或 `server.py`) 中添加：

```python
from logging_config import setup_logging

# 启动时初始化日志
logger = setup_logging(
    level='INFO',
    log_format='detailed',
    enable_console=True,
    max_bytes=50 * 1024 * 1024,  # 50MB
    backup_count=10
)
```

#### 方式 B: 使用 logging.conf

```python
import logging.config
logging.config.fileConfig('/home/gato/memos-graph/logging.conf')
```

### 3.2 安装 systemd 服务

```bash
# 复制服务文件
sudo cp /home/gato/memos-graph/systemd/memos-graph.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable memos-graph

# 启动服务
sudo systemctl start memos-graph

# 查看状态
sudo systemctl status memos-graph
```

### 3.3 安装日志轮转

```bash
# 复制 logrotate 配置
sudo cp /home/gato/memos-graph/logrotate.conf /etc/logrotate.d/memos-graph

# 测试配置 (dry-run)
sudo logrotate -d /etc/logrotate.d/memos-graph

# 强制轮转测试
sudo logrotate -f /etc/logrotate.d/memos-graph

# 查看轮转状态
cat /var/lib/logrotate/status | grep memos-graph
```

### 3.4 创建日志目录

```bash
# 创建日志目录
mkdir -p /home/gato/.memos-graph/logs
chmod 750 /home/gato/.memos-graph/logs
chown gato:gato /home/gato/.memos-graph/logs
```

### 3.5 配置监控 (可选)

#### 添加 cron 任务

```bash
# 编辑 crontab
crontab -e

# 添加以下行 (每 5 分钟检查一次)
*/5 * * * * /home/gato/memos-graph/monitor.sh >> /home/gato/.memos-graph/logs/monitor.log 2>&1
```

#### 配置告警 (可选)

编辑 `/home/gato/memos-graph/monitor.sh`:

```bash
# 设置告警邮箱
ALERT_EMAIL="admin@example.com"

# 设置 Slack webhook
SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

---

## 四、使用方法

### 4.1 诊断工具

```bash
# 完整诊断
python3 /home/gato/memos-graph/diagnose.py

# 快速检查
python3 /home/gato/memos-graph/diagnose.py --quick

# 仅检查服务
python3 /home/gato/memos-graph/diagnose.py --service

# 仅检查 PostgreSQL
python3 /home/gato/memos-graph/diagnose.py --postgres

# 仅分析日志
python3 /home/gato/memos-graph/diagnose.py --logs

# 导出报告
python3 /home/gato/memos-graph/diagnose.py --export
```

### 4.2 健康检查

```bash
# 快速检查
python3 /home/gato/memos-graph/health_check.py --quick

# JSON 输出 (用于监控系统)
python3 /home/gato/memos-graph/health_check.py --json

# 完整检查
python3 /home/gato/memos-graph/health_check.py
```

### 4.3 查看日志

```bash
# 实时查看应用日志
tail -f /home/gato/.memos-graph/logs/memos-graph-*.log

# 查看错误日志
tail -f /home/gato/.memos-graph/logs/memos-graph-errors-*.log

# 查看 systemd 日志
journalctl -u memos-graph -f

# 查看最近 1 小时日志
journalctl -u memos-graph --since "1 hour ago"

# 搜索错误
grep -i "ERROR\|CRITICAL" /home/gato/.memos-graph/logs/*.log
```

### 4.4 日志轮转管理

```bash
# 手动轮转日志
sudo logrotate -f /etc/logrotate.d/memos-graph

# 查看轮转后的文件
ls -lh /home/gato/.memos-graph/logs/

# 清理旧日志 (超过 30 天)
find /home/gato/.memos-graph/logs -name "*.log.gz" -mtime +30 -delete
```

---

## 五、故障排查流程

### 5.1 服务掉线时

```
第一步：运行诊断
  python3 diagnose.py --quick

第二步：查看状态
  systemctl status memos-graph postgresql

第三步：查看日志
  tail -100 /home/gato/.memos-graph/logs/memos-graph-errors-*.log
  journalctl -u memos-graph --since "1 hour ago"

第四步：根据错误关键字定位
  - "Connection refused" → PostgreSQL 问题
  - "Out of memory" → 内存不足
  - "timeout" → 网络或查询超时
  - "segmentation fault" → 程序崩溃

第五步：参考 TROUBLESHOOTING.md 详细手册
```

### 5.2 区分故障类型

| 检查项 | PostgreSQL 挂了 | memos-graph 挂了 | 网络问题 |
|--------|---------------|-----------------|---------|
| `systemctl status postgresql` | ❌ failed | ✅ active | ✅ active |
| `systemctl status memos-graph` | ✅ active (报错) | ❌ failed | ✅ active |
| `telnet 127.0.0.1 5432` | ❌ 不通 | ✅ 通 | ✅ 通 |
| `telnet 127.0.0.1 8765` | ✅ 通 | ❌ 不通 | ❌ 不通 |
| 诊断命令 | `diagnose.py --postgres` | `diagnose.py --service` | `diagnose.py --network` |

---

## 六、日志规范

### 6.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 调试信息 (开发用) | SQL 查询细节、向量计算过程 |
| INFO | 正常运营 | 服务启动、API 请求成功 |
| WARNING | 可恢复异常 | 重试、降级、性能警告 |
| ERROR | 需要关注的错误 | API 失败、数据库连接失败 |
| CRITICAL | 严重故障 | 服务崩溃、数据损坏风险 |

### 6.2 日志格式

```
2026-07-22 20:30:45 [INFO] memos_graph.api - server.py:125 - handle_request() - API POST /api/v1/events - 201 (35.2ms)
2026-07-22 20:30:46 [ERROR] memos_graph.db - database.py:89 - execute() - DB INSERT events - FAIL (1205.3ms) - connection timeout
```

### 6.3 防止日志爆盘

- **单文件上限**: 50MB
- **文件数量**: 最多 10 个备份
- **自动压缩**: 旧日志 gzip 压缩
- **定期清理**: 删除超过 30 天的日志
- **磁盘告警**: 使用率超过 80% 告警

---

## 七、监控集成

### 7.1 Prometheus (可选)

如果需要集成 Prometheus，添加 metrics 端点：

```python
from prometheus_client import start_http_server, Counter, Histogram

# 定义指标
REQUEST_COUNT = Counter('memos_graph_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('memos_graph_request_duration_seconds', 'Request duration')

# 启动 metrics 服务器
start_http_server(8000)  # metrics 端口
```

### 7.2 Grafana 仪表盘 (可选)

导入系统监控仪表盘：
- Node Exporter (系统指标)
- PostgreSQL Exporter (数据库指标)
- 自定义日志面板

### 7.3 告警规则 (可选)

```yaml
# Prometheus alerting rules
groups:
- name: memos-graph
  rules:
  - alert: MemosGraphDown
    expr: up{job="memos-graph"} == 0
    for: 5m
    annotations:
      summary: "memos-graph service is down"
  
  - alert: PostgreSQLDown
    expr: up{job="postgresql"} == 0
    for: 5m
    annotations:
      summary: "PostgreSQL service is down"
  
  - alert: HighErrorRate
    expr: rate(memos_graph_requests_total{status=~"5.."}[5m]) > 0.1
    for: 10m
    annotations:
      summary: "High error rate detected"
```

---

## 八、验证安装

### 8.1 检查清单

```bash
# 1. 日志目录存在
ls -la /home/gato/.memos-graph/logs/

# 2. 日志文件生成
ls -la /home/gato/.memos-graph/logs/*.log

# 3. systemd 服务运行
systemctl status memos-graph

# 4. 诊断工具可用
python3 diagnose.py --quick

# 5. 健康检查可用
python3 health_check.py --quick

# 6. logrotate 配置
sudo logrotate -d /etc/logrotate.d/memos-graph
```

### 8.2 测试故障恢复

```bash
# 1. 手动停止服务
sudo systemctl stop memos-graph

# 2. 等待自动重启 (5 秒)
sleep 10

# 3. 检查状态
systemctl status memos-graph

# 4. 查看日志确认重启
journalctl -u memos-graph --since "2 minutes ago"
```

---

## 九、常见问题

### Q1: 日志文件不生成？

**A**: 检查日志目录权限：
```bash
mkdir -p /home/gato/.memos-graph/logs
chmod 750 /home/gato/.memos-graph/logs
chown gato:gato /home/gato/.memos-graph/logs
```

### Q2: logrotate 不工作？

**A**: 手动测试配置：
```bash
sudo logrotate -d /etc/logrotate.d/memos-graph
sudo logrotate -f /etc/logrotate.d/memos-graph
```

### Q3: 诊断脚本权限错误？

**A**: 赋予执行权限：
```bash
chmod +x /home/gato/memos-graph/diagnose.py
chmod +x /home/gato/memos-graph/health_check.py
chmod +x /home/gato/memos-graph/monitor.sh
```

### Q4: systemd 服务启动失败？

**A**: 查看详细错误：
```bash
journalctl -u memos-graph -n 50 --no-pager
```

---

## 十、后续优化

1. **添加 metrics 端点**: 集成 Prometheus
2. **配置分布式追踪**: Jaeger/Zipkin
3. **集成 APM**: DataDog/New Relic
4. **添加审计日志**: 记录用户操作
5. **配置日志聚合**: ELK/Loki

---

**文档维护**: 每次更新日志配置或诊断工具后，更新此文档。
