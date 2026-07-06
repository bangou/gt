"""
WePoker H5 牌面自动检测脚本

用法:
    cd gto_solver
    PYTHONPATH="src" python scripts/detect_cards.py

功能:
    截取屏幕 → 多种方法检测牌面位置 → 保存裁剪图供模板库用
"""

import cv2
import numpy as np
from pathlib import Path


def detect_cards(image: np.ndarray, output_dir: str = "templates/cards/h5_new"):
    """多种方法检测牌面，返回裁剪图列表"""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates = []

    # 方法 1: 找白色矩形 (传统牌面: 白底黑字)
    for thr in [120, 140, 160]:
        _, mask = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            ar = cw / max(ch, 1)
            area = cw * ch
            if 800 < area < 25000 and 0.35 < ar < 0.95:
                roi = gray[y:y+ch, x:x+cw]
                if roi.std() > 20:
                    candidates.append((x, y, cw, ch, f"white_thr{thr}"))

    # 方法 2: 找暗色矩形 (牌背/暗色牌面)
    for thr in [50, 70, 90]:
        mask = cv2.inRange(gray, 0, thr)
        kernel = np.ones((3, 3), np.uint8)
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            ar = cw / max(ch, 1)
            area = cw * ch
            if 1000 < area < 30000 and 0.3 < ar < 0.95:
                roi = gray[y:y+ch, x:x+cw]
                if roi.std() > 30:
                    candidates.append((x, y, cw, ch, f"dark_thr{thr}"))

    # 方法 3: 边缘检测 (Canny)
    edges = cv2.Canny(gray, 30, 100)
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        ar = cw / max(ch, 1)
        area = cw * ch
        if 1500 < area < 25000 and 0.35 < ar < 0.95:
            roi = gray[y:y+ch, x:x+cw]
            internal = roi[5:-5, 5:-5] if roi.shape[0] > 10 and roi.shape[1] > 10 else roi
            if internal.std() > 20:
                candidates.append((x, y, cw, ch, "edge"))

    # 方法 4: HSV 高饱和度彩色区域 (牌面花纹)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturated = cv2.inRange(hsv, (0, 30, 60), (180, 255, 255))
    contours, _ = cv2.findContours(saturated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        ar = cw / max(ch, 1)
        area = cw * ch
        if 500 < area < 15000 and 0.3 < ar < 0.95:
            candidates.append((x, y, cw, ch, "saturated"))

    # 去重 (按位置聚类)
    if not candidates:
        return [], image

    candidates.sort(key=lambda c: (c[1], c[0]))
    unique = []
    for c in candidates:
        x, y, cw, ch, method = c
        # 检查是否和已有候选重叠
        overlap = False
        for ux, uy, uw, uh, um in unique:
            ix = max(x, ux)
            iy = max(y, uy)
            ix2 = min(x + cw, ux + uw)
            iy2 = min(y + ch, uy + uh)
            if ix2 > ix and iy2 > iy:
                overlap_area = (ix2 - ix) * (iy2 - iy)
                min_area = min(cw * ch, uw * uh)
                if overlap_area > 0.5 * min_area:
                    overlap = True
                    break
        if not overlap:
            unique.append(c)

    # 保存裁剪图
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    saved = []
    for i, (x, y, cw, ch, method) in enumerate(unique):
        patch = image[y:y+ch, x:x+cw]
        fname = f"card_{i:03d}_{x}_{y}_{cw}x{ch}_{method}.png"
        cv2.imwrite(str(out / fname), patch)
        saved.append((fname, x, y, cw, ch, method))

    # 画框标注原图
    annotated = image.copy()
    for x, y, cw, ch, method in unique:
        color = {"white": (0, 255, 0), "dark": (0, 255, 255), "edge": (255, 0, 255), "saturated": (255, 255, 0)}.get(
            method.split("_")[0], (0, 0, 255)
        )
        cv2.rectangle(annotated, (x, y), (x + cw, y + ch), color, 2)
        cv2.putText(annotated, f"{cw}x{ch}", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    cv2.imwrite(str(out / "_annotated.png"), annotated)
    return saved, annotated


def main():
    from capture.screen_capture import ScreenCapture

    print("截取屏幕...")
    cap = ScreenCapture()
    full = cap.capture_monitor(1)
    print(f"屏幕尺寸: {full.shape[1]}x{full.shape[0]}")

    print("检测牌面...")
    cards, annotated = detect_cards(full)

    print(f"\n找到 {len(cards)} 张牌面候选:")
    for name, x, y, cw, ch, method in cards:
        print(f"  {name}: ({x},{y}) {cw}x{ch} [{method}]")

    if not cards:
        print("\n未找到任何牌面！")
        print("可能原因:")
        print("  1. 你不在牌桌上 (在大厅)")
        print("  2. WePoker H5牌面设计跟预期完全不同")
        print("  3. 牌面的白色/暗色阈值不在扫描范围内")

        # 打印全屏颜色统计帮助诊断
        print("\n全屏颜色诊断:")
        hsv = cv2.cvtColor(full, cv2.COLOR_BGR2HSV)
        for y_start in range(0, full.shape[0], 80):
            y_end = min(y_start + 80, full.shape[0])
            strip = full[y_start:y_end, :, :]
            m = strip.mean(axis=(0, 1))
            s = strip.std(axis=(0, 1)).mean()
            print(f"  Y={y_start:4d}-{y_end}: BGR=({m[0]:.0f},{m[1]:.0f},{m[2]:.0f}) std={s:.0f}")


if __name__ == "__main__":
    main()
