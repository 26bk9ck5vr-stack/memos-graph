# memos-graph v2.0 网络访问指南

**更新时间**: 2026-07-13 14:45  
**监听地址**: 0.0.0.0:8765 (所有网络接口)

---

## 🌐 网络配置

### 服务器监听

**memos-graph 服务器**:
- **监听地址**: 0.0.0.0:8765
- **说明**: 监听所有网络接口，允许局域网访问

**Neo4j 数据库**:
- **Bolt 协议**: 0.0.0.0:7687
- **HTTP 协议**: 0.0.0.0:7474
- **说明**: 允许远程连接

### 本机网络信息

**局域网 IP**: `192.168.1.108`

---

## 📱 访问方式

### 1. 本机访问

```bash
# 使用 localhost
http://localhost:8765/
http://localhost:8765/dashboard
http://localhost:8765/neo4j-graph

# 或使用 0.0.0.0
http://0.0.0.0:8765/
http://0.0.0.0:8765/dashboard
http://0.0.0.0:8765/neo4j-graph
```

### 2. 局域网访问

**从同一局域网的其他设备访问**:

```
http://192.168.1.108:8765/
http://192.168.1.108:8765/dashboard
http://192.168.1.108:8765/neo4j-graph
```

**示例**:
- 手机浏览器：`http://192.168.1.108:8765/dashboard`
- 其他电脑：`http://192.168.1.108:8765/`

### 3. API 访问

**基础 URL**:
```
http://192.168.1.108:8765/api/v1/
```

**示例**:
```bash
# 获取 Agent 状态
curl http://192.168.1.108:8765/api/v1/agents/hermes/state

# 更新 Agent 状态
curl -X PUT http://192.168.1.108:8765/api/v1/agents/hermes/state \
  -H "Content-Type: application/json" \
  -d '{"stage":2,"affinity":60,"mood":75,"energy":80}'

# 获取承诺列表
curl "http://192.168.1.108:8765/api/v1/promises?agent_id=hermes&status=open"

# 获取图谱数据
curl "http://192.168.1.108:8765/api/v1/neo4j/graph?agent_id=hermes&limit=50"
```

---

## 🔧 配置详情

### memos-graph 配置

**文件**: `~/.config/memos-graph/config.yaml`

```yaml
database:
  url: postgresql+asyncpg://memos:memos@localhost:5432/memos_graph

neo4j:
  uri: bolt://0.0.0.0:7687  # ← 已改为 0.0.0.0
  username: neo4j
  password: memos2024

llm:
  base_url: https://maas-coding-api.cn-huabei-1.xf-yun.com/v2
  model: astron-code-latest
```

### Viewer 配置

**文件**: `src/memos_graph/viewer/dashboard.html`

```javascript
const API_BASE = 'http://0.0.0.0:8765/api/v1';  // ← 已改为 0.0.0.0
const AGENT_ID = 'hermes';
```

**文件**: `src/memos_graph/server.py`

```python
@app.get("/dashboard", response_class=FileResponse)
async def agent_dashboard():
    dashboard_path = Path(__file__).parent / "viewer" / "dashboard.html"
    return dashboard_path

@app.get("/neo4j-graph", response_class=FileResponse)
async def neo4j_graph_viewer():
    viewer_path = Path(__file__).parent / "viewer" / "neo4j-graph.html"
    return viewer_path
```

---

## 🛡️ 防火墙配置

如果需要从其他设备访问，确保防火墙允许 8765 和 7474/7687 端口：

### Ubuntu/Debian (UFW)

```bash
# 允许 memos-graph
sudo ufw allow 8765/tcp

# 允许 Neo4j
sudo ufw allow 7474/tcp
sudo ufw allow 7687/tcp

# 查看状态
sudo ufw status
```

### CentOS/RHEL (firewalld)

```bash
# 允许端口
sudo firewall-cmd --permanent --add-port=8765/tcp
sudo firewall-cmd --permanent --add-port=7474/tcp
sudo firewall-cmd --permanent --add-port=7687/tcp

# 重新加载
sudo firewall-cmd --reload

# 查看状态
sudo firewall-cmd --list-ports
```

### iptables

```bash
# 允许端口
sudo iptables -A INPUT -p tcp --dport 8765 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 7474 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 7687 -j ACCEPT

# 保存规则
sudo iptables-save > /etc/iptables/rules.v4
```

---

## 🔍 网络测试

### 1. 检查端口监听

```bash
# 查看 memos-graph 端口
ss -tlnp | grep 8765

# 查看 Neo4j 端口
ss -tlnp | grep -E "7474|7687"
```

**预期输出**:
```
LISTEN 0      128          0.0.0.0:8765       0.0.0.0:*    users:(("python",pid=102150,fd=3))
LISTEN 0      128          0.0.0.0:7474       0.0.0.0:*    users:(("java",pid=100355,fd=12))
LISTEN 0      128          0.0.0.0:7687       0.0.0.0:*    users:(("java",pid=100355,fd=15))
```

### 2. 本地连接测试

```bash
# 测试 memos-graph
curl http://localhost:8765/dashboard | head -5

# 测试 Neo4j HTTP
curl -u neo4j:memos2024 http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "MATCH (n) RETURN count(n)"}]}'
```

### 3. 局域网连接测试

**从其他设备测试**:
```bash
# 假设你的 IP 是 192.168.1.100
curl http://192.168.1.108:8765/dashboard | head -5
```

**预期**: 返回 HTML 内容

---

## 📊 访问地址汇总

