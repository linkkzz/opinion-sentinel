# -*- coding: utf-8 -*-
"""微博搜索类型枚举。"""

from __future__ import annotations

from enum import Enum

class SearchType(Enum):
    DEFAULT = "1"       # 综合
    REAL_TIME = "61"    # 实时
    POPULAR = "60"      # 热门
    VIDEO = "64"        # 视频
