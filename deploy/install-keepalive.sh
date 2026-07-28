#!/bin/bash
# memos-graph 全自动保活系统安装脚本
# 一键部署，无需人工介入

set -e

echo "🚀 开始安装 memos-graph 全自动保活系统..."

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="${PROJECT_DIR}/deploy/memos-graph.service"

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  请使用 sudo 运行此脚本"
    echo "sudo ${BASH_SOURCE[0]}"
    exit 1
fi

# 1. 创建备份目录
echo "📁 创建备份目录..."
mkdir -p /backup/memos-graph
chown gato:gato /backup/memos-graph
chmod 755 /backup/memos-graph

# 2. 创建日志目录
echo "📁 创建日志目录..."
mkdir -p "${PROJECT_DIR}/logs"
chown gato:gato "${PROJECT_DIR}/logs"
chmod 755 "${PROJECT_DIR}/logs"

# 3. 设置脚本权限
echo "🔧 设置脚本权限..."
chmod +x "${PROJECT_DIR}/bin/keepalive.sh"
chown gato:gato "${PROJECT_DIR}/bin/keepalive.sh"

# 4. 安装 systemd 服务
echo "📋 安装 systemd 服务..."
cp "${SERVICE_FILE}" /etc/systemd/system/memos-graph.service
systemctl daemon-reload

# 5. 启用服务
echo "⚙️  启用服务..."
systemctl enable memos-graph.service

# 6. 启动服务
echo "🚀 启动服务..."
systemctl start memos-graph.service

# 7. 检查状态
sleep 3
echo ""
echo "📊 服务状态:"
systemctl status memos-graph.service --no-pager | head -20

# 8. 验证
echo ""
echo "🔍 验证服务..."
if systemctl is-active --quiet memos-graph.service; then
    echo "✅ memos-graph 服务已成功启动！"
    echo ""
    echo "📝 常用命令:"
    echo "  查看状态：sudo systemctl status memos-graph"
    echo "  查看日志：sudo journalctl -u memos-graph -f"
    echo "  重启服务：sudo systemctl restart memos-graph"
    echo "  停止服务：sudo systemctl stop memos-graph"
    echo ""
    echo "📋 保活功能:"
    echo "  ✅ 进程崩溃自动重启 (最多 5 次/5 分钟)"
    echo "  ✅ 健康检查失败自动重启"
    echo "  ✅ 每天 03:00 自动备份数据库"
    echo "  ✅ 每周日 04:00 自动轮转日志"
    echo "  ✅ 资源监控 (CPU/内存/磁盘)"
    echo "  ✅ 开机自启动"
    echo ""
    echo "⚙️  配置告警 (可选):"
    echo "  编辑 /etc/systemd/system/memos-graph.service"
    echo "  添加环境变量:"
    echo "    MEMOS_ALERT_WEBHOOK=你的钉钉/企业微信 webhook"
    echo "    MEMOS_ALERT_ENABLED=true"
    echo "  然后运行：sudo systemctl daemon-reload && sudo systemctl restart memos-graph"
else
    echo "❌ 服务启动失败，请检查日志:"
    echo "  sudo journalctl -u memos-graph -n 50"
    exit 1
fi
