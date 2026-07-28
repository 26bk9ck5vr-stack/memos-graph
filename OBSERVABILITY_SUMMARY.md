# memos-graph 可观测性方案总结

## 📋 方案概述

本方案为 memos-graph 构建了完整的**稳定性环路**，解决用户痛点：**"服务莫名掉线，不知何时，无法调试"**。

### 核心能力

| 能力 | 实现方式 | 解决问题 |
|------|---------|---------|
| **快速定位** | 一键诊断脚本 | 30 秒内确定故障类型 |
| **故障区分** | 分类矩阵 + 关键字匹配 | 区分 PostgreSQL/memos-graph/网络问题 |
| **日志规范** | 分级记录 + 自动轮转 | 防止爆盘，便于排查 |
| **自动恢复** | systemd + 监控脚本 | 服务掉线自动重启 |
| **健康检查** | HTTP 端点 + 脚本 | 支持监控系统集成 |

---

## 📁 交付文件

### 1. 日志配置 (2 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `logging_config.py` | 6.3KB | Python 日志配置模块，支持轮转、分级 |
| `logging.conf` | 2.0KB | INI 格式日志配置，兼容标准 logging |

**关键特性**:
- 单文件最大 50MB，保留 10 个备份 (最多 500MB)
- 自动压缩旧日志 (gzip)
- 错误日志单独文件，便于快速定位
- 支持 DEBUG/INFO/WARNING/ERROR/CRITICAL 五级

### 2. 诊断工具 (1 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `diagnose.py` | 17KB | 一键诊断脚本，收集系统/PostgreSQL/应用状态 |

**支持选项**:
```bash
python3 diagnose.py --quick      # 快速检查 (30 秒)
python3 diagnose.py --service    # 仅服务状态
python3 diagnose.py --postgres   # 仅 PostgreSQL
python3 diagnose.py --logs       # 仅日志分析
python3 diagnose.py --export     # 导出 JSON+TXT 报告
```

**输出示例**:
```
✓ PostgreSQL 服务 - OK
✓ memos-graph 进程 - OK (PID: 12345)
✗ HTTP 健康检查 - FAIL (Connection refused)
⚠ 发现 1 个问题: memos-graph HTTP 健康检查失败
```

### 3. 健康检查 (2 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `health_check.py` | 6.1KB | 健康检查脚本，支持 JSON 输出 |
| `monitor.sh` | 5.5KB | 监控脚本，支持 cron 定时任务 |

**集成方式**:
```bash
# Prometheus/Grafana
python3 health_check.py --json | jq '.healthy'

# Cron 定时检查 (每 5 分钟)
*/5 * * * * /home/gato/memos-graph/monitor.sh
```

### 4. 日志轮转 (1 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `logrotate.conf` | 1.4KB | logrotate 配置，系统级日志管理 |

**安装**:
```bash
sudo cp logrotate.conf /etc/logrotate.d/memos-graph
sudo logrotate -f /etc/logrotate.d/memos-graph  # 测试
```

### 5. 文档 (3 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `TROUBLESHOOTING.md` | 18KB | 故障排查手册，详细步骤 + 命令 |
| `OBSERVABILITY_SETUP.md` | 9.3KB | 安装指南，包含所有配置步骤 |
| `TROUBLESHOOTING_FLOWCHART.txt` | 32KB | ASCII 流程图海报，可打印张贴 |

### 6. systemd 服务 (1 个文件)

| 文件 | 大小 | 用途 |
|------|------|------|
| `systemd/memos-graph.service` | 1.4KB | 增强的 systemd 服务配置 |

**增强特性**:
- 自动重启 (Restart=always)
- 资源限制 (MemoryMax=2G)
- 安全增强 (NoNewPrivileges, ProtectSystem)
- 日志输出到 journal

---

## 🔧 故障排查流程

### 标准流程 (5 步)

```
1. 运行诊断
   $ python3 diagnose.py --quick
   
2. 查看状态
   $ systemctl status memos-graph postgresql
   
3. 查看日志
   $ tail -100 /home/gato/.memos-graph/logs/memos-graph-errors-*.log
   
4. 根据关键字定位
   - "Connection refused" → PostgreSQL 问题
   - "Out of memory" → 内存不足
   - "timeout" → 网络或查询超时
   
5. 执行恢复
   $ systemctl restart memos-graph
```

