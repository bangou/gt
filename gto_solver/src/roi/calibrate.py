"""
calibrate.py - 自动标定牌桌 ROI

在发牌状态下运行，自动检测牌桌各元素位置并保存校准结果。

用法: python -X utf8 -m src.roi.calibrate
"""

import json
from pathlib import Path

import cv2
import numpy as np

from src.capture.screen_capture import ScreenCapture


def auto_calibrate(save_path: str = "assets/config/calibrated_roi.json"):
    """
    自动检测牌桌各区域位置，生成 ROI 配置文件。
    需要在发牌状态下运行。
    """
    cap = ScreenCapture()
    img = cap.capture_monitor(1)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    print(f"截图尺寸: {w}x{h}")
    print("正在检测牌桌区域...")

    # ── 1. 找牌桌背景（蓝绿色高饱和区域） ──
    bg_mask = cv2.inRange(hsv, (50, 100, 50), (130, 255, 200))
    kernel = np.ones((7, 7), np.uint8)
    bg_mask = cv2.morphologyEx(bg_mask, cv2.MORPH_CLOSE, kernel)
    bg_mask = cv2.morphologyEx(bg_mask, cv2.MORPH_OPEN, kernel)

    # 水平投影找桌面的上下边界
    row_proj = np.sum(bg_mask > 0, axis=1)
    min_green = w * 0.15
    table_rows = np.where(row_proj > min_green)[0]

    if len(table_rows) < 50:
        print("⚠️  未检测到足够大的牌桌区域（桌面背景不明显）")
        print("   尝试用内容密度定位...")

        # 回退：用边缘密度找
        edges = cv2.Canny(gray, 30, 100)
        row_edges = np.sum(edges > 0, axis=1)
        table_rows = np.where(row_edges > w * 0.02)[0]

    if len(table_rows) < 50:
        print("❌ 无法定位牌桌，请确保牌桌画面在屏幕上")
        return None

    table_top = int(table_rows[0])
    table_bottom = int(table_rows[-1])
    table_height = table_bottom - table_top
    table_mid = (table_top + table_bottom) // 2

    print(f"  牌桌范围: y={table_top}~{table_bottom} (高{table_height}px)")

    # ── 2. 检测牌 ──
    print("正在检测卡牌...")
    table_gray = gray[table_top:table_bottom, :]

    # 多阈值找牌（白色/浅色矩形）
    cards = []
    for thresh in [200, 180, 150, 120]:
        _, bw = cv2.threshold(table_gray, thresh, 255, cv2.THRESH_BINARY)
        # 形态学清理噪点
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in contours:
            area = cv2.contourArea(c)
            if area < 300 or area > 8000:
                continue
            cx, cy, cw, ch = cv2.boundingRect(c)
            if cw < 20 or ch < 30:
                continue
            ar = cw / max(ch, 1)
            if 0.35 < ar < 1.0:
                abs_y = cy + table_top
                # 去重
                is_dup = False
                for _, ex, ey, _, _ in cards:
                    if abs(cx - ex) < 30 and abs(abs_y - ey) < 30:
                        is_dup = True
                        break
                if not is_dup:
                    cards.append((area, cx, abs_y, cw, ch))

    cards.sort(reverse=True)
    print(f"  找到 {len(cards)} 个疑似牌区域")

    # ── 3. 找红色按钮（弃牌/加注等） ──
    print("正在检测按钮...")
    red_mask = cv2.inRange(hsv, (0, 50, 50), (10, 255, 255))
    red_mask |= cv2.inRange(hsv, (160, 50, 50), (180, 255, 255))
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    buttons = []
    for c in red_contours:
        area = cv2.contourArea(c)
        if area < 100 or area > 5000:
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        buttons.append((area, bx, by, bw, bh))

    buttons.sort(reverse=True)
    print(f"  找到 {len(buttons)} 个红色按钮区域")

    # ── 4. 找 "+" 号座位 ──
    _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    plus_contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    seats = []
    for c in plus_contours:
        area = cv2.contourArea(c)
        if area < 20 or area > 300:
            continue
        sx, sy, sw, sh = cv2.boundingRect(c)
        if table_top < sy < table_bottom:
            seats.append((area, sx, sy, sw, sh))

    print(f"  找到 {len(seats)} 个 '+' 符号（空座位）")

    # ── 5. 保存结果 ──
    result = {
        "screen_size": {"width": w, "height": h},
        "table_region": {
            "top": int(table_top),
            "bottom": int(table_bottom),
            "height": int(table_height),
            "mid_y": int(table_mid),
        },
        "cards": [(int(x), int(y), int(cw), int(ch)) for _, x, y, cw, ch in cards[:10]],
        "buttons": [(int(x), int(y), int(bw), int(bh)) for _, x, y, bw, bh in buttons[:10]],
        "plus_signs": [(int(x), int(y), int(sw), int(sh)) for _, x, y, sw, sh in seats[:20]],
    }

    path = Path(save_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n✅ 标定结果已保存: {save_path}")
    return result


def draw_calibration(image: np.ndarray, result: dict, output_path: str):
    """在图上标注标定结果"""
    vis = image.copy()

    # 牌桌区域
    t = result["table_region"]
    cv2.rectangle(vis, (0, t["top"]), (result["screen_size"]["width"], t["bottom"]), (0, 255, 0), 3)
    cv2.putText(vis, f"Table y={t['top']}-{t['bottom']}", (10, t["top"] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # 牌
    for i, (x, y, cw, ch) in enumerate(result["cards"]):
        cv2.rectangle(vis, (x, y), (x + cw, y + ch), (255, 0, 0), 2)
        cv2.putText(vis, f"Card{i + 1}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

    # 按钮
    for x, y, bw, bh in result["buttons"]:
        cv2.rectangle(vis, (x, y), (x + bw, y + bh), (0, 0, 255), 2)

    # '+' 号
    for x, y, sw, sh in result["plus_signs"]:
        cv2.rectangle(vis, (x, y), (x + sw, y + sh), (255, 255, 0), 1)

    cv2.imwrite(output_path, vis)
    print(f"标注图已保存: {output_path}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    result = auto_calibrate()
    if result:
        from src.capture.screen_capture import ScreenCapture

        cap = ScreenCapture()
        img = cap.capture_monitor(1)
        draw_calibration(img, result, "tests/output/calibration_result.png")
