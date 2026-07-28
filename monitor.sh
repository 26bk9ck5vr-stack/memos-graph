#!/usr/bin/env bash
# memos-graph 监控脚本
# ====================
# 用于 cron 定时任务，定期检查服务健康状态并发送告警
#
# 安装:
#   chmod +x /home/gato/memos-graph/monitor.sh
#   crontab -e
#   # 添加：*/5 * * * * /home/gato/memos-graph/monitor.sh >> /var/log/memos-graph-monitor.log 2>&1

set -e

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/home/gato/.memos-graph/logs"
ALERT_EMAIL=""  # 可选：设置告警邮箱
SLACK_WEBHOOK=""  # 可选：设置 Slack webhook

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 告警函数
send_alert() {
    local message="$1"
    log "${RED}ALERT: $message${NC}"
    
    # 邮件告警 (如果配置)
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "memos-graph Alert" "$ALERT_EMAIL"
    fi
    
    # Slack 告警 (如果配置)
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"memos-graph Alert: $message\"}" \
            "$SLACK_WEBHOOK"
    fi
}

# 检查服务状态
check_service() {
    local service_name="$1"
    
    if systemctl is-active --quiet "$service_name"; then
        log "${GREEN}✓ $service_name is active${NC}"
        return 0
    else
        log "${RED}✗ $service_name is NOT active${NC}"
        return 1
    fi
}

# 检查进程
check_process() {
    local pattern="$1"
    
    if pgrep -f "$pattern" > /dev/null; then
        local pids=$(pgrep -f "$pattern" | tr '\n' ' ')
        log "${GREEN}✓ Process '$pattern' running (PIDs: $pids)${NC}"
        return 0
    else
        log "${RED}✗ Process '$pattern' NOT running${NC}"
        return 1
    fi
}

# 检查磁盘空间
check_disk() {
    local threshold=80
    local usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$usage" -gt "$threshold" ]; then
        log "${YELLOW}⚠ Disk usage at ${usage}% (threshold: ${threshold}%)${NC}"
        send_alert "Disk usage at ${usage}% on $(hostname)"
        return 1
    else
        log "${GREEN}✓ Disk usage at ${usage}%${NC}"
        return 0
    fi
}

# 检查内存
check_memory() {
    local threshold=90
    local usage=$(free | grep Mem | awk '{printf("%.0f", $3/$2*100.0)}')
    
    if [ "$usage" -gt "$threshold" ]; then
        log "${YELLOW}⚠ Memory usage at ${usage}% (threshold: ${threshold}%)${NC}"
        send_alert "Memory usage at ${usage}% on $(hostname)"
        return 1
    else
        log "${GREEN}✓ Memory usage at ${usage}%${NC}"
        return 0
    fi
}

# 检查日志错误
check_log_errors() {
    local log_pattern="$LOG_DIR/*.log"
    local error_count=0
    
    if ls $log_pattern 1> /dev/null 2>&1; then
        error_count=$(grep -c "ERROR\|CRITICAL" $log_pattern 2>/dev/null | awk -F: '{sum+=$2} END {print sum}')
    fi
    
    if [ "$error_count" -gt 100 ]; then
        log "${YELLOW}⚠ High error count: $error_count errors in logs${NC}"
        send_alert "High error count: $error_count errors in memos-graph logs"
        return 1
    else
        log "${GREEN}✓ Error count: $error_count${NC}"
        return 0
    fi
}

# 检查 PostgreSQL 连接
check_postgres() {
    if psql -U postgres -c "SELECT 1;" > /dev/null 2>&1; then
        log "${GREEN}✓ PostgreSQL connection OK${NC}"
        return 0
    else
        log "${RED}✗ PostgreSQL connection FAILED${NC}"
        send_alert "PostgreSQL connection failed on $(hostname)"
        return 1
    fi
}

# 检查 HTTP 健康端点
check_http_health() {
    local url="http://127.0.0.1:8765/health"
    
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        log "${GREEN}✓ HTTP health check OK ($url)${NC}"
        return 0
    else
        log "${RED}✗ HTTP health check FAILED ($url)${NC}"
        send_alert "memos-graph HTTP health check failed on $(hostname)"
        return 1
    fi
}

# 自动恢复服务
auto_recovery() {
    local service_name="$1"
    
    log "Attempting to restart $service_name..."
    
    if systemctl restart "$service_name"; then
        log "${GREEN}✓ $service_name restarted successfully${NC}"
        send_alert "$service_name was automatically restarted on $(hostname)"
        return 0
    else
        log "${RED}✗ Failed to restart $service_name${NC}"
        send_alert "Failed to restart $service_name on $(hostname)"
        return 1
    fi
}

# 主函数
main() {
    log "=========================================="
    log "Starting memos-graph health check"
    log "=========================================="
    
    local issues=0
    
    # 系统资源检查
    check_disk || ((issues++))
    check_memory || ((issues++))
    
    # 服务检查
    check_service "postgresql" || ((issues++))
    check_service "memos-graph" || {
        # 尝试自动恢复
        sleep 5
        check_process "memos-graph" || {
            auto_recovery "memos-graph" || ((issues++))
        }
    }
    
    # 进程检查 (双重确认)
    check_process "memos-graph" || ((issues++))
    
    # 连接检查
    check_postgres || ((issues++))
    check_http_health || ((issues++))
    
    # 日志检查
    check_log_errors || ((issues++))
    
    # 总结
    log "=========================================="
    if [ $issues -eq 0 ]; then
        log "${GREEN}All checks passed!${NC}"
    else
        log "${YELLOW}$issues check(s) failed${NC}"
    fi
    log "=========================================="
    
    return $issues
}

# 执行
main
exit $?
