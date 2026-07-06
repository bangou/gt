"""
seat_detector.py - 智能座位检测

工作原理：
  1. 对每个座位区域截图
  2. 判断该区域是否存在"+"号（空位）或头像/名字（有人）
  3. 结合庄位附近的手牌判断牌局中活跃人数

  这样就不需要硬编码 6 人桌了——桌面有几人就识别几人。
"""

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class SeatDetector:
    """
    座位检测器：识别每个座位是否有人

    用法：
        detector = SeatDetector()
        # 传入 ROI 裁剪好的 6 个座位图像
        results = detector.detect_all(seat_images_dict)
        # results = {0: True, 1: False, 2: True, ...}  True=有人
    """

    def __init__(self):
        # "+" 号模板（会在运行时从第一个"空位"自动学习）
        self._plus_template = None

    def detect_seat(self, seat_img: np.ndarray) -> dict:
        """
        检测单个座位是否有人

        Returns:
            {
                "occupied": bool,   # True=有人, False=空位
                "method": str,      # 判断依据: "avatar" / "plus_sign" / "name" / "unknown"
                "confidence": float, # 0-1
            }
        """
        h, w = seat_img.shape[:2]
        if h < 10 or w < 10:
            return {"occupied": False, "method": "too_small", "confidence": 0.0}

        gray = cv2.cvtColor(seat_img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(seat_img, cv2.COLOR_BGR2HSV)

        # ── 方法1：检测 "+" 号（空位标志） ──
        # "+" 通常是白色/亮色，在深色背景上
        _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # 找白色轮廓
        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        has_plus = False
        for c in contours:
            area = cv2.contourArea(c)
            x, y, cw, ch = cv2.boundingRect(c)
            if area < 10 or area > 500:
                continue
            # "+" 的轮廓接近正方形，且中心区域是白色
            aspect = cw / max(ch, 1)
            if 0.3 < aspect < 3.0:
                # 检查是否像 "+" 形状（水平和垂直线的交叉）
                roi_center = bright[y:y+ch, x:x+cw]
                white_ratio = np.sum(roi_center > 0) / (cw * ch)
                if white_ratio > 0.2:
                    has_plus = True
                    break

        if has_plus:
            return {"occupied": False, "method": "plus_sign", "confidence": 0.8}

        # ── 方法2：检测头像特征（圆形+肤色） ──
        # 皮肤色在 HSV 中范围（亚洲人肤色）
        skin_mask = cv2.inRange(hsv, (0, 15, 40), (30, 150, 230))
        skin_ratio = np.sum(skin_mask > 0) / (h * w)

        # 检测圆形轮廓（头像）
        blur = cv2.GaussianBlur(gray, (5, 5), 1)
        circles = cv2.HoughCircles(
            blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
            param1=40, param2=15, minRadius=8, maxRadius=40
        )
        has_face_circle = circles is not None and len(circles[0]) > 0

        # ── 方法3：检测名字文字区域 ──
        # 有人坐的座位通常有玩家名字（水平排列的文字）
        edges = cv2.Canny(gray, 40, 120)
        # 水平投影：找连续多行都有边缘的行
        row_edges = np.sum(edges > 0, axis=1) > w * 0.08
        # 找连续的文字块
        text_rows = 0
        in_text = False
        for re in row_edges:
            if re and not in_text:
                in_text = True
                text_rows += 1
            elif not re:
                in_text = False
        has_text = text_rows > 2

        # ── 方法4：检测非加号的高对比度（玩家头像+名字综合） ──
        local_std = cv2.Laplacian(gray, cv2.CV_64F).var()
        # 座位的平均亮度（头像+名字区域通常在中间亮度）
        mean_bright = np.mean(gray)

        # 综合判断（加权投票）
        occupied = False
        method = "unknown"
        confidence = 0.0
        votes = 0

        # 投票：头像/肤色
        if skin_ratio > 0.03:
            votes += 1
        if has_face_circle:
            votes += 2  # 圆形脸是强证据
        if has_text:
            votes += 1
        # 如果高对比度但确定不是加号
        if local_std > 80 and not has_plus:
            votes += 1

        if votes >= 3:
            occupied = True
            method = "avatar+name"
            confidence = 0.85
        elif votes >= 2:
            occupied = True
            method = "partial_evidence"
            confidence = 0.65
        elif votes == 0 and not has_plus:
            # 既无加号也无头像证据 — 不确定，保守判断为无人
            pass

        return {"occupied": occupied, "method": method, "confidence": confidence}

    def detect_all(self, seat_images: dict) -> dict:
        """
        检测所有座位

        Args:
            seat_images: {seat_index: cropped_image}

        Returns:
            {
                0: {"occupied": True, "method": "skin_tone", "confidence": 0.85},
                1: {"occupied": False, "method": "plus_sign", "confidence": 0.8},
                ...
            }
        """
        results = {}
        for idx, img in seat_images.items():
            results[idx] = self.detect_seat(img)
        return results

    def get_active_players(self, seat_results: dict) -> list:
        """
        从检测结果中获取活跃玩家列表

        Returns:
            [seat_index, ...] 例如 [0, 1, 3, 4] = 4人桌
        """
        return [idx for idx, result in seat_results.items() if result["occupied"]]

    def get_table_size(self, seat_results: dict) -> int:
        """获取牌桌人数（活跃玩家数量）"""
        return len(self.get_active_players(seat_results))

    def detect_cards_near_dealer(self, dealer_region: np.ndarray) -> bool:
        """
        检测庄位附近是否有手牌（判断是否在发牌状态）

        Args:
            dealer_region: 庄位附近的截图

        Returns:
            True=附近有牌, False=无牌
        """
        if dealer_region.size == 0:
            return False

        gray = cv2.cvtColor(dealer_region, cv2.COLOR_BGR2GRAY)

        # 扑克牌特征：白色矩形带圆角，高宽比约 2.5:3.5
        _, white = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        card_count = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area < 50:
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            if cw < 5 or ch < 5:
                continue
            aspect = cw / max(ch, 1)
            # 牌的高宽比大约 0.6-0.8
            if 0.4 < aspect < 0.9:
                card_count += 1

        logger.debug(f"庄位附近检测到 {card_count} 个类牌矩形")
        return card_count >= 2  # 至少两张牌（每人发两张）


def test_detector():
    """简易测试：用当前截图检测座位"""
    from src.capture.screen_capture import ScreenCapture
    from src.roi.roi_manager import ROIManager

    cap = ScreenCapture()
    roi = ROIManager()
    detector = SeatDetector()

    full = cap.capture()
    seat_imgs = roi.crop_all_seats(full)
    results = detector.detect_all(seat_imgs)

    print("=== 座位检测结果 ===")
    for idx in range(6):
        r = results[idx]
        icon = "👤" if r["occupied"] else "➕"
        print(f"  座位 {idx}: {icon} {r['method']} (置信度: {r['confidence']:.0%})")

    active = detector.get_active_players(results)
    print(f"\n  活跃玩家: {len(active)} 人 → 座位 {active}")
    return results


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    test_detector()
