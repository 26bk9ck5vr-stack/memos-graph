#!/bin/bash
# 后台更新 tsvector
PGPASSWORD=memos psql -h localhost -U memos -d memos_graph << 'EOF'
UPDATE chunks SET tsvector = to_tsvector('simple', content) WHERE tsvector IS NULL;
EOF
echo "Tsvector 更新完成"