| 服务 | 本机访问 | 局域网访问 | 说明 |
|------|---------|-----------|------|
| **memos-graph** | `http://localhost:8765/` | `http://192.168.1.108:8765/` | 主页面 |
| **Agent Dashboard** | `http://localhost:8765/dashboard` | `http://192.168.1.108:8765/dashboard` | 高级监控 ✨ |
| **Neo4j 图谱** | `http://localhost:8765/neo4j-graph` | `http://192.168.1.108:8765/neo4j-graph` | 图谱可视化 ✨ |
| **API 端点** | `http://localhost:8765/api/v1/` | `http://192.168.1.108:8765/api/v1/` | REST API |
| **Neo4j Browser** | `http://localhost:7474` | `http://192.168.1.108:7474` | Neo4j 管理界面 |

---

## 🔐 安全建议

### 当前状态

⚠️ **注意**: 当前配置允许**所有设备**访问（监听 0.0.0.0），适合**受信任的局域网**环境。

### 加固建议

#### 1. 限制访问 IP (可选)

修改服务器代码，只允许特定 IP 访问：

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        allowed_ips = ["192.168.1.", "127.0.0.1"]  # 允许的 IP 段
        if not any(client_ip.startswith(ip) for ip in allowed_ips):
            raise HTTPException(status_code=403, detail="Access denied")
        return await call_next(request)

app.add_middleware(IPWhitelistMiddleware)
```

#### 2. 启用 HTTPS (生产环境推荐)

使用 Nginx 反向代理 + Let's Encrypt 证书：

```nginx
server {
    listen 443 ssl;
    server_name memos.example.com;
    
    ssl_certificate /etc/letsencrypt/live/memos.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/memos.example.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 3. 修改默认密码

```bash
# Neo4j 密码
cypher-shell -u neo4j -p memos2024
> ALTER CURRENT USER SET PASSWORD FROM 'memos2024' TO 'your_strong_password';
```

---

## 🚀 快速启动脚本

创建启动脚本 `start.sh`:

```bash
#!/bin/bash

echo "🚀 启动 memos-graph v2.0..."

# 1. 检查 PostgreSQL
if ! pg_isready -q; then
    echo "⚠️  PostgreSQL 未运行，正在启动..."
    pg_ctl start
fi

# 2. 检查 Neo4j
if ! sudo neo4j status > /dev/null 2>&1; then
    echo "⚠️  Neo4j 未运行，正在启动..."
    sudo neo4j start
fi

# 3. 启动 memos-graph
echo "📊 启动 memos-graph 服务器..."
cd /home/gato/memos-graph
.venv/bin/python -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765 &

# 4. 等待启动
sleep 10

# 5. 显示访问地址
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "✅ memos-graph 已启动！"
echo ""
echo "📱 访问地址:"
echo "   本机：http://localhost:8765/"
echo "   局域网：http://${LOCAL_IP}:8765/"
echo ""
echo "🎯 推荐访问:"
echo "   Dashboard: http://${LOCAL_IP}:8765/dashboard"
echo "   Neo4j 图谱：http://${LOCAL_IP}:8765/neo4j-graph"
echo ""
```

使用方式:
```bash
chmod +x start.sh
./start.sh
```

---

## 📝 故障排查

### 问题 1: 无法从其他设备访问

**可能原因**:
- 防火墙阻止
- 服务器未监听 0.0.0.0
- 网络隔离

**解决方法**:
```bash
# 1. 检查防火墙
sudo ufw status
sudo ufw allow 8765/tcp

# 2. 检查监听地址
ss -tlnp | grep 8765
# 应该显示 0.0.0.0:8765 而不是 127.0.0.1:8765

# 3. 重启服务器
pkill -f uvicorn
cd /home/gato/memos-graph
.venv/bin/python -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765
```

### 问题 2: Neo4j 连接失败

**可能原因**:
- Neo4j 未启动
- 密码错误
- Bolt 端口未监听

**解决方法**:
```bash
# 1. 检查 Neo4j 状态
sudo neo4j status

# 2. 重启 Neo4j
sudo neo4j restart

# 3. 检查端口
ss -tlnp | grep -E "7474|7687"

# 4. 测试连接
curl -u neo4j:memos2024 http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "RETURN 1"}]}'
```

### 问题 3: Dashboard 无法加载数据

**可能原因**:
- API 地址错误
- CORS 问题
- Agent 不存在

**解决方法**:
```bash
# 1. 检查 API 地址 (查看浏览器控制台)
# 应该是 http://0.0.0.0:8765/api/v1/...

# 2. 测试 API
curl http://localhost:8765/api/v1/agents/hermes/state

# 3. 如果 Agent 不存在，创建它
curl -X PUT http://localhost:8765/api/v1/agents/hermes/state \
  -H "Content-Type: application/json" \
  -d '{"stage":1,"affinity":50,"mood":50,"energy":50}'
```

---

## 🎉 总结

**memos-graph v2.0 已完全配置为局域网可访问！**

### 访问地址

- **本机**: http://localhost:8765/
- **局域网**: http://192.168.1.108:8765/
- **Dashboard**: http://192.168.1.108:8765/dashboard
- **Neo4j 图谱**: http://192.168.1.108:8765/neo4j-graph

### 关键配置

- ✅ 服务器监听：0.0.0.0:8765
- ✅ Neo4j Bolt: 0.0.0.0:7687
- ✅ Viewer API 地址：0.0.0.0:8765
- ✅ 防火墙规则：需手动配置

### 安全提示

⚠️ 当前配置适合**受信任的局域网**环境。如需公网访问，请配置防火墙、HTTPS 和认证机制。

---

**指南生成时间**: 2026-07-13 14:45  
**局域网 IP**: 192.168.1.108  
**服务状态**: ✅ 运行中
