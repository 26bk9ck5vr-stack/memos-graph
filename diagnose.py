#!/usr/bin/env python3
"""
memos-graph 诊断脚本
===================
一键收集系统、PostgreSQL、memos-graph 服务的诊断信息

使用方法:
    python3 diagnose.py              # 完整诊断
    python3 diagnose.py --quick      # 快速检查 (仅关键指标)
    python3 diagnose.py --service    # 仅服务状态
    python3 diagnose.py --postgres   # 仅 PostgreSQL 状态
    python3 diagnose.py --logs       # 仅日志分析
    python3 diagnose.py --export     # 导出到文件
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import json


class Colors:
    """终端颜色"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_status(label: str, status: str, details: str = None):
    """打印状态行"""
    color = Colors.GREEN if status == 'OK' else (Colors.RED if status == 'FAIL' else Colors.YELLOW)
    status_str = f"{color}[{status}]{Colors.RESET}"
    print(f"  {label:35} {status_str}", end='')
    if details:
        print(f" - {details}")
    else:
        print()


def run_command(cmd: List[str], timeout: int = 10, capture: bool = True) -> tuple:
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, '', 'Command timed out'
    except Exception as e:
        return -1, '', str(e)


def check_system_resources() -> Dict[str, Any]:
    """检查系统资源"""
    print_header("系统资源状态")
    result = {}
    
    # CPU 负载
    code, out, _ = run_command(['uptime'])
    if code == 0:
        print(f"  系统运行时间：{out.strip()}")
        result['uptime'] = out.strip()
    
    # 内存使用
    code, out, _ = run_command(['free', '-h'])
    if code == 0:
        print(f"  内存状态:\n{out}")
        result['memory'] = out.strip()
    
    # 磁盘使用
    code, out, _ = run_command(['df', '-h', '/'])
    if code == 0:
        print(f"  磁盘状态:\n{out}")
        result['disk'] = out.strip()
    
    # 日志目录大小
    log_dir = Path.home() / '.memos-graph' / 'logs'
    if log_dir.exists():
        code, out, _ = run_command(['du', '-sh', str(log_dir)])
        if code == 0:
            print(f"  日志目录大小：{out.strip()}")
            result['log_dir_size'] = out.strip()
    
    return result


def check_postgresql() -> Dict[str, Any]:
    """检查 PostgreSQL 状态"""
    print_header("PostgreSQL 状态")
    result = {'status': 'unknown'}
    
    # 系统服务状态
    code, out, err = run_command(['systemctl', 'is-active', 'postgresql'])
    if code == 0:
        print_status('PostgreSQL 服务', 'OK', out.strip())
        result['service_status'] = 'active'
    else:
        print_status('PostgreSQL 服务', 'FAIL', err.strip() or 'not running')
        result['service_status'] = 'inactive'
        return result
    
    # 监听端口
    code, out, _ = run_command(['ss', '-tlnp', '|', 'grep', '5432'], timeout=5)
    # 使用更可靠的方式
    code, out, _ = run_command(['bash', '-c', 'ss -tlnp 2>/dev/null | grep 5432 || netstat -tlnp 2>/dev/null | grep 5432 || echo "port check failed"'])
    if '5432' in out:
        print_status('PostgreSQL 端口 5432', 'OK', '监听中')
        result['port_listening'] = True
    else:
        print_status('PostgreSQL 端口 5432', 'WARN', '未在监听 (可能使用 Unix socket)')
        result['port_listening'] = False
    
    # 数据库连接测试
    code, out, err = run_command(['psql', '-U', 'postgres', '-c', 'SELECT version();'], timeout=5)
    if code == 0:
        print_status('数据库连接', 'OK')
        result['connection'] = 'ok'
        version_lines = out.strip().split('\n')
        if len(version_lines) >= 3:
            print(f"  PostgreSQL 版本：{version_lines[2].strip()}")
            result['version'] = version_lines[2].strip()
    else:
        print_status('数据库连接', 'FAIL', err.strip()[:100])
        result['connection'] = 'failed'
        result['connection_error'] = err.strip()
    
    # 检查 memos-graph 数据库
    code, out, err = run_command([
        'psql', '-U', 'postgres', '-c',
        "SELECT datname FROM pg_database WHERE datname LIKE '%memos%';"
    ], timeout=5)
    if code == 0 and 'memos' in out.lower():
        print_status('memos-graph 数据库', 'OK', '存在')
        result['memos_db_exists'] = True
    else:
        print_status('memos-graph 数据库', 'WARN', '未找到 (可能使用不同名称)')
        result['memos_db_exists'] = False
    
    # 活跃连接数
    code, out, _ = run_command([
        'psql', '-U', 'postgres', '-t', '-c',
        "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
    ], timeout=5)
    if code == 0:
        active_count = out.strip()
        print(f"  活跃连接数：{active_count}")
        result['active_connections'] = active_count
    
    # 慢查询检查
    code, out, _ = run_command([
        'psql', '-U', 'postgres', '-t', '-c',
        "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 minutes';"
    ], timeout=5)
    if code == 0:
        slow_count = int(out.strip() or 0)
        if slow_count > 0:
            print_status('慢查询 (>5 分钟)', 'WARN', f'{slow_count} 个')
        else:
            print_status('慢查询 (>5 分钟)', 'OK', '无')
        result['slow_queries'] = slow_count
    
    return result


