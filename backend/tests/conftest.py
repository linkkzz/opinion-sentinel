# -*- coding: utf-8 -*-
"""pytest 全局配置：确保所有测试使用 sqlite，避免 .env 的空 DATABASE_URL 触发 MySQL。

必须在任何 app.* 导入之前设置 env var，因此放在 conftest.py 顶层。
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_opinion_sentinel.db")
os.environ.setdefault("STORAGE_ROOT", "./test_storage")
