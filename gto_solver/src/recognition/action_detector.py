"""
行动触发检测 — 模板匹配"弃牌/跟注/加注"按钮判断是否轮到自己。

方案:
- 当前没有 WePoker 按钮模板 → 用颜色检测兜底
- 红色/绿色/蓝色按钮分别对应 Fold/Call/Raise
- 在 Hero 操作区域 (config.json 中配置) 做颜色直方图检测
- 后续收集按钮模板后可切换到精确模板匹配

用法:
    detector = ActionTrigger(config)
    if detector.is_hero_turn(frame):
        ...
"""

from __future__ import annotations

import cv2
import numpy as np


class ActionTrigger:
    """检测是否轮到自己行动（弃牌/跟注/加注按钮可见）。"""

    # WePoker 按钮颜色 HSV 范围（经验值）
    FOLD_RED_LOWER1 = (0, 80, 80)
    FOLD_RED_UPPER1 = (10, 255, 255)
    FOLD_RED_LOWER2 = (160, 80, 80)
    FOLD_RED_UPPER2 = (180, 255, 255)

    CALL_GREEN_LOWER = (35, 50, 50)
    CALL_GREEN_UPPER = (85, 255, 255)

    RAISE_BLUE_LOWER = (95, 50, 50)
    RAISE_BLUE_UPPER = (130, 255, 255)

    # 按钮区域占截图的比例阈值（按钮区域 > 3% 像素即认为存在）
    BUTTON_PIXEL_RATIO = 0.015

    def __init__(
        self,
        action_roi: tuple[int, int, int, int] | None = None,
        use_color: bool = True,
    ):
        """
        Args:
            action_roi: (x, y, w, h) 操作按钮区域。None 则用默认 Hero 操作区。
            use_color: 是否启用颜色检测（没有模板时的兜底方案）。
        """
        self.use_color = use_color
        self._default_roi = action_roi

    def _get_action_roi(self, frame: np.ndarray) -> tuple[int, int, int, int] | None:
        """获取操作按钮区域。默认从 config 读取，回退到全屏底部 1/4。"""
        if self._default_roi:
            return self._default_roi

        try:
            from utils.config import get
            roi = get("hero_action_roi")
            if roi:
                return tuple(roi)
        except Exception:
            pass

        # 回退: 底部 1/4 中央 60%
        h, w = frame.shape[:2]
        return (int(w * 0.2), int(h * 0.75), int(w * 0.6), int(h * 0.20))

    def is_hero_turn(self, frame: np.ndarray) -> bool:
        """
        判断是否轮到自己。

        Args:
            frame: BGR 截图。

        Returns:
            True 如果检测到操作按钮可见。
        """
        if not self.use_color:
            return False

        roi_rect = self._get_action_roi(frame)
        if roi_rect is None:
            return False

        x, y, w, h = roi_rect
        if y + h > frame.shape[0] or x + w > frame.shape[1]:
            return False

        roi = frame[y:y + h, x:x + w]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        total = roi.shape[0] * roi.shape[1]

        # 红色 (Fold)
        red_mask = cv2.inRange(hsv, self.FOLD_RED_LOWER1, self.FOLD_RED_UPPER1)
        red_mask |= cv2.inRange(hsv, self.FOLD_RED_LOWER2, self.FOLD_RED_UPPER2)
        red_ratio = np.sum(red_mask > 0) / total

        # 绿色 (Call)
        green_mask = cv2.inRange(hsv, self.CALL_GREEN_LOWER, self.CALL_GREEN_UPPER)
        green_ratio = np.sum(green_mask > 0) / total

        # 蓝色 (Raise)
        blue_mask = cv2.inRange(hsv, self.RAISE_BLUE_LOWER, self.RAISE_BLUE_UPPER)
        blue_ratio = np.sum(blue_mask > 0) / total

        # 至少两个按钮颜色区域 > 阈值 → 轮到自己
        triggers = sum(
            r > self.BUTTON_PIXEL_RATIO
            for r in (red_ratio, green_ratio, blue_ratio)
        )
        return triggers >= 2
