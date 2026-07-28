# memos-graph 故障排查手册

**版本**: 1.0  
**更新日期**: 2026-07-22  
**目标读者**: 运维工程师、开发人员

---

## 一、快速诊断流程

### 1.1 一键诊断

```bash
# 执行完整诊断
cd /home/gato/memos-graph
python3 diagnose.py --export

# 快速检查 (仅关键指标)
python3 diagnose.py --quick

# 仅检查服务状态
python3 diagnose.py --service

# 仅检查 PostgreSQL
python3 diagnose.py --postgres

# 仅分析日志
python3 diagnose.py --logs
```

### 1.2 故障排查流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    服务掉线报警                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ 第一步：检查进程 │
                    │ python3 diagnose.py --service │
                    └─────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ 进程在运行     │  │ 进程不存在    │  │ 进程不存在    │
    │ 但 systemd   │  │ 且无 PID     │  │ 但有 PID     │
    │ 显示 inactive│  │             │  │ (僵尸进程)  │
    └──────────────┘  └──────────────┘  └──────────────┘
            │                 │                 │
            │                 ▼                 ▼
            │         ┌──────────────┐  ┌──────────────┐
            │         │ 第二步：查日志 │  │ 第二步：杀进程 │
            │         │ tail -100    │  │ kill -9 PID  │
            │         │ *.log        │  │ 然后重启     │
            │         └──────────────┘  └──────────────┘
            │                 │
            ▼                 ▼
    ┌──────────────────────────────────┐
    │    第三步：查看错误关键字          │
    │    grep -E "ERROR|CRITICAL|FATAL" │
    └──────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ 数据库连接    │  │ 内存不足     │  │ API 调用失败  │
    │ 失败         │  │ (OOM)        │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ 查 PostgreSQL │  │ 增加内存限制  │  │ 检查 API Key │
    │ 状态         │  │ 或优化查询    │  │ 和网络       │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 二、故障分类与定位

### 2.1 故障类型判断矩阵

| 现象 | PostgreSQL 挂了 | memos-graph 挂了 | 网络问题 |
|------|---------------|-----------------|---------|
| **systemctl status postgresql** | ❌ inactive/failed | ✅ active | ✅ active |
| **systemctl status memos-graph** | ✅ active (但报错) | ❌ inactive/failed | ✅ active (但连不上 DB) |
| **ps aux \| grep postgres** | 无进程 | 有进程 | 有进程 |
| **ps aux \| grep memos** | 有进程 | 无进程 | 有进程 |
| **telnet 127.0.0.1 5432** | ❌ 不通 | ✅ 通 | ✅ 通 |
| **telnet 127.0.0.1 8765** | ✅ 通 | ❌ 不通 | ❌ 不通 (服务崩) |
| **日志关键字** | "connection refused" | "segfault", "panic" | "timeout", "connection reset" |
| **诊断命令** | `python3 diagnose.py --postgres` | `python3 diagnose.py --service` | `python3 diagnose.py --network` |

### 2.2 第一步：判断故障类型

```bash
# 1. 检查两个服务状态
systemctl status postgresql memos-graph

# 2. 检查进程
ps aux | grep -E 'postgres|memos' | grep -v grep

# 3. 检查端口
ss -tlnp | grep -E '5432|8765'

# 4. 快速诊断
python3 diagnose.py --quick
```

### 2.3 第二步：查看对应日志

#### PostgreSQL 日志位置

```bash
# Debian/Ubuntu
/var/log/postgresql/postgresql-*.log

# 通过 journalctl
journalctl -u postgresql --since "1 hour ago"

# 实时查看
tail -f /var/log/postgresql/postgresql-*.log
```

#### memos-graph 日志位置

```bash
# 应用日志
/home/gato/.memos-graph/logs/*.log

# 通过 journalctl
journalctl -u memos-graph --since "1 hour ago"

# 实时查看
tail -f /home/gato/.memos-graph/logs/memos-graph-*.log
```

#### 系统日志

```bash
# OOM Killer (内存不足导致进程被杀)
dmesg | grep -i "killed process"
journalctl -k --since "1 hour ago" | grep -i "oom"

# 系统错误
journalctl --priority=err --since "1 hour ago"
```

### 2.4 第三步：根据错误关键字定位

