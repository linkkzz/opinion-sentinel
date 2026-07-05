# -*- coding: utf-8 -*-
# 基于 MediaCrawler 二开的 bilibili WBI 签名工具。
#
# 原始项目：https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/bilibili/help.py
# 原始版权：Copyright (c) 2025 relakkes@gmail.com
# 许可：NON-COMMERCIAL LEARNING LICENSE 1.1（仅供学习研究，禁止商用）。
#
# 二开改动：去除 model/tools 依赖，get_unix_timestamp 改为本地实现。
"""bilibili WBI 签名算法。纯 Python，无浏览器依赖。

参考：https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html
"""
from __future__ import annotations

import time
import urllib.parse
from hashlib import md5
from typing import Dict


def get_unix_timestamp() -> int:
    return int(time.time())


class BilibiliSign:
    """bilibili WBI 参数签名。

    算法：img_key + sub_key 经 64 项固定 map_table 重排取前 32 位得 salt →
    params 加 wts 时间戳 → 排序 → 过滤 !'()* → urlencode + salt 取 md5 = w_rid。
    """

    def __init__(self, img_key: str, sub_key: str):
        self.img_key = img_key
        self.sub_key = sub_key
        self.map_table = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
            33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
            61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
            36, 20, 34, 44, 52,
        ]

    def get_salt(self) -> str:
        """img_key + sub_key 经 map_table 重排取前 32 位。"""
        salt = ""
        mixin_key = self.img_key + self.sub_key
        for mt in self.map_table:
            salt += mixin_key[mt]
        return salt[:32]

    def sign(self, req_data: Dict) -> Dict:
        """对 params 签名，返回含 wts + w_rid 的 dict。"""
        req_data.update({"wts": get_unix_timestamp()})
        req_data = dict(sorted(req_data.items()))
        req_data = {
            k: "".join(filter(lambda ch: ch not in "!'()*", str(v)))
            for k, v in req_data.items()
        }
        query = urllib.parse.urlencode(req_data)
        salt = self.get_salt()
        req_data["w_rid"] = md5((query + salt).encode()).hexdigest()
        return req_data
