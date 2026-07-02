"""memos-graph storage layer — v0.1.0-docs 占位。

TASK_BREAKDOWN T1 + T5 负责 storage 操作。
v0.1 阶段不暴露独立 storage 接口（直接走 db/session.py）。
"""

from __future__ import annotations


class StorageError(Exception):
    """Storage 基类异常。"""


# v0.1 占位：所有 chunk/vector/state 读写都走 db.session.get_session()
# 不暴露独立的 storage.* 类（设计选择 — 见 ARCHITECTURE §2.1）
