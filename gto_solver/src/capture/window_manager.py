"""
window_manager.py - 窗口查找与定位

功能：
  1. 列出所有可见窗口
  2. 按窗口标题关键词搜索目标窗口（如 "WePoker"）
  3. 获取窗口位置和大小（用于后续 ROI 切割）
"""

import logging
from typing import Optional

try:
    import pygetwindow as gw
except ImportError:
    gw = None  # 未安装时降级

logger = logging.getLogger(__name__)


class WindowInfo:
    """窗口信息：位置、大小、标题"""

    def __init__(self, title: str, left: int, top: int, width: int, height: int):
        self.title = title
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    @property
    def rect(self) -> dict:
        """返回 (left, top, width, height) 字典，兼容 mss 截图参数"""
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    @property
    def center(self) -> tuple:
        """窗口中心坐标"""
        return (self.left + self.width // 2, self.top + self.height // 2)

    def __repr__(self):
        return f"WindowInfo(title='{self.title}', pos=({self.left},{self.top}), size={self.width}x{self.height})"


def list_windows() -> list[WindowInfo]:
    """列出所有可见窗口"""
    if gw is None:
        logger.warning("pygetwindow 未安装，无法列出窗口")
        return []

    windows = []
    try:
        for w in gw.getWindowsWithTitle(""):
            if w.visible and w.width > 0 and w.height > 0:
                windows.append(WindowInfo(w.title, w.left, w.top, w.width, w.height))
    except Exception as e:
        logger.error(f"列出窗口失败: {e}")

    return windows


def find_window(keyword: str) -> Optional[WindowInfo]:
    """
    按标题关键词查找窗口（不区分大小写）

    Args:
        keyword: 窗口标题关键词，如 "WePoker"、"Chrome"、"Poker"

    Returns:
        找到的第一个匹配窗口，未找到返回 None
    """
    if gw is None:
        logger.warning("pygetwindow 未安装，无法查找窗口")
        return None

    try:
        all_windows = gw.getWindowsWithTitle("")
        for w in all_windows:
            if w.visible and w.width > 0 and w.height > 0:
                if keyword.lower() in w.title.lower():
                    logger.info(f"找到目标窗口: '{w.title}'")
                    return WindowInfo(w.title, w.left, w.top, w.width, w.height)
    except Exception as e:
        logger.error(f"查找窗口失败: {e}")

    logger.warning(f"未找到标题包含 '{keyword}' 的可见窗口")
    return None


def find_window_enhanced(keywords: list[str]) -> Optional[WindowInfo]:
    """
    按多个关键词查找窗口（AND 逻辑，全部匹配才算）

    Args:
        keywords: 关键词列表，如 ["WePoker", "Chrome"]

    Returns:
        匹配的窗口，未找到返回 None
    """
    if gw is None:
        return None

    try:
        all_windows = gw.getWindowsWithTitle("")
        for w in all_windows:
            if w.visible and w.width > 0 and w.height > 0:
                title_lower = w.title.lower()
                if all(kw.lower() in title_lower for kw in keywords):
                    return WindowInfo(w.title, w.left, w.top, w.width, w.height)
    except Exception as e:
        logger.error(f"增强查找失败: {e}")

    return None


def get_active_window() -> Optional[WindowInfo]:
    """获取当前活动窗口"""
    if gw is None:
        return None

    try:
        w = gw.getActiveWindow()
        if w and w.visible and w.width > 0 and w.height > 0:
            return WindowInfo(w.title, w.left, w.top, w.width, w.height)
    except Exception as e:
        logger.error(f"获取活动窗口失败: {e}")

    return None
