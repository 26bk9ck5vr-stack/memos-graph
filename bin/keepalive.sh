#!/bin/bash
# memos-graph 全自动保活脚本
# 功能：监控 + 自愈 + 备份 + 告警 一体化

set -e

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/.."
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="/backup/memos-graph"
PID_FILE="/tmp/memos-graph.pid"
HEALTH_URL="http://localhost:8765/api/v1/health/ready"
MAX_RESTART_COUNT=5
RESTART_WINDOW=300  # 5 分钟内最多重启 5 次

# 告警配置 (钉钉/企业微信 webhook)
ALERT_WEBHOOK="${MEMOS_ALERT_WEBHOOK:-}"  # 从环境变量读取
ALERT_ENABLED="${MEMOS_ALERT_ENABLED:-false}"

# 监控阈值
CPU_THRESHOLD=90
MEMORY_THRESHOLD=90
DISK_THRESHOLD=85
DB_CONNECTION_THRESHOLD=8

# ==================== 初始化 ====================
mkdir -p "${LOG_DIR}" "${BACKUP_DIR}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_DIR}/keepalive.log"
}

send_alert() {
    local message="$1"
    local level="$2"  # INFO/WARN/ERROR/CRITICAL
    
    if [ "${ALERT_ENABLED}" != "true" ] || [ -z "${ALERT_WEBHOOK}" ]; then
        log "[ALERT] ${level}: ${message}"
        return
    fi
    
    # 钉钉/企业微信通用格式
    local payload="{
        \"msgtype\": \"markdown\",
        \"markdown\": {
            \"title\": \"memos-graph ${level}\",
            \"text\": \"**memos-graph ${level}**\\n\\n${message}\\n\\n时间：$(date '+%Y-%m-%d %H:%M:%S')\"
        }
    }"
    
    curl -s -X POST "${ALERT_WEBHOOK}" \
        -H "Content-Type: application/json" \
        -d "${payload}" > /dev/null || true
}

# ==================== 进程守护 ====================
get_process_pid() {
    pgrep -f "memos_graph.server:create_app" 2>/dev/null || echo ""
}