| 错误关键字 | 可能原因 | 解决方案 |
|-----------|---------|---------|
| `Connection refused` | PostgreSQL 未启动 | `systemctl start postgresql` |
| `authentication failed` | 密码错误或权限问题 | 检查 pg_hba.conf 和密码 |
| `too many clients` | 连接数超限 | 增加 max_connections 或优化连接池 |
| `Out of memory` / `OOM` | 内存不足 | 增加内存或优化查询 |
| `timeout` | 网络或查询超时 | 检查网络、优化慢查询 |
| `segmentation fault` | 程序崩溃 | 查看 core dump，更新版本 |
| `Address already in use` | 端口被占用 | `kill` 旧进程或改端口 |
| `Permission denied` | 文件权限问题 | `chown` 修正权限 |
| `No space left on device` | 磁盘满 | `df -h` 检查并清理 |

---

## 三、日志规范

### 3.1 日志级别定义

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| **DEBUG** | 详细调试信息，开发时使用 | API 请求参数、SQL 查询细节、向量计算过程 |
| **INFO** | 正常运营信息 | 服务启动/停止、API 请求成功、定时任务执行 |
| **WARNING** | 可恢复的异常 | 重试、降级、性能警告、慢查询 |
| **ERROR** | 需要关注的错误 | API 调用失败、数据库连接失败、向量生成失败 |
| **CRITICAL** | 严重故障 | 服务崩溃、数据损坏风险、无法恢复的错误 |

### 3.2 日志格式

```python
# 详细格式 (推荐)
%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s

# 示例输出
2026-07-22 20:30:45 [INFO] memos_graph.api - server.py:125 - handle_request() - API POST /api/v1/events - 201 (35.2ms)
2026-07-22 20:30:46 [ERROR] memos_graph.db - database.py:89 - execute() - DB INSERT events - FAIL (1205.3ms) - connection timeout
```

### 3.3 日志内容规范

#### 必须记录的信息

1. **API 请求日志** (INFO 级别)
   ```
   API {METHOD} {PATH} - {STATUS} ({DURATION}ms) - IP: {CLIENT_IP}
   ```

2. **数据库操作日志** (INFO/ERROR 级别)
   ```
   DB {OPERATION} {TABLE} - {OK|FAIL} ({DURATION}ms) - {ERROR_MESSAGE}
   ```

3. **健康检查日志** (INFO/WARNING 级别)
   ```
   Health check: {COMPONENT} - {STATUS} ({LATENCY}ms) - {DETAILS}
   ```

4. **错误日志** (ERROR/CRITICAL 级别)
   ```
   ERROR: {ERROR_TYPE} - {ERROR_MESSAGE} - File: {FILENAME}:{LINE} - Traceback: {STACK_TRACE}
   ```

#### 禁止记录的信息

- ❌ 用户密码、API Key 等敏感信息
- ❌ 完整的请求/响应体 (可能包含敏感数据)
- ❌ 数据库连接字符串 (含密码)
- ❌ 用户隐私数据 (邮箱、手机号等)

### 3.4 日志轮转策略

#### 应用层轮转 (logging.handlers.RotatingFileHandler)

```python
# 配置示例
RotatingFileHandler(
    filename='/var/log/memos-graph/memos-graph.log',
    maxBytes=50 * 1024 * 1024,  # 50MB
    backupCount=10,              # 保留 10 个文件
    encoding='utf-8'
)
# 总磁盘占用：50MB × 10 = 500MB
```

#### 系统层轮转 (logrotate)

```bash
# /etc/logrotate.d/memos-graph
/home/gato/.memos-graph/logs/*.log {
    daily           # 每天轮转
    rotate 10       # 保留 10 个文件
    compress        # 压缩旧日志
    size 50M        # 或按大小轮转 (50MB)
    missingok
    notifempty
    create 0640 gato gato
}
```

#### 防止日志爆盘的措施

1. **设置单文件上限**: 50MB
2. **限制文件数量**: 最多 10 个备份
3. **启用压缩**: 旧日志自动 gzip 压缩
4. **定期清理**: 删除超过 30 天的日志
5. **监控磁盘**: 设置磁盘使用率告警 (80%)