def check_memos_graph_service() -> Dict[str, Any]:
    """检查 memos-graph 服务状态"""
    print_header("memos-graph 服务状态")
    result = {'status': 'unknown'}
    
    # systemd 服务状态
    code, out, err = run_command(['systemctl', 'is-active', 'memos-graph'])
    if code == 0:
        print_status('memos-graph 服务', 'OK', out.strip())
        result['service_status'] = 'active'
    else:
        print_status('memos-graph 服务', 'FAIL', err.strip() or 'not running')
        result['service_status'] = 'inactive'
        
        # 检查是否有进程在运行
        code, out, _ = run_command(['pgrep', '-f', 'memos-graph'])
        if code == 0:
            pids = out.strip().split('\n')
            print_status('memos-graph 进程', 'OK', f'PID: {", ".join(pids)} (但未注册 systemd)')
            result['process_exists'] = True
            result['pids'] = pids
        else:
            print_status('memos-graph 进程', 'FAIL', '未找到进程')
            result['process_exists'] = False
        return result
    
    # 服务详细信息
    code, out, _ = run_command(['systemctl', 'status', 'memos-graph', '--no-pager'])
    if code == 0:
        lines = out.strip().split('\n')
        for line in lines[:10]:  # 显示前 10 行
            print(f"  {line}")
    
    # HTTP 健康检查
    import urllib.request
    import urllib.error
    
    health_urls = [
        'http://127.0.0.1:8765/health',
        'http://localhost:8765/health',
        'http://127.0.0.1:8765/',
    ]
    
    for url in health_urls:
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                print_status(f'HTTP 健康检查 ({url})', 'OK', f'Status {response.status}')
                result['http_health'] = {'url': url, 'status': response.status}
                break
        except urllib.error.URLError as e:
            print_status(f'HTTP 健康检查 ({url})', 'FAIL', str(e.reason)[:50])
        except Exception as e:
            print_status(f'HTTP 健康检查 ({url})', 'FAIL', str(e)[:50])
    else:
        result['http_health'] = {'status': 'failed'}
    
    # 检查监听端口
    code, out, _ = run_command(['bash', '-c', 'ss -tlnp 2>/dev/null | grep 8765 || netstat -tlnp 2>/dev/null | grep 8765 || echo "port check failed"'])
    if '8765' in out:
        print_status('memos-graph 端口 8765', 'OK', '监听中')
        result['port_listening'] = True
    else:
        print_status('memos-graph 端口 8765', 'WARN', '未在监听')
        result['port_listening'] = False
    
    return result


def check_network_connectivity() -> Dict[str, Any]:
    """检查网络连通性"""
    print_header("网络连通性")
    result = {}
    
    # localhost 连通性
    code, out, _ = run_command(['ping', '-c', '1', '-W', '2', '127.0.0.1'])
    if code == 0:
        print_status('localhost (127.0.0.1)', 'OK')
        result['localhost'] = 'ok'
    else:
        print_status('localhost (127.0.0.1)', 'FAIL')
        result['localhost'] = 'failed'
    
    # DNS 解析
    code, out, _ = run_command(['getent', 'hosts', 'localhost'])
    if code == 0:
        print_status('DNS 解析 (localhost)', 'OK', out.strip().split()[0])
        result['dns_localhost'] = 'ok'
    else:
        print_status('DNS 解析 (localhost)', 'WARN', '无法解析')
        result['dns_localhost'] = 'failed'
    
    return result