### 故障分类矩阵

| 现象 | PostgreSQL 挂了 | memos-graph 挂了 | 网络问题 |
|------|---------------|-----------------|---------|
| systemctl status postgresql | ❌ inactive | ✅ active | ✅ active |
| systemctl status memos-graph | ✅ active (报错) | ❌ inactive | ✅ active |
| telnet 127.0.0.1 5432 | ❌ 不通 | ✅ 通 | ✅ 通 |
| telnet 127.0.0.1 8765 | ✅ 通 | ❌ 不通 | ❌ 不通 |
| 诊断命令 | `--postgres` | `--service` | `--network` |

---

## 📊 日志规范

### 日志级别定义

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| DEBUG | 详细调试 (开发用) | SQL 查询细节、向量计算过程 |
| INFO | 正常运营 | 服务启动、API 请求成功 |
| WARNING | 可恢复异常 | 重试、降级、性能警告 |
| ERROR | 需关注错误 | API 失败、数据库连接失败 |
| CRITICAL | 严重故障 | 服务崩溃、数据损坏风险 |

### 日志格式

```
2026-07-22 20:30:45 [INFO] memos_graph.api - server.py:125 - API POST /api/v1/events - 201 (35.2ms)
2026-07-22 20:30:46 [ERROR] memos_graph.db - database.py:89 - DB INSERT events - FAIL (1205.3ms)
```

### 防止爆盘措施

1. **单文件上限**: 50MB
2. **文件数量**: 最多 10 个备份
3. **自动压缩**: 旧日志 gzip
4. **定期清理**: 删除超过 30 天的日志
5. **磁盘告警**: 使用率超过 80% 告警

---

## 🚀 快速开始

### 1. 安装日志配置

```bash
cd /home/gato/memos-graph

# 在应用入口添加
python3 -c "from logging_config import setup_logging; setup_logging()"
```

### 2. 创建日志目录

```bash
mkdir -p /home/gato/.memos-graph/logs
chmod 750 /home/gato/.memos-graph/logs
```

### 3. 安装 systemd 服务

```bash
sudo cp systemd/memos-graph.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable memos-graph
sudo systemctl start memos-graph
```

### 4. 安装日志轮转

```bash
sudo cp logrotate.conf /etc/logrotate.d/memos-graph
sudo logrotate -f /etc/logrotate.d/memos-graph
```

### 5. 配置监控 (可选)

```bash
# 添加 cron 任务
crontab -e
# */5 * * * * /home/gato/memos-graph/monitor.sh
```

---

## ✅ 验证清单

```bash
# 1. 日志目录存在
ls -la /home/gato/.memos-graph/logs/

# 2. 诊断工具可用
python3 diagnose.py --quick

# 3. 健康检查可用
python3 health_check.py --quick

# 4. systemd 服务运行
systemctl status memos-graph

# 5. logrotate 配置
sudo logrotate -d /etc/logrotate.d/memos-graph
```

---

## 📈 预期效果

| 指标 | 改善前 | 改善后 |
|------|--------|--------|
| 故障定位时间 | 未知 | <5 分钟 |
| 日志磁盘占用 | 无限制 | <500MB |
| 服务恢复时间 | 人工干预 | 自动 (5 秒) |
| 监控覆盖率 | 0% | 100% |
| 文档完整性 | 无 | 完整手册 |

---

## 🔗 相关文件

- **故障排查手册**: `TROUBLESHOOTING.md`
- **安装指南**: `OBSERVABILITY_SETUP.md`
- **流程图海报**: `TROUBLESHOOTING_FLOWCHART.txt`
- **日志配置**: `logging_config.py`
- **诊断脚本**: `diagnose.py`
- **健康检查**: `health_check.py`
- **监控脚本**: `monitor.sh`

---

## 📞 支持

遇到问题时:
1. 首先运行 `python3 diagnose.py --export` 导出诊断报告
2. 查看 `/tmp/memos-graph-diagnose-*.txt` 报告
3. 参考 `TROUBLESHOOTING.md` 对应章节
4. 检查日志 `/home/gato/.memos-graph/logs/*.log`

---

**方案版本**: 1.0  
**创建日期**: 2026-07-22  
**适用版本**: memos-graph v0.9.0+
