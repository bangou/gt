"""
roi_manager.py - ROI 区域管理

负责：
  1. 加载 ROI 配置
  2. 根据窗口位置映射到实际屏幕坐标
  3. 截图裁剪到指定区域
"""

import logging
from typing import Optional

import cv2
import numpy as np

from src.roi.roi_config import (
    ROI_CONFIG,
    resolve_roi,
    get_seat_rect,
    get_all_seat_rects,
)

logger = logging.getLogger(__name__)


class ROIManager:
    """
    ROI 管理器：将截图按配置区域裁剪。

    用法：
        roi_mgr = ROIManager()
        # 截取某个座位的图像
        seat_img = roi_mgr.crop_seat(screenshot, 3)
        # 截取公共牌
        board_img = roi_mgr.crop_community(screenshot)
        # 截取底池金额
        pot_img = roi_mgr.crop_pot(screenshot)
    """

    def __init__(self, window_offset: tuple = (0, 0)):
        """
        Args:
            window_offset: 窗口在屏幕上的偏移 (offset_x, offset_y)
                           用于将 ROI 相对坐标映射到屏幕绝对坐标
        """
        self.offset_x, self.offset_y = window_offset

    def _apply_offset(self, rect: tuple) -> tuple:
        """将相对坐标转换为屏幕绝对坐标"""
        x, y, w, h = rect
        return (x + self.offset_x, y + self.offset_y, w, h)

    def crop(self, image: np.ndarray, rect: tuple) -> np.ndarray:
        """
        从图像中裁剪指定区域

        Args:
            image: 全屏截图（numpy 数组）
            rect: (x, y, width, height)

        Returns:
            裁剪后的图像
        """
        x, y, w, h = rect
        # 确保不越界
        img_h, img_w = image.shape[:2]
        x = max(0, min(x, img_w - 1))
        y = max(0, min(y, img_h - 1))
        w = min(w, img_w - x)
        h = min(h, img_h - y)
        return image[y : y + h, x : x + w]

    # ── 座位裁剪 ──

    def crop_seat(self, image: np.ndarray, seat_index: int) -> np.ndarray:
        """裁剪指定座位的区域"""
        return self.crop(image, get_seat_rect(seat_index))

    def crop_all_seats(self, image: np.ndarray) -> dict:
        """裁剪所有座位，返回 {seat_index: cropped_image}"""
        return {idx: self.crop_seat(image, idx) for idx in range(6)}

    # ── 中央区域裁剪 ──

    def crop_community_cards(self, image: np.ndarray) -> np.ndarray:
        """裁剪公共牌区域"""
        return self.crop(image, resolve_roi("community_cards"))

    def crop_pot(self, image: np.ndarray) -> np.ndarray:
        """裁剪底池金额区域"""
        return self.crop(image, resolve_roi("pot"))

    def crop_game_info(self, image: np.ndarray) -> np.ndarray:
        """裁剪游戏信息区域"""
        return self.crop(image, resolve_roi("game_info"))

    # ── Hero 区域 ──

    def crop_hero_cards(self, image: np.ndarray) -> np.ndarray:
        """裁剪你的手牌区域"""
        return self.crop(image, resolve_roi("hero", "cards"))

    def crop_hero_actions(self, image: np.ndarray) -> np.ndarray:
        """裁剪操作按钮区域"""
        return self.crop(image, resolve_roi("hero", "actions"))

    def crop_hero_stack(self, image: np.ndarray) -> np.ndarray:
        """裁剪 Hero 筹码区域"""
        return self.crop(image, resolve_roi("hero", "stack"))

    # ── 调试工具 ──

    def draw_all_rois(self, image: np.ndarray) -> np.ndarray:
        """在图像上绘制所有 ROI 框（调试用）"""
        vis = image.copy()

        # 座位
        for idx, rect in get_all_seat_rects().items():
            x, y, w, h = rect
            color = (0, 255, 0)
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
            cv2.putText(vis, f"Seat {idx}", (x + 2, y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # 中央区域
        for key in ["community_cards", "pot", "game_info"]:
            x, y, w, h = resolve_roi(key)
            cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(vis, key, (x + 2, y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

        # Hero 区域
        for sub_key in ["cards", "actions", "stack"]:
            x, y, w, h = resolve_roi("hero", sub_key)
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(vis, f"hero_{sub_key}", (x + 2, y + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        return vis

    def save_roi_visualization(self, image: np.ndarray, output_path: str):
        """保存 ROI 可视化标注图"""
        vis = self.draw_all_rois(image)
        cv2.imwrite(output_path, vis)
        logger.info(f"ROI 可视化已保存: {output_path}")
