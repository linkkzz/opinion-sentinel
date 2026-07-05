from app.collection.adapters.base import CollectionAdapter, RawCollectedItem
from app.collection.adapters.bilibili import BilibiliAdapter
from app.collection.adapters.kuaishou import KuaishouAdapter
from app.collection.adapters.weibo import WeiboAdapter


def get_adapter(platform: str) -> CollectionAdapter:
    adapters: dict[str, CollectionAdapter] = {
        "微博": WeiboAdapter(),
        "快手": KuaishouAdapter(),
        "bilibili": BilibiliAdapter(),
    }
    if platform not in adapters:
        raise ValueError(f"{platform}暂未支持持续监测")
    return adapters[platform]


__all__ = ["CollectionAdapter", "RawCollectedItem", "get_adapter"]