```bash
# 监控脚本
#!/bin/bash
LOG_DIR="/home/gato/.memos-graph/logs"
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ $DISK_USAGE -gt 80 ]; then
    echo "警告：磁盘使用率超过 80%"
    # 清理旧日志
    find $LOG_DIR -name "*.log.gz" -mtime +7 -delete
fi
```

---

## 四、诊断脚本使用指南

### 4.1 安装与配置

```bash
# 赋予执行权限
chmod +x /home/gato/memos-graph/diagnose.py

# 添加到 PATH (可选)
ln -s /home/gato/memos-graph/diagnose.py /usr/local/bin/memos-diagnose
```

### 4.2 命令选项

```bash
# 完整诊断 (默认)
python3 diagnose.py

# 快速检查 (仅关键指标)
python3 diagnose.py --quick

# 仅检查服务状态
python3 diagnose.py --service

# 仅检查 PostgreSQL
python3 diagnose.py --postgres

# 仅分析日志
python3 diagnose.py --logs

# 仅检查网络
python3 diagnose.py --network

# 导出诊断报告 (JSON + TXT)
python3 diagnose.py --export

# 组合使用
python3 diagnose.py --service --postgres --export
```

### 4.3 输出示例

```
memos-graph 诊断工具 v1.0
生成时间：2026-07-22T20:30:00.000000

============================================================
                      memos-graph 服务状态                      \n============================================================

  memos-graph 服务                      [OK] - active
  HTTP 健康检查 (http://127.0.0.1:8765/health) [OK] - Status 200
  memos-graph 端口 8765                  [OK] - 监听中

============================================================
                       PostgreSQL 状态                        \n============================================================

  PostgreSQL 服务                       [OK] - active
  PostgreSQL 端口 5432                  [OK] - 监听中
  数据库连接                               [OK]
  PostgreSQL 版本：PostgreSQL 15.3

============================================================
                            诊断总结                            \n============================================================

✓ 所有检查通过，系统运行正常

诊断报告已导出：/tmp/memos-graph-diagnose-20260722_203000.json
文本报告：/tmp/memos-graph-diagnose-20260722_203000.txt
```

---

## 五、常见故障处理

### 5.1 PostgreSQL 连接失败

**症状**: memos-graph 日志中出现 `connection refused` 或 `authentication failed`

**排查步骤**:

```bash
# 1. 检查 PostgreSQL 状态
systemctl status postgresql

# 2. 检查监听端口
ss -tlnp | grep 5432

# 3. 测试连接
psql -U postgres -c "SELECT version();"

# 4. 查看 PostgreSQL 日志
tail -100 /var/log/postgresql/postgresql-*.log

# 5. 检查 pg_hba.conf
cat /etc/postgresql/*/main/pg_hba.conf | grep -v "^#"
```

**解决方案**:

```bash
# 重启 PostgreSQL
sudo systemctl restart postgresql

# 如果是认证问题，修改 pg_hba.conf
# 将 local 连接改为 trust (仅测试环境)
# local   all   all   trust

# 重载配置
sudo systemctl reload postgresql
```

### 5.2 memos-graph 服务崩溃

**症状**: `systemctl status memos-graph` 显示 `failed` 或 `inactive`

**排查步骤**:

```bash
# 1. 查看服务状态
systemctl status memos-graph

# 2. 查看最近日志
journalctl -u memos-graph --since "1 hour ago" -n 50

# 3. 查看应用日志
tail -100 /home/gato/.memos-graph/logs/memos-graph-errors.log

# 4. 检查是否有僵尸进程
ps aux | grep memos | grep -v grep

# 5. 检查系统日志 (OOM)
dmesg | grep -i "killed process" | tail -10
```

**解决方案**:

```bash
# 清理僵尸进程
pkill -9 -f memos-graph

# 重启服务
systemctl restart memos-graph

# 如果是 OOM，增加内存限制
# 编辑 /etc/systemd/system/memos-graph.service
# MemoryMax=4G
systemctl daemon-reexec
systemctl restart memos-graph
```

### 5.3 服务响应慢

**症状**: API 请求超时，日志中出现大量 `timeout`

**排查步骤**:

