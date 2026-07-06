"""
数字识别 — 对固定区域的数字，使用模板匹配（0-9 + 小数点）+ 手动输入兜底。

当前阶段:
- 没有数字模板 → 用简易轮廓分析作为折中方案
- 后续收集 0-9 模板后可切换到精确模板匹配
- 手动输入始终作为最终回退

用法:
    reader = NumberReader()
    value = reader.read(roi_image)  # 返回 float 或 None
"""

from __future__ import annotations

import cv2
import numpy as np


class NumberReader:
    """扑克桌面数字识别器（底池/下注金额）。"""

    DIGIT_CONTOUR_MIN_AREA = 50
    DIGIT_CONTOUR_MAX_AREA = 800
    DIGIT_ASPECT_MIN = 0.3
    DIGIT_ASPECT_MAX = 1.2

    def __init__(self, digit_templates_dir: str = "templates/digits"):
        self._templates: dict[str, np.ndarray] = {}
        self._templates_dir = digit_templates_dir
        # 预加载模板（如果存在）
        self._load_templates()

    def _load_templates(self) -> None:
        from pathlib import Path
        tp = Path(self._templates_dir)
        if not tp.exists():
            return
        for digit_file in sorted(tp.glob("*.png")):
            digit_name = digit_file.stem  # "0", "1", ..., "9", "dot"
            img = cv2.imread(str(digit_file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._templates[digit_name] = img

    # ── 模板匹配（模板存在时）──────────────────────────────────────

    def _match_templates(self, roi_gray: np.ndarray) -> float | None:
        """
        用 0-9 + dot 模板在 ROI 中从左到右匹配，组装数字。
        """
        if not self._templates:
            return None

        # 从左到右滑窗，找每个数字
        found_digits: list[tuple[int, str, float]] = []  # (x, digit, score)

        for name, tmpl in self._templates.items():
            if tmpl.shape[0] > roi_gray.shape[0] or tmpl.shape[1] > roi_gray.shape[1]:
                continue
            result = cv2.matchTemplate(roi_gray, tmpl, cv2.TM_CCOEFF_NORMED)
            locs = np.where(result > 0.70)
            for px, py in zip(locs[1], locs[0]):
                score = float(result[py, px])
                # 去重：10px 内同数字只保留最高分
                if not any(abs(px - fx) < 10 and fname == name for fx, fname, _ in found_digits):
                    found_digits.append((px, name, score))

        if not found_digits:
            return None

        # 按 x 排序，组装
        found_digits.sort(key=lambda d: d[0])
        digits_str = "".join(
            "." if d[1] == "dot" else d[1]
            for d in found_digits
        )

        try:
            return float(digits_str)
        except ValueError:
            return None

    # ── 轮廓分析回退（无模板时）────────────────────────────────────

    def _contour_read(self, roi_bgr: np.ndarray) -> float | None:
        """
        用轮廓分析识别数字。
        假设白色数字在深色背景上，找到数字形状的轮廓。
        """
        h, w = roi_bgr.shape[:2]
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        # OTSU 二值化（反转：数字为白色前景）
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 确定前景更暗还是更亮
        if np.mean(gray[binary > 0]) > np.mean(gray[binary == 0]):
            binary = cv2.bitwise_not(binary)

        # 去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        digit_contours = []
        for c in contours:
            area = cv2.contourArea(c)
            rx, ry, rw, rh = cv2.boundingRect(c)
            aspect = rw / max(rh, 1)
            if (
                self.DIGIT_CONTOUR_MIN_AREA < area < self.DIGIT_CONTOUR_MAX_AREA
                and self.DIGIT_ASPECT_MIN < aspect < self.DIGIT_ASPECT_MAX
                and rh > h * 0.3  # 至少占 ROI 高度的 30%
            ):
                digit_contours.append((rx, c))

        # 按 x 排，数轮廓数
        digit_contours.sort(key=lambda d: d[0])
        # 简单启发式：轮廓数 = 数字位数（含小数点）
        if not digit_contours:
            return None

        count = len(digit_contours)
        # 返回值仅仅是轮廓数，不是真正的数字识别
        # 轮廓分析只能确定"存在数字"，不能精确识别
        return None  # 轮廓不精确，返回 None 让手动输入接管

    # ── 公共入口 ───────────────────────────────────────────────────

    def read(self, roi_bgr: np.ndarray) -> float | None:
        """
        从数字 ROI 图像中读取数值。

        Args:
            roi_bgr: 包含数字的 BGR 裁剪图。

        Returns:
            识别出的数值（float），None 表示需要手动输入。
        """
        if roi_bgr.size == 0:
            return None

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        # 方法 1: 模板匹配（优先，模板存在时）
        result = self._match_templates(gray)
        if result is not None:
            return result

        # 方法 2: 轮廓分析（不精确，返回 None 触发手动输入）
        # result = self._contour_read(roi_bgr)
        # if result is not None:
        #     return result

        return None  # 需要手动输入

    @staticmethod
    def manual_input(prompt: str = "请输入数值") -> float | None:
        """
        手动输入回退。

        Args:
            prompt: 提示文字。

        Returns:
            用户输入的数值，取消返回 None。
        """
        try:
            value = input(f"{prompt}: ")
            return float(value)
        except (ValueError, EOFError):
            return None
