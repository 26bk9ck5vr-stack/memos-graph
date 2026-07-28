# memos-graph v3.0 全自动保活系统部署指南

**目标**: 零人工介入的全自动保活机制

---

## 🚀 快速部署 (推荐)

### 一键安装

```bash
# 克隆项目 (如果还没有)
git clone https://github.com/26bk9ck5vr-stack/memos-graph.git
cd memos-graph

# 运行一键安装脚本 (需要 sudo)
sudo ./deploy/install-keepalive.sh
```

安装脚本会自动:
- ✅ 创建必要的目录 (日志、备份)
- ✅ 设置文件权限
- ✅ 安装 systemd 服务
- ✅ 启用开机自启
- ✅ 启动服务
- ✅ 验证运行状态

---

## 📋 手动部署 (高级)

### 1. 创建目录

```bash
# 创建备份目录
sudo mkdir -p /backup/memos-graph
sudo chown $(whoami):$(whoami) /backup/memos-graph

# 创建日志目录
mkdir -p logs
```

### 2. 设置权限

```bash
chmod +x bin/keepalive.sh
```

### 3. 安装 systemd 服务

```bash
sudo cp deploy/memos-graph.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable memos-graph
```

### 4. 启动服务

```bash
sudo systemctl start memos-graph
```

### 5. 验证状态

```bash
# 检查服务状态
sudo systemctl status memos-graph

# 查看日志
sudo journalctl -u memos-graph -f

# 测试健康检查
curl http://localhost:8765/api/v1/health/ready
```

---

## 🛠️ 使用指南

### 查看状态

```bash
./bin/keepalive.sh status
```

输出示例:
```
✅ memos-graph 运行中 (PID: 12345)
✅ 健康检查通过
```

### 手动备份

```bash
./bin/keepalive.sh backup
```

输出示例:
```
[2026-07-30 23:45:00] 开始备份数据库...
[2026-07-30 23:45:02] ✅ 数据库备份成功：/backup/memos-graph/db_20260730_234500.sql.gz
[2026-07-30 23:45:02] 已清理 7 天前的旧备份
```

### 重启服务

```bash
./bin/keepalive.sh restart
```

### 停止服务

```bash
sudo systemctl stop memos-graph
```

### 查看日志

```bash
# systemd 日志
sudo journalctl -u memos-graph -f

# 保活日志
tail -f logs/keepalive.log

# 服务器日志
tail -f logs/server.log
```

---

## ⚙️ 配置告警 (可选)

### 1. 获取 Webhook URL

**钉钉机器人**:
1. 钉钉群 → 群设置 → 智能群助手 → 添加机器人
2. 选择"自定义"
3. 复制 Webhook 地址

**企业微信机器人**:
1. 企业微信群 → 群设置 → 添加群机器人
2. 复制 Webhook 地址

### 2. 配置 systemd 服务

```bash
sudo nano /etc/systemd/system/memos-graph.service
```

添加环境变量:
```ini
[Service]
Environment="MEMOS_ALERT_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx"
Environment="MEMOS_ALERT_ENABLED=true"
```

### 3. 重启服务

```bash
sudo systemctl daemon-reload
sudo systemctl restart memos-graph
```

### 4. 测试告警

```bash
# 手动触发告警
./bin/keepalive.sh status
```

---

## 📊 保活机制详解

### 1. 进程守护

- **检测频率**: 每 60 秒
- **重启策略**: 崩溃后立即重启
- **频率限制**: 5 分钟内最多重启 5 次 (防止无限重启循环)
- **等待时间**: 重启后等待 3 秒验证启动成功

### 2. 健康检查

- **检测频率**: 每 60 秒
- **检查项**: HTTP 端点 `/api/v1/health/ready`
- **重试次数**: 3 次 (每次间隔 2 秒)
- **失败处理**: 触发自动重启

### 3. 数据库监控

- **检测频率**: 每 5 分钟
- **检查项**: 
  - PostgreSQL 是否运行
  - 连接数是否超过阈值 (默认 8)
- **告警**: 连接数过高时发送告警

### 4. 资源监控

- **检测频率**: 每 5 分钟
- **监控项**:
  - CPU 使用率 (阈值：90%)
  - 内存使用率 (阈值：90%)
  - 磁盘使用率 (阈值：85%)
- **告警**: 超过阈值时发送告警

### 5. 自动备份

- **执行时间**: 每天 03:00
- **备份内容**: PostgreSQL 数据库 (pg_dump)
- **备份格式**: gzip 压缩
- **保留策略**: 最近 7 天
- **失败处理**: 记录日志 + 发送告警

### 6. 日志轮转

- **执行时间**: 每周日 04:00
- **触发条件**: 日志文件 > 10MB
- **保留策略**: 最近 30 天
- **轮转方式**: 重命名为 .log.1, .log.2 等

---

## 🔍 故障排查

### 服务无法启动

```bash
# 查看详细日志
sudo journalctl -u memos-graph -n 50

# 检查端口占用
sudo lsof -i :8765

# 手动测试启动
./bin/keepalive.sh start
```

### 健康检查失败

```bash
# 手动测试健康检查
curl -v http://localhost:8765/api/v1/health/ready

# 检查数据库连接
pg_isready -d memos_graph

# 检查 API 配置
cat ~/.config/memos-graph/config.yaml
```

### 备份失败

```bash
# 检查 PostgreSQL 是否运行
sudo systemctl status postgresql

# 手动测试备份
pg_dump memos_graph | gzip > /tmp/test.sql.gz

# 检查磁盘空间
df -h /backup
```

### 告警未发送

```bash
# 检查环境变量
sudo systemctl show memos-graph | grep MEMOS_

# 测试 webhook
curl -X POST "你的 webhook 地址" \
  -H "Content-Type: application/json" \
  -d '{"msgtype":"text","text":{"content":"测试"}}'

# 查看保活日志
tail -f logs/keepalive.log | grep ALERT
```

---

## 📈 监控指标

### 关键指标

| 指标 | 正常值 | 告警阈值 | 检查频率 |
|------|--------|---------|---------|
| 进程状态 | Running | Stopped | 60s |
| 健康检查 | 200 OK | != 200 | 60s |
| CPU 使用率 | < 80% | > 90% | 300s |
| 内存使用率 | < 80% | > 90% | 300s |
| 磁盘使用率 | < 80% | > 85% | 300s |
| 数据库连接 | < 5 | > 8 | 300s |
| 重启次数 | 0 | > 5/5min | 持续 |

### 查看指标

```bash
# 查看系统资源
top -p $(pgrep -f memos_graph)

# 查看数据库连接
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='memos_graph'"

# 查看磁盘使用
df -h /backup/memos-graph
```

---

## 🎯 最佳实践

### 1. 定期验证备份

```bash
# 每周验证备份可恢复性
pg_restore -d memos_graph_test /backup/memos-graph/latest.sql.gz
```

### 2. 监控日志大小

```bash
# 定期检查日志大小
du -sh logs/
```

### 3. 测试故障恢复

```bash
# 定期测试自动重启
sudo systemctl kill memos-graph
# 观察是否自动重启
```

### 4. 更新告警联系人

```bash
# 定期更新 webhook URL
# 确保告警能送达值班人员
```

---

## 📞 支持

- **GitHub Issues**: https://github.com/26bk9ck5vr-stack/memos-graph/issues
- **文档**: README.md
- **保活评估报告**: KEEPALIVE_ASSESSMENT.md

---

**memos-graph v3.0 - 生产级全自动保活，零人工介入！** 🚀
