#!/bin/bash
# GitHub 推送脚本
# 使用方法：./push_to_github.sh

REPO_URL="https://github.com/26bk9ck5vr-stack/memos-graph.git"
BRANCH="master"

echo "🚀 准备推送到 GitHub..."
echo "仓库：$REPO_URL"
echo "分支：$BRANCH"
echo ""

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo "⚠️  有未提交的更改，请先提交"
    git status --short
    exit 1
fi

# 显示最近的提交
echo "📝 最近提交:"
git log --oneline -3
echo ""

# 推送
echo "📤 推送到 GitHub..."
git push $REPO_URL $BRANCH

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 推送成功！"
    echo "🌐 查看仓库：https://github.com/26bk9ck5vr-stack/memos-graph"
else
    echo ""
    echo "❌ 推送失败"
    echo ""
    echo "可能的解决方案:"
    echo "1. 使用 GitHub Personal Access Token:"
    echo "   git remote set-url origin https://YOUR_TOKEN@github.com/26bk9ck5vr-stack/memos-graph.git"
    echo "   git push origin master"
    echo ""
    echo "2. 使用 SSH (需要配置 SSH key):"
    echo "   git remote set-url origin git@github.com:26bk9ck5vr-stack/memos-graph.git"
    echo "   git push origin master"
    echo ""
    echo "3. 使用 gh CLI:"
    echo "   gh auth login"
    echo "   git push origin master"
fi
