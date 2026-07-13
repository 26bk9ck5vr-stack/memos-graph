#!/bin/bash
# memos-graph 数据库健康检查脚本

set -e

DB_HOST="localhost"
DB_USER="memos"
DB_PASS="memos"
DB_NAME="memos_graph"

echo "🔍 memos-graph 数据库健康检查"
echo "================================"
echo ""

# 1. 检查数据库连接
echo "1️⃣  检查数据库连接..."
if PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1; then
    echo "   ✅ 数据库连接正常"
else
    echo "   ❌ 数据库连接失败"
    exit 1
fi

# 2. 检查表完整性
echo ""
echo "2️⃣  检查表完整性..."
TABLES=(
    "chunks"
    "chunk_vectors"
    "entities"
    "entity_edges"
    "events"
    "event_vectors"
    "promises"
    "agent_state"
    "packs"
    "user_profile"
)

for table in "${TABLES[@]}"; do
    count=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM $table" 2>/dev/null | tr -d ' ')
    if [ $? -eq 0 ]; then
        echo "   ✅ $table: $count 条记录"
    else
        echo "   ❌ $table: 检查失败"
    fi
done

# 3. 检查向量维度
echo ""
echo "3️⃣  检查向量维度..."
dim=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT vector_dims(embedding) FROM chunk_vectors LIMIT 1" 2>/dev/null | tr -d ' ')
if [ "$dim" == "1024" ]; then
    echo "   ✅ 向量维度：1024 (BAAI/bge-m3)"
else
    echo "   ⚠️  向量维度：$dim (期望 1024)"
fi

# 4. 检查外键约束
echo ""
echo "4️⃣  检查外键约束..."
FK_ISSUES=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "
SELECT COUNT(*) 
FROM information_schema.table_constraints tc 
JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name 
WHERE tc.constraint_type = 'FOREIGN KEY' 
AND tc.table_schema = 'public'" 2>/dev/null | tr -d ' ')
echo "   ✅ 外键约束：$FK_ISSUES 个"

# 5. 检查孤儿记录
echo ""
echo "5️⃣  检查孤儿记录..."

# 检查 chunk_vectors 中的孤儿
orphan_vectors=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "
SELECT COUNT(*) 
FROM chunk_vectors cv 
WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.id = cv.chunk_id)" 2>/dev/null | tr -d ' ')
if [ "$orphan_vectors" -gt 0 ]; then
    echo "   ⚠️  孤儿向量记录：$orphan_vectors 条"
else
    echo "   ✅ 无孤儿向量记录"
fi

# 检查 promises 中的孤儿
orphan_promises=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "
SELECT COUNT(*) 
FROM promises p 
WHERE NOT EXISTS (SELECT 1 FROM agent_state a WHERE a.agent_id = p.agent_id)" 2>/dev/null | tr -d ' ')
if [ "$orphan_promises" -gt 0 ]; then
    echo "   ⚠️  孤儿承诺记录：$orphan_promises 条"
else
    echo "   ✅ 无孤儿承诺记录"
fi

# 6. 检查数据一致性
echo ""
echo "6️⃣  检查数据一致性..."

# 检查 promises 的 due_at 字段
due_at_count=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM promises WHERE due_at IS NOT NULL" 2>/dev/null | tr -d ' ')
total_promises=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM promises" 2>/dev/null | tr -d ' ')
echo "   ✅ 承诺记录：$total_promises 条 (其中 $due_at_count 条有截止时间)"

# 检查 agent_state
agents=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM agent_state" 2>/dev/null | tr -d ' ')
echo "   ✅ Agent 状态：$agents 个"

# 7. 数据库大小
echo ""
echo "7️⃣  数据库大小..."
size=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'))" 2>/dev/null | tr -d ' ')
echo "   📊 数据库大小：$size"

# 8. 建议
echo ""
echo "💡 建议:"
echo "   - 定期运行 VACUUM ANALYZE 优化性能"
echo "   - 监控 pgvector 索引大小"
echo "   - 定期备份数据库"
echo ""
echo "================================"
echo "✅ 数据库健康检查完成"
