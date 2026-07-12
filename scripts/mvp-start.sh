#!/bin/bash
# memos-graph MVP 一键启动脚本
# 用途：快速启动 MVP 版本服务并验证

set -e

echo "=== memos-graph MVP 启动脚本 ==="

# 1. 进入项目目录
cd /home/gato/memos-graph

# 2. 激活虚拟环境
echo "[1/5] 激活虚拟环境..."
source .venv/bin/activate

# 3. 检查配置文件
echo "[2/5] 检查配置文件..."
if [ ! -f ~/.config/memos-graph/config.yaml ]; then
    echo "❌ 配置文件不存在：~/.config/memos-graph/config.yaml"
    exit 1
fi
echo "✅ 配置文件检查通过"

# 4. 数据库初始化（如果未初始化）
echo "[3/5] 检查数据库..."
python3 << 'EOF'
import asyncio
from memos_graph.db.session import create_session_factory, _async_session_factory
from memos_graph.config import load_config

cfg = load_config()
create_session_factory(cfg.database.url)

async def check_db():
    try:
        async with _async_session_factory() as session:
            await session.execute("SELECT 1")
        print("✅ 数据库连接正常")
    except Exception as e:
        print(f"❌ 数据库连接失败：{e}")
        exit(1)

asyncio.run(check_db())
EOF

# 5. 启动服务
echo "[4/5] 启动 API 服务..."
pkill -f "uvicorn memos_graph.server" 2>/dev/null || true
sleep 2
python3 -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765 &
SERVER_PID=$!
echo "服务器 PID: $SERVER_PID"

# 6. 等待服务启动
echo "[5/5] 等待服务启动..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8765/api/v1/health > /dev/null 2>&1; then
        echo "✅ 服务启动成功！"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ 服务启动超时"
        exit 1
    fi
    sleep 1
done

# 7. 运行验证测试
echo ""
echo "=== 运行验证测试 ==="
bash /home/gato/memos-graph/scripts/mvp-verify.sh

echo ""
echo "=== MVP 启动完成 ==="
echo "API 地址：http://127.0.0.1:8765"
echo "健康检查：curl http://127.0.0.1:8765/api/v1/health"
echo "停止服务：pkill -f 'uvicorn memos_graph.server'"
