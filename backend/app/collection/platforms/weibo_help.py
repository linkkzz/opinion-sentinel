# -*- coding: utf-8 -*-
"""微博搜索结果卡片过滤。"""

from __future__ import annotations

from typing import Dict, List

def filter_search_result_card(card_list: List[Dict]) -> List[Dict]:
    """只保留 card_type==9 的微博正文卡片（含 card_group 内嵌套）。"""
    note_list: List[Dict] = []
    for card_item in card_list or []:
        if card_item.get("card_type") == 9:
            note_list.append(card_item)
        card_group = card_item.get("card_group") or []
        for sub in card_group:
            if sub.get("card_type") == 9:
                note_list.append(sub)
    return note_list