```bash
# 1. 检查系统负载
uptime
top -bn1 | head -20

# 2. 检查慢查询
psql -U postgres -c "SELECT * FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 minutes';"

# 3. 检查连接数
psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# 4. 检查磁盘 IO
iostat -x 1 5

# 5. 检查内存使用
free -h
```

**解决方案**:

```bash
# 优化慢查询 (添加索引)
psql -U memos_graph -d memos_graph -c "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_events_created ON events(created_at);"

# 增加连接数限制
psql -U postgres -c "ALTER SYSTEM SET max_connections = 200;"
psql -U postgres -c "SELECT pg_reload_conf();"

# 清理旧数据
psql -U memos_graph -d memos_graph -c "DELETE FROM events WHERE created_at < NOW() - INTERVAL '90 days';"
```

### 5.4 日志文件过大

**症状**: `df -h` 显示磁盘使用率超过 80%

**排查步骤**:

```bash
# 1. 查找大文件
find /home/gato/.memos-graph/logs -type f -exec du -h {} + | sort -rh | head -10

# 2. 检查 logrotate 配置
cat /etc/logrotate.d/memos-graph

# 3. 手动轮转
sudo logrotate -f /etc/logrotate.d/memos-graph
```

**解决方案**:

```bash
# 清理旧日志
find /home/gato/.memos-graph/logs -name "*.log.gz" -mtime +30 -delete

# 压缩当前日志
gzip /home/gato/.memos-graph/logs/*.log.1

# 重启服务 (释放文件句柄)
systemctl restart memos-graph
```

---

## 六、预防性维护

### 6.1 日常检查清单

```bash
# 每日检查 (建议加入 cron)
# 1. 服务状态
systemctl is-active postgresql memos-graph

# 2. 磁盘使用
df -h / | tail -1 | awk '{print $5}'

# 3. 日志错误数
grep -c "ERROR\|CRITICAL" /home/gato/.memos-graph/logs/memos-graph-*.log

# 4. 活跃连接数
psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

### 6.2 监控告警配置

```bash
# 创建监控脚本 /home/gato/memos-graph/monitor.sh
#!/bin/bash

# 检查服务
if ! systemctl is-active --quiet memos-graph; then
    echo "ALERT: memos-graph service is down!"
    # 发送邮件/短信/Slack 通知
fi

# 检查磁盘
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "ALERT: Disk usage is at ${DISK_USAGE}%"
fi

# 检查内存
MEM_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2*100.0)}')
if [ $MEM_USAGE -gt 90 ]; then
    echo "ALERT: Memory usage is at ${MEM_USAGE}%"
fi
```

### 6.3 自动恢复配置

```bash
# systemd 已配置自动重启
# Restart=always
# RestartSec=5

# 如果需要更复杂的恢复逻辑，使用 watchdog
# 编辑 /etc/systemd/system/memos-graph.service
# WatchdogSec=30
# NotifyAccess=all
```

---

## 七、附录

### A. 相关文件路径

| 文件类型 | 路径 |
|---------|------|
| 应用日志 | `/home/gato/.memos-graph/logs/*.log` |
| PostgreSQL 日志 | `/var/log/postgresql/postgresql-*.log` |
| systemd 服务 | `/etc/systemd/system/memos-graph.service` |
| logrotate 配置 | `/etc/logrotate.d/memos-graph` |
| 诊断脚本 | `/home/gato/memos-graph/diagnose.py` |
| 日志配置 | `/home/gato/memos-graph/logging_config.py` |

### B. 常用命令速查

```bash
# 服务管理
systemctl start|stop|restart|status memos-graph
systemctl start|stop|restart|status postgresql

# 日志查看
journalctl -u memos-graph -f          # 实时查看
journalctl -u memos-graph --since "1 hour ago"  # 最近 1 小时
tail -f /home/gato/.memos-graph/logs/*.log  # 应用日志

# 诊断工具
python3 diagnose.py --quick           # 快速检查
python3 diagnose.py --export          # 导出报告

# 性能检查
top -p $(pgrep -f memos-graph)        # 进程资源
psql -c "SELECT * FROM pg_stat_activity;"  # 数据库连接
```

### C. 紧急联系人

- **运维负责人**: [填写]
- **开发负责人**: [填写]
- **升级流程**: [填写]

---

**文档维护**: 每次故障处理后，更新此文档的"常见故障处理"章节。
