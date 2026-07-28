#!/usr/bin/env python3
"""
memos-graph 健康检查脚本
========================
用于 systemd watchdog 或外部监控系统

使用方法:
    python3 health_check.py              # 完整检查
    python3 health_check.py --quick      # 仅检查服务是否运行
    python3 health_check.py --json       # 输出 JSON 格式
"""

import argparse
import sys
import os
import json
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error


def check_process() -> dict:
    """检查进程状态"""
    import subprocess
    
    result = {'running': False, 'pids': []}
    
    # 检查 memos-graph 进程
    proc_result = subprocess.run(
        ['pgrep', '-f', 'memos-graph'],
        capture_output=True, text=True
    )
    
    if proc_result.returncode == 0:
        result['running'] = True
        result['pids'] = proc_result.stdout.strip().split('\n')
    
    return result


def check_http_health() -> dict:
    """检查 HTTP 健康端点"""
    result = {'healthy': False, 'status': None, 'latency_ms': None}
    
    health_url = 'http://127.0.0.1:8765/health'
    
    try:
        start = datetime.now()
        req = urllib.request.Request(health_url, method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            latency = (datetime.now() - start).total_seconds() * 1000
            result['healthy'] = response.status == 200
            result['status'] = response.status
            result['latency_ms'] = round(latency, 2)
    except urllib.error.URLError as e:
        result['error'] = str(e.reason)
    except Exception as e:
        result['error'] = str(e)
    
    return result


def check_postgres() -> dict:
    """检查 PostgreSQL 连接"""
    import subprocess
    
    result = {'connected': False, 'version': None}
    
    proc_result = subprocess.run(
        ['psql', '-U', 'postgres', '-t', '-c', 'SELECT version();'],
        capture_output=True, text=True, timeout=5
    )
    
    if proc_result.returncode == 0:
        result['connected'] = True
        lines = proc_result.stdout.strip().split('\n')
        if len(lines) >= 1:
            result['version'] = lines[0].strip()
    else:
        result['error'] = proc_result.stderr.strip()
    
    return result


def check_disk_space() -> dict:
    """检查磁盘空间"""
    import subprocess
    
    result = {'usage_percent': 0, 'available_gb': 0, 'ok': True}
    
    proc_result = subprocess.run(
        ['df', '-h', '/'],
        capture_output=True, text=True
    )
    
    if proc_result.returncode == 0:
        lines = proc_result.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            usage = int(parts[4].replace('%', ''))
            result['usage_percent'] = usage
            result['available_gb'] = parts[3]  # Available
            result['ok'] = usage < 80  # 80% 阈值
    
    return result


def check_log_errors() -> dict:
    """检查日志中的错误数量"""
    result = {'error_count': 0, 'critical_count': 0, 'ok': True}
    
    log_dir = Path.home() / '.memos-graph' / 'logs'
    if not log_dir.exists():
        return result
    
    try:
        for log_file in log_dir.glob('*.log'):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                result['error_count'] += content.count('ERROR')
                result['critical_count'] += content.count('CRITICAL')
        
        # 如果错误数超过 100，标记为不健康
        result['ok'] = result['error_count'] < 100
    except Exception:
        pass
    
    return result


def run_health_check(quick: bool = False) -> dict:
    """执行健康检查"""
    checks = {
        'process': check_process(),
        'http': check_http_health(),
        'postgres': check_postgres(),
        'disk': check_disk_space(),
        'logs': check_log_errors(),
    }
    
    # 快速模式只检查进程
    if quick:
        return {
            'healthy': checks['process']['running'],
            'checks': {'process': checks['process']},
            'timestamp': datetime.now().isoformat()
        }
    
    # 完整检查
    overall_healthy = (
        checks['process']['running'] and
        checks['http']['healthy'] and
        checks['postgres']['connected'] and
        checks['disk']['ok'] and
        checks['logs']['ok']
    )
    
    return {
        'healthy': overall_healthy,
        'checks': checks,
        'timestamp': datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description='memos-graph 健康检查')
    parser.add_argument('--quick', action='store_true', help='快速检查')
    parser.add_argument('--json', action='store_true', help='JSON 输出')
    args = parser.parse_args()
    
    result = run_health_check(quick=args.quick)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # 人类可读输出
        status = "✓ HEALTHY" if result['healthy'] else "✗ UNHEALTHY"
        print(f"memos-graph 健康检查 - {datetime.now().isoformat()}")
        print(f"状态：{status}")
        print()
        
        for check_name, check_data in result['checks'].items():
            if isinstance(check_data, dict):
                if check_data.get('running') is True:
                    print(f"  ✓ {check_name}: 运行中 (PIDs: {', '.join(check_data.get('pids', []))})")
                elif check_data.get('healthy') is True:
                    latency = check_data.get('latency_ms', 'N/A')
                    print(f"  ✓ {check_name}: 健康 ({latency}ms)")
                elif check_data.get('connected') is True:
                    print(f"  ✓ {check_name}: 已连接")
                elif check_data.get('ok') is True:
                    print(f"  ✓ {check_name}: 正常")
                else:
                    error = check_data.get('error', '未知错误')
                    print(f"  ✗ {check_name}: 异常 - {error}")
    
    # 返回退出码 (0=健康，1=不健康)
    return 0 if result['healthy'] else 1


if __name__ == '__main__':
    sys.exit(main())