is_process_alive() {
    local pid=$(get_process_pid)
    [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

start_service() {
    log "启动 memos-graph 服务..."
    
    cd "${PROJECT_DIR}"
    
    # 激活虚拟环境
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
    
    # 后台启动
    nohup python3 -m uvicorn memos_graph.server:create_app \
        --factory \
        --host 0.0.0.0 \
        --port 8765 \
        >> "${LOG_DIR}/server.log" 2>&1 &
    
    local pid=$!
    echo "${pid}" > "${PID_FILE}"
    
    # 等待启动
    sleep 3
    
    if is_process_alive; then
        log "✅ 服务启动成功 (PID: ${pid})"
        send_alert "服务已自动重启\nPID: ${pid}" "INFO"
        return 0
    else
        log "❌ 服务启动失败"
        send_alert "服务启动失败，需要人工介入！" "CRITICAL"
        return 1
    fi
}

stop_service() {
    log "停止 memos-graph 服务..."
    
    local pid=$(get_process_pid)
    if [ -n "${pid}" ]; then
        kill "${pid}" 2>/dev/null || true
        sleep 2
        # 强制停止
        kill -9 "${pid}" 2>/dev/null || true
        log "✅ 服务已停止 (PID: ${pid})"
    fi
    
    rm -f "${PID_FILE}"
}

restart_service() {
    local restart_count_file="${LOG_DIR}/restart_count"
    local current_time=$(date +%s)
    
    # 读取上次重启时间
    local last_reset=0
    local count=0
    if [ -f "${restart_count_file}" ]; then
        last_reset=$(cat "${restart_count_file}" | head -1)
        count=$(cat "${restart_count_file}" | tail -1)
    fi
    
    # 如果超过时间窗口，重置计数
    if [ $((current_time - last_reset)) -gt ${RESTART_WINDOW} ]; then
        count=0
    fi
    
    # 检查重启频率
    count=$((count + 1))
    echo -e "${current_time}\n${count}" > "${restart_count_file}"
    
    if [ ${count} -gt ${MAX_RESTART_COUNT} ]; then
        log "❌ 5 分钟内重启 ${count} 次，超过限制，停止自动重启"
        send_alert "5 分钟内重启${count}次，服务可能存在严重问题，已停止自动重启" "CRITICAL"
        return 1
    fi
    
    log "重启服务 (第 ${count} 次/${MAX_RESTART_COUNT} 次)..."
    stop_service
    sleep 2
    start_service
}

# ==================== 健康检查 ====================
check_health() {
    local max_retries=3
    local retry=0
    
    while [ ${retry} -lt ${max_retries} ]; do
        local response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "${HEALTH_URL}" 2>/dev/null || echo "000")
        
        if [ "${response}" = "200" ]; then
            return 0
        fi
        
        retry=$((retry + 1))
        sleep 2
    done
    
    return 1
}

check_database() {
    # 检查 PostgreSQL 是否运行
    if ! pg_isready -q 2>/dev/null; then
        log "❌ PostgreSQL 未运行"
        return 1
    fi
    
    # 检查数据库连接数
    local conn_count=$(psql -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='memos_graph'" 2>/dev/null | tr -d ' ')
    
    if [ -n "${conn_count}" ] && [ "${conn_count}" -gt "${DB_CONNECTION_THRESHOLD}" ]; then
        log "⚠️  数据库连接数过高：${conn_count}/${DB_CONNECTION_THRESHOLD}"
        send_alert "数据库连接数过高：${conn_count}" "WARN"
        return 1
    fi
    
    return 0
}

# ==================== 资源监控 ====================
check_resources() {
    local alerts=""
    
    # CPU 使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 | cut -d'.' -f1)
    if [ -n "${cpu_usage}" ] && [ "${cpu_usage}" -gt "${CPU_THRESHOLD}" ]; then
        alerts="${alerts}CPU 使用率过高：${cpu_usage}%\\n"
    fi
    
    # 内存使用率
    local mem_usage=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
    if [ "${mem_usage}" -gt "${MEMORY_THRESHOLD}" ]; then
        alerts="${alerts}内存使用率过高：${mem_usage}%\\n"
    fi
    
    # 磁盘使用率
    local disk_usage=$(df -h "${PROJECT_DIR}" | awk 'NR==2 {print $5}' | tr -d '%')
    if [ "${disk_usage}" -gt "${DISK_THRESHOLD}" ]; then
        alerts="${alerts}磁盘使用率过高：${disk_usage}%\\n"
    fi
    
    if [ -n "${alerts}" ]; then
        log "⚠️  资源告警：${alerts}"
        send_alert "${alerts}" "WARN"
        return 1
    fi
    
    return 0
}

# ==================== 自动备份 ====================
backup_database() {
    local backup_file="${BACKUP_DIR}/db_$(date +%Y%m%d_%H%M%S).sql.gz"
    
    log "开始备份数据库..."
    
    if pg_dump memos_graph 2>/dev/null | gzip > "${backup_file}"; then
        log "✅ 数据库备份成功：${backup_file}"
        
        # 保留最近 7 天的备份
        find "${BACKUP_DIR}" -name "db_*.sql.gz" -mtime +7 -delete
        log "已清理 7 天前的旧备份"
        
        return 0
    else
        log "❌ 数据库备份失败"
        send_alert "数据库备份失败" "ERROR"
        return 1
    fi
}

# ==================== 日志轮转 ====================
rotate_logs() {
    log "执行日志轮转..."
    
    # 日志文件超过 10MB 时轮转
    find "${LOG_DIR}" -name "*.log" -size +10M -exec mv {} {}.1 \;
    
    # 保留最近 5 个轮转日志
    find "${LOG_DIR}" -name "*.log.[0-9]*" -mtime +30 -delete
    
    log "✅ 日志轮转完成"
}

# ==================== 主循环 ====================
main_loop() {
    log "🚀 memos-graph 全自动保活系统启动"
    log "监控间隔：60 秒 | 备份间隔：每天 03:00 | 日志轮转：每周日 04:00"
    
    local last_backup=$(date +%u)  # 星期几
    local last_rotate=$(date +%u)
    
    while true; do
        local current_time=$(date +%s)
        local current_hour=$(date +%H)
        local current_minute=$(date +%M)
        local current_weekday=$(date +%u)
        
        # 1. 检查进程是否存在
        if ! is_process_alive; then
            log "❌ 进程不存在，尝试重启..."
            send_alert "进程消失，正在自动重启" "WARN"
            restart_service
            sleep 10
            continue
        fi
        
        # 2. 健康检查
        if ! check_health; then
            log "❌ 健康检查失败，尝试重启..."
            send_alert "健康检查失败，正在自动重启" "ERROR"
            restart_service
            sleep 10
            continue
        fi
        
        # 3. 数据库检查 (每 5 分钟)
        if [ $((current_time % 300)) -eq 0 ]; then
            if ! check_database; then
                log "⚠️  数据库异常"
            fi
        fi
        
        # 4. 资源监控 (每 5 分钟)
        if [ $((current_time % 300)) -eq 0 ]; then
            check_resources || true
        fi
        
        # 5. 自动备份 (每天 03:00)
        if [ "${current_hour}" = "03" ] && [ "${current_minute}" = "00" ] && [ "${current_weekday}" != "${last_backup}" ]; then
            backup_database || true
            last_backup="${current_weekday}"
        fi
        
        # 6. 日志轮转 (每周日 04:00)
        if [ "${current_hour}" = "04" ] && [ "${current_minute}" = "00" ] && [ "${current_weekday}" = "7" ] && [ "${current_weekday}" != "${last_rotate}" ]; then
            rotate_logs
            last_rotate="${current_weekday}"
        fi
        
        # 7. 清理重启计数 (每 5 分钟)
        local restart_count_file="${LOG_DIR}/restart_count"
        if [ -f "${restart_count_file}" ]; then
            local last_reset=$(head -1 "${restart_count_file}")
            if [ $((current_time - last_reset)) -gt ${RESTART_WINDOW} ]; then
                echo -e "${current_time}\n0" > "${restart_count_file}"
            fi
        fi
        
        # 等待 60 秒
        sleep 60
    done
}

# ==================== 命令行接口 ====================
case "${1:-run}" in
    run)
        main_loop
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        if is_process_alive; then
            echo "✅ memos-graph 运行中 (PID: $(get_process_pid))"
            check_health && echo "✅ 健康检查通过" || echo "❌ 健康检查失败"
        else
            echo "❌ memos-graph 未运行"
        fi
        ;;
    backup)
        backup_database
        ;;
    *)
        echo "用法: $0 {run|start|stop|restart|status|backup}"
        exit 1
        ;;
esac
