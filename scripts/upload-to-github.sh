#!/bin/bash
# GitHub 上传脚本 - memos-graph v2.0.0

set -e

REPO_URL="git@github.com:26bk9ck5vr-stack/memos-graph.git"
VERSION="v2.0.0"

echo "📦 memos-graph $VERSION GitHub 上传脚本"
echo "=========================================="
echo ""

# 检查 SSH key
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "⚠️  未找到 SSH key，正在生成..."
    ssh-keygen -t ed25519 -C "gato@memos-graph" -f ~/.ssh/id_ed25519 -N ""
    echo "✅ SSH key 已生成，请添加到 GitHub:"
    echo "   1. 复制以下内容:"
    cat ~/.ssh/id_ed25519.pub
    echo ""
    echo "   2. 访问：https://github.com/settings/keys"
    echo "   3. 点击 'New SSH key' 并粘贴"
    echo ""
    read -p "按回车继续..."
fi

# 测试 SSH 连接
echo "🔑 测试 SSH 连接..."
ssh -T -o StrictHostKeyChecking=no git@github.com 2>&1 | grep -q "successfully authenticated" && echo "✅ SSH 连接成功" || {
    echo "⚠️  SSH 连接失败，请检查 SSH key 配置"
    exit 1
}

cd /home/gato/memos-graph

# 推送代码
echo ""
echo "📤 推送代码到 GitHub..."
git push -u origin master

if [ $? -eq 0 ]; then
    echo "✅ 代码推送成功！"
    echo ""
    echo "📝 接下来请手动创建 Release:"
    echo "   1. 访问：https://github.com/26bk9ck5vr-stack/memos-graph/releases/new"
    echo "   2. Tag version: $VERSION"
    echo "   3. Release title: memos-graph $VERSION - 完全体发布"
    echo "   4. 复制 RELEASE_$VERSION.md 的内容到描述"
    echo "   5. 点击 'Publish release'"
    echo ""
    echo "🎉 完成！"
else
    echo "❌ 推送失败，请检查网络连接"
    exit 1
fi
