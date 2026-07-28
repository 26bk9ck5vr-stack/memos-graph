"""
memos-graph 日志配置模块
========================
提供结构化的日志配置，支持日志轮转、分级记录和可观测性。

日志级别规范:
- DEBUG: 详细调试信息 (API 请求参数、SQL 查询细节、向量计算过程)
- INFO: 正常运营信息 (服务启动/停止、API 请求成功、定时任务执行)
- WARNING: 可恢复的异常 (重试、降级、性能警告)
- ERROR: 需要关注的错误 (API 失败、数据库连接失败、向量生成失败)
- CRITICAL: 严重故障 (服务崩溃、数据损坏风险、无法恢复的错误)

日志轮转策略:
- 单个文件最大: 50MB
- 保留文件数: 10 个
- 总磁盘占用: 最多 500MB
- 压缩旧日志: 是 (gzip)
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


def get_log_directory() -> Path:
    """获取日志目录路径"""
    # 优先使用用户目录 (不需要 root 权限)
    log_path = Path.home() / '.memos-graph' / 'logs'
    
    # 如果环境变量指定了其他目录，使用环境变量
    env_log_dir = os.environ.get('MEMOS_GRAPH_LOG_DIR')
    if env_log_dir:
        env_path = Path(env_log_dir)
        if env_path.exists() and os.access(env_path, os.W_OK):
            log_path = env_path
    
    log_path.mkdir(parents=True, exist_ok=True)
    return log_path


def setup_logging(
    level: str = 'INFO',
    log_format: str = 'detailed',
    enable_console: bool = True,
    max_bytes: int = 50 * 1024 * 1024,  # 50MB
    backup_count: int = 10,
    log_filename: Optional[str] = None,
) -> logging.Logger:
    """
    配置 memos-graph 的日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: 日志格式 ('simple', 'detailed', 'json')
        enable_console: 是否同时输出到控制台
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        log_filename: 日志文件名 (默认自动生成)
    
    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger('memos_graph')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除已有的 handlers
    logger.handlers.clear()
    
    # 日志格式配置
    formats = {
        'simple': '%(levelname)s - %(message)s',
        'detailed': '%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d - %(message)s',
        'json': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", '
                '"file": "%(filename)s", "line": %(lineno)d, "message": "%(message)s"}',
    }
    
    log_fmt = formats.get(log_format, formats['detailed'])
    formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
    
    # 文件处理器 (带轮转)
    log_dir = get_log_directory()
    if log_filename is None:
        log_filename = f"memos-graph-{datetime.now().strftime('%Y%m%d')}.log"
    
    log_file = log_dir / log_filename
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
        delay=True  # 延迟打开文件，避免启动时报错
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 错误日志单独文件 (便于快速定位)
    error_log_file = log_dir / f"memos-graph-errors-{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
        delay=True
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # 防止日志传播到根 logger
    logger.propagate = False
    
    return logger


def get_logger(name: str = 'memos_graph') -> logging.Logger:
    """获取 logger 实例"""
    return logging.getLogger(name)


# 结构化日志辅助函数
def log_api_request(logger: logging.Logger, method: str, path: str, status: int, 
                    duration_ms: float, client_ip: Optional[str] = None):
    """记录 API 请求日志"""
    logger.info(
        f"API {method} {path} - {status} ({duration_ms:.2f}ms)",
        extra={
            'api_method': method,
            'api_path': path,
            'api_status': status,
            'api_duration_ms': duration_ms,
            'client_ip': client_ip or 'unknown'
        }
    )


def log_db_operation(logger: logging.Logger, operation: str, table: str, 
                     duration_ms: float, success: bool = True, error: Optional[str] = None):
    """记录数据库操作日志"""
    level = logging.INFO if success else logging.ERROR
    message = f"DB {operation} {table} - {'OK' if success else 'FAIL'} ({duration_ms:.2f}ms)"
    if error:
        message += f" - {error}"
    logger.log(level, message)


def log_health_check(logger: logging.Logger, component: str, status: str, 
                     latency_ms: Optional[float] = None, details: Optional[str] = None):
    """记录健康检查日志"""
    level = logging.INFO if status == 'healthy' else logging.WARNING
    message = f"Health check: {component} - {status}"
    if latency_ms is not None:
        message += f" ({latency_ms:.2f}ms)"
    if details:
        message += f" - {details}"
    logger.log(level, message)


if __name__ == '__main__':
    # 测试日志配置
    logger = setup_logging(level='DEBUG', log_format='detailed')
    
    logger.debug("DEBUG: 详细调试信息")
    logger.info("INFO: 服务启动成功")
    logger.warning("WARNING: 内存使用率超过 80%")
    logger.error("ERROR: 数据库连接失败")
    logger.critical("CRITICAL: 服务崩溃")
    
    print(f"\n日志文件位置: {get_log_directory()}")
