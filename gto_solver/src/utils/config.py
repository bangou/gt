"""
配置管理 — 读取/写入 config.json。

字段:
    window_title: 要查找的窗口标题关键词（默认 "WePoker"）。
    hero_seat: 用户在桌上的座位号（0-5，默认 3 = BTN）。
    template_threshold: 模板匹配最低分数（默认 0.65）。
    reference_width / reference_height: 基准分辨率（默认 1920x1080）。
    hero_card_boxes: Hero 手牌区域 [(x,y,w,h), ...]。
    community_search_roi: 公共牌搜索区域 (x,y,w,h)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"

DEFAULTS: dict[str, Any] = {
    "window_title": "WePoker",
    "hero_seat": 3,
    "template_threshold": 0.65,
    "reference_width": 1920,
    "reference_height": 1080,
    "hero_card_boxes": [
        [908, 873, 50, 73],
        [963, 873, 50, 73],
    ],
    "community_search_roi": [800, 465, 300, 50],
    "poll_interval_ms": 200,
}


def _load() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    # 合并默认值
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def _save(data: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get(key: str) -> Any:
    """读取单个配置项。"""
    return _load()[key]


def set(key: str, value: Any) -> None:
    """设置并持久化单个配置项。"""
    data = _load()
    data[key] = value
    _save(data)


def get_all() -> dict:
    """读取全部配置。"""
    return _load()


def reset() -> None:
    """重置为默认值。"""
    _save(dict(DEFAULTS))