def analyze_logs() -> Dict[str, Any]:
    """分析日志文件"""
    print_header("日志分析")
    result = {'errors': [], 'warnings': []}
    
    log_dir = Path.home() / '.memos-graph' / 'logs'
    if not log_dir.exists():
        print_status('日志目录', 'WARN', f'{log_dir} 不存在')
        result['log_dir_exists'] = False
        return result
    
    print_status('日志目录', 'OK', str(log_dir))
    result['log_dir_exists'] = True
    result['log_dir'] = str(log_dir)
    
    # 列出日志文件
    log_files = sorted(log_dir.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True)
    if not log_files:
        print("  未找到日志文件")
        result['log_files'] = []
        return result
    
    print(f"  找到 {len(log_files)} 个日志文件:")
    for lf in log_files[:5]:  # 显示最近 5 个
        size_kb = lf.stat().st_size / 1024
        print(f"    - {lf.name} ({size_kb:.1f} KB)")
    result['log_files'] = [str(f) for f in log_files[:5]]
    
    # 分析最新日志
    latest_log = log_files[0]
    try:
        with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        result['total_lines'] = len(lines)
        print(f"\n  最新日志：{latest_log.name} ({len(lines)} 行)")
        
        # 统计错误和警告
        errors = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l]
        warnings = [l for l in lines if 'WARNING' in l]
        
        result['error_count'] = len(errors)
        result['warning_count'] = len(warnings)
        
        print_status('错误数量', 'OK' if len(errors) == 0 else 'WARN', f'{len(errors)} 个')
        print_status('警告数量', 'OK' if len(warnings) == 0 else 'WARN', f'{len(warnings)} 个')
        
        # 显示最近错误
        if errors:
            print(f"\n  最近错误 (最后 5 个):")
            for err_line in errors[-5:]:
                print(f"    {Colors.RED}{err_line.strip()[:100]}{Colors.RESET}")
            result['recent_errors'] = [l.strip() for l in errors[-5:]]
        
        # 显示最近警告
        if warnings:
            print(f"\n  最近警告 (最后 5 个):")
            for warn_line in warnings[-5:]:
                print(f"    {Colors.YELLOW}{warn_line.strip()[:100]}{Colors.RESET}")
            result['recent_warnings'] = [l.strip() for l in warnings[-5:]]
        
    except Exception as e:
        print_status('日志读取', 'FAIL', str(e))
        result['log_read_error'] = str(e)
    
    # 检查 systemd 日志
    print("\n  systemd 日志 (最近 10 条):")
    code, out, _ = run_command(['journalctl', '-u', 'memos-graph', '-n', '10', '--no-pager'])
    if code == 0 and out.strip():
        for line in out.strip().split('\n')[:10]:
            print(f"    {line}")
        result['journalctl_available'] = True
    else:
        print("    无 systemd 日志或 journalctl 不可用")
        result['journalctl_available'] = False
    
    return result


def generate_report(results: Dict[str, Any], export: bool = False):
    """生成诊断报告"""
    print_header("诊断总结")
    
    # 计算总体状态
    issues = []
    
    if results.get('postgres', {}).get('service_status') != 'active':
        issues.append("PostgreSQL 服务未运行")
    
    if results.get('postgres', {}).get('connection') != 'ok':
        issues.append("PostgreSQL 连接失败")
    
    if results.get('memos_graph', {}).get('service_status') != 'active':
        issues.append("memos-graph 服务未运行")
    
    if results.get('memos_graph', {}).get('http_health', {}).get('status') == 'failed':
        issues.append("memos-graph HTTP 健康检查失败")
    
    if results.get('logs', {}).get('error_count', 0) > 0:
        issues.append(f"日志中存在 {results['logs']['error_count']} 个错误")
    
    if issues:
        print(f"\n{Colors.RED}⚠ 发现 {len(issues)} 个问题:{Colors.RESET}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print(f"\n{Colors.GREEN}✓ 所有检查通过，系统运行正常{Colors.RESET}")
    
    # 导出报告
    if export:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = Path(f'/tmp/memos-graph-diagnose-{timestamp}.json')
        report_file.write_text(json.dumps(results, indent=2, default=str))
        print(f"\n{Colors.CYAN}诊断报告已导出：{report_file}{Colors.RESET}")
        
        # 也生成文本版本
        text_file = Path(f'/tmp/memos-graph-diagnose-{timestamp}.txt')
        with open(text_file, 'w') as f:
            f.write(f"memos-graph 诊断报告\n")
            f.write(f"生成时间：{datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n\n")
            for section, data in results.items():
                f.write(f"\n[{section.upper()}]\n")
                f.write(json.dumps(data, indent=2, default=str))
                f.write('\n')
        print(f"{Colors.CYAN}文本报告：{text_file}{Colors.RESET}")


def main():
    parser = argparse.ArgumentParser(description='memos-graph 诊断工具')
    parser.add_argument('--quick', action='store_true', help='快速检查 (仅关键指标)')
    parser.add_argument('--service', action='store_true', help='仅检查服务状态')
    parser.add_argument('--postgres', action='store_true', help='仅检查 PostgreSQL')
    parser.add_argument('--logs', action='store_true', help='仅分析日志')
    parser.add_argument('--network', action='store_true', help='仅检查网络')
    parser.add_argument('--export', action='store_true', help='导出诊断报告')
    parser.add_argument('--all', action='store_true', help='执行所有检查 (默认)')
    
    args = parser.parse_args()
    
    # 如果没有指定任何选项，执行所有检查
    if not any([args.quick, args.service, args.postgres, args.logs, args.network, args.all]):
        args.all = True
    
    print(f"{Colors.BOLD}memos-graph 诊断工具 v1.0{Colors.RESET}")
    print(f"生成时间：{datetime.now().isoformat()}")
    
    results = {}
    
    if args.all or args.quick or args.service:
        results['system'] = check_system_resources()
        results['memos_graph'] = check_memos_graph_service()
    
    if args.all or args.quick or args.postgres:
        results['postgres'] = check_postgresql()
    
    if args.all or args.quick or args.network:
        results['network'] = check_network_connectivity()
    
    if args.all or args.quick or args.logs:
        results['logs'] = analyze_logs()
    
    generate_report(results, export=args.export)
    
    return 0 if not any([
        results.get('postgres', {}).get('service_status') != 'active',
        results.get('memos_graph', {}).get('service_status') != 'active',
    ]) else 1


if __name__ == '__main__':
    sys.exit(main())
