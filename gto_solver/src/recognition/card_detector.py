"""
card_detector.py - 牌面自动检测与提取

工作原理：
  1. 截取全屏
  2. 在牌桌区域（y=0.35~0.9 的屏幕范围）扫描
  3. 找白色/浅色矩形（宽高比接近扑克牌 0.55~0.75）
  4. 按位置分组（Hero区 vs 公共牌区 vs 对手区）
  5. 提取每张牌的图片（用于后续 OCR 或模板匹配）

用法：
    detector = CardDetector()
    cards = detector.detect(screenshot)
    for card in cards:
        print(card.region, card.image)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DetectedCard:
    """检测到的一张牌"""
    x: int
    y: int
    width: int
    height: int
    area: float
    image: np.ndarray  # 裁剪图（RGB）
    location: str = "unknown"  # hero / community / opponent

    @property
    def center(self) -> tuple:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def __repr__(self):
        return f"DetectedCard(pos=({self.x},{self.y}), size={self.width}x{self.height}, loc={self.location})"


class CardDetector:
    """
    扑克牌自动检测器。

    在截图中扫描，找到所有牌形的白色矩形对象。
    不依赖硬编码坐标——2人桌、6人桌都能工作。
    """

    # 扑克牌特征参数
    MIN_CARD_AREA = 300    # 最小面积（像素²）
    MAX_CARD_AREA = 15000  # 最大面积
    MIN_CARD_W = 18        # 最小宽度
    MIN_CARD_H = 25        # 最小高度
    CARD_ASPECT_MIN = 0.40  # 宽高比下限（W/H）
    CARD_ASPECT_MAX = 0.90  # 宽高比上限

    # 牌桌搜索范围（占屏幕高度的比例）
    TABLE_TOP_RATIO = 0.05
    TABLE_BOTTOM_RATIO = 0.85

    def __init__(self):
        self._last_cards = []

    def detect(self, screenshot: np.ndarray) -> list[DetectedCard]:
        """
        在截图中检测所有牌。

        Args:
            screenshot: BGR 截图 (H, W, 3)

        Returns:
            检测到的牌列表
        """
        h, w = screenshot.shape[:2]
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        # 搜索范围：牌桌区域
        search_top = int(h * self.TABLE_TOP_RATIO)
        search_bottom = int(h * self.TABLE_BOTTOM_RATIO)

        cards = []

        # 多阈值扫描（牌面亮度不同牌面差异大）
        for threshold in [200, 180, 160, 140]:
            cards_in_threshold = self._scan_by_threshold(
                gray, screenshot, search_top, search_bottom, threshold
            )
            # 去重合并
            for card in cards_in_threshold:
                if not self._is_duplicate(card, cards):
                    cards.append(card)

        # 排序：从上到下，从左到右
        cards.sort(key=lambda c: (c.y, c.x))

        self._last_cards = cards
        logger.info(f"检测到 {len(cards)} 张牌")

        return cards

    def _scan_by_threshold(
        self,
        gray: np.ndarray,
        color: np.ndarray,
        search_top: int,
        search_bottom: int,
        threshold: int,
    ) -> list[DetectedCard]:
        """用单个亮度阈值扫描"""
        h, w = gray.shape[:2]

        # 搜索区域
        search_region = gray[search_top:search_bottom, :]
        _, binary = cv2.threshold(search_region, threshold, 255, cv2.THRESH_BINARY)

        # 去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cards = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.MIN_CARD_AREA or area > self.MAX_CARD_AREA:
                continue

            x, y_offset, cw, ch = cv2.boundingRect(c)
            if cw < self.MIN_CARD_W or ch < self.MIN_CARD_H:
                continue

            aspect = cw / max(ch, 1)
            if aspect < self.CARD_ASPECT_MIN or aspect > self.CARD_ASPECT_MAX:
                continue

            y = y_offset + search_top

            # 验证：牌内部应该有内容（不是纯白色）
            card_roi = gray[y : y + ch, x : x + cw]
            inner_std = np.std(card_roi)
            if inner_std < 15:
                continue  # 太均匀，可能是空白区

            cropped = color[y : y + ch, x : x + cw].copy()
            cards.append(
                DetectedCard(
                    x=int(x),
                    y=int(y),
                    width=int(cw),
                    height=int(ch),
                    area=float(area),
                    image=cropped,
                )
            )

        return cards

    def _is_duplicate(self, card: DetectedCard, existing: list[DetectedCard]) -> bool:
        """检查是否与已有牌重叠（去重）"""
        for ex in existing:
            # 矩形交叠比例
            x_overlap = max(
                0,
                min(card.x + card.width, ex.x + ex.width)
                - max(card.x, ex.x),
            )
            y_overlap = max(
                0,
                min(card.y + card.height, ex.y + ex.height)
                - max(card.y, ex.y),
            )
            if x_overlap > 0 and y_overlap > 0:
                overlap_area = x_overlap * y_overlap
                card_area = card.width * card.height
                if overlap_area > card_area * 0.5:
                    return True
        return False

    def classify_by_location(self, cards: list[DetectedCard]) -> dict:
        """
        将检测到的牌按位置分类：
          - hero: 底部中央（你自己的手牌）
          - community: 中央偏上（公共牌）
          - opponent_N: 其他位置（对手的牌）

        Returns:
            {"hero": [...], "community": [...], "opponent": [...]}
        """
        if not cards:
            return {"hero": [], "community": [], "opponent": []}

        y_vals = [c.y for c in cards]
        y_median = np.median(y_vals)
        x_vals = [c.x for c in cards]
        x_median = np.median(x_vals)

        result = {"hero": [], "community": [], "opponent": []}

        for card in cards:
            cy = card.y + card.height // 2
            cx = card.x + card.width // 2

            # 规则：
            # - 最 下 方 → Hero 区
            # - 中间偏上 → 公共牌区
            # - 左右两侧 → 对手区

            if cy > y_median + 20 or (cy > y_median and abs(cx - x_median) < 200):
                result["hero"].append(card)
                card.location = "hero"
            elif cy < y_median - 20:
                result["community"].append(card)
                card.location = "community"
            else:
                result["opponent"].append(card)
                card.location = "opponent"

        return result

    def save_debug_image(self, screenshot: np.ndarray, cards: list[DetectedCard], path: str):
        """保存调试用的标注图"""
        vis = screenshot.copy()
        colors = {
            "hero": (0, 255, 0),        # 绿
            "community": (255, 0, 255),  # 紫
            "opponent": (255, 255, 0),   # 青
            "unknown": (0, 0, 255),      # 红
        }

        for card in cards:
            color = colors.get(card.location, colors["unknown"])
            cv2.rectangle(vis, (card.x, card.y),
                          (card.x + card.width, card.y + card.height), color, 2)
            label = f"{card.location[:4]}"
            cv2.putText(vis, label, (card.x, card.y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        cv2.imwrite(path, vis)
        logger.info(f"调试图已保存: {path}")


# ── 快速测试 ──

def test_with_current_screen():
    """用当前屏幕测试牌检测"""
    from src.capture.screen_capture import ScreenCapture

    cap = ScreenCapture()
    screenshot = cap.capture_monitor(1)

    detector = CardDetector()
    cards = detector.detect(screenshot)

    print(f"\n检测到 {len(cards)} 张牌:")
    for card in cards:
        print(f"  {card}")

    classified = detector.classify_by_location(cards)
    print(f"\n分类结果:")
    for loc, card_list in classified.items():
        print(f"  {loc}: {len(card_list)} 张")

    detector.save_debug_image(screenshot, cards, "tests/output/card_detection_debug.png")
    print(f"\n调试图已保存: tests/output/card_detection_debug.png")

    return cards


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s:%(name)s:%(message)s")
    test_with_current_screen()
