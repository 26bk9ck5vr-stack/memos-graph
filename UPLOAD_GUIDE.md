# memos-graph v2.0.0 - GitHub 上传指南

## 📦 已完成的准备工作

✅ 1. 代码已打包：`/home/gato/memos-graph-v2.0.0.tar.gz` (283KB)
✅ 2. .gitignore 已配置（排除敏感文件）
✅ 3. config.example.yaml 已创建（示例配置）
✅ 4. README.md 已更新（完整文档）
✅ 5. requirements.txt 已生成
✅ 6. 上传脚本已创建：`scripts/upload-to-github.sh`

## 🚀 上传方法

### 方法 1: 使用上传脚本（推荐）

```bash
cd /home/gato/memos-graph
./scripts/upload-to-github.sh
```

脚本会自动：
1. 检查 SSH key（如无则生成）
2. 测试 GitHub 连接
3. 推送代码到 master 分支
4. 提供 Release 创建指南

### 方法 2: 手动上传压缩包

1. **解压代码包**
   ```bash
   cd /home/gato
   tar -xzf memos-graph-v2.0.0.tar.gz -C /tmp/memos-graph-upload
   cd /tmp/memos-graph-upload
   ```

2. **初始化 Git 并推送**
   ```bash
   git init
   git add .
   git commit -m "🎉 memos-graph v2.0.0 初始提交"
   git remote add origin git@github.com:26bk9ck5vr-stack/memos-graph.git
   git push -u origin master
   ```

### 方法 3: GitHub Desktop

1. 下载并安装 [GitHub Desktop](https://desktop.github.com/)
2. 克隆仓库：`git clone git@github.com:26bk9ck5vr-stack/memos-graph.git`
3. 复制所有文件到克隆的目录
4. 使用 GitHub Desktop 提交并推送

## 🔑 SSH Key 配置（首次使用）

如果还没有配置 GitHub SSH key：

```bash
# 1. 生成 SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub

# 3. 添加到 GitHub
# 访问：https://github.com/settings/keys
# 点击 "New SSH key" 并粘贴公钥

# 4. 测试连接
ssh -T git@github.com
```

## 📝 创建 Release

推送代码后，创建 GitHub Release：

1. **访问**: https://github.com/26bk9ck5vr-stack/memos-graph/releases/new

2. **填写信息**:
   - Tag version: `v2.0.0`
   - Target: `master`
   - Release title: `memos-graph v2.0.0 - 完全体发布 🎉`

3. **描述**: 复制 `RELEASE_v2.0.0.md` 的内容

4. **点击**: "Publish release"

## ✅ 验证清单

上传完成后验证：

- [ ] 代码已推送到 master 分支
- [ ] README.md 在 GitHub 上正确显示
- [ ] 所有源代码文件可见
- [ ] 没有敏感信息泄露（检查 config.yaml）
- [ ] Release v2.0.0 已创建

## 🔒 安全检查

上传前请确认以下文件**未**包含在提交中：

```bash
# 检查是否有敏感文件
git ls-files | grep -E "(config\.yaml|\.env|\.key|secret)"

# 应该只看到：
# config.example.yaml ✅ (示例配置，不含真实密钥)
```

## 📊 项目统计

```bash
# 查看代码统计
cd /home/gato/memos-graph
cloc src/  # 如已安装 cloc

# 或手动统计
find src/ -name "*.py" | wc -l  # Python 文件数
wc -l src/**/*.py | tail -1     # 总代码行数
```

## 🎉 完成！

上传成功后，你的项目将在：
**https://github.com/26bk9ck5vr-stack/memos-graph**

---

**祝上传顺利！🚀**
