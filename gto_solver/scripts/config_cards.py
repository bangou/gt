"""
简易牌面位置配置器

用法:
    cd gto_solver
    PYTHONPATH="src" python -X utf8 scripts/config_cards.py

功能:
    1. 截图 → 显示带网格和像素坐标的预览图
    2. 让你输入牌面区域的坐标
    3. 保存到 config.json
"""

import sys
from pathlib import Path

import cv2
import numpy as np

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def main():
    from capture.screen_capture import ScreenCapture

    print("=" * 55)
    print("WePoker H5 — 牌面位置配置器")
    print("=" * 55)
    print()

    # 1. 截图
    print("[1/3] 截图...")
    cap = ScreenCapture()
    img = cap.capture_monitor(1)
    h, w = img.shape[:2]
    print(f"  屏幕: {w} x {h}")

    # 2. 画网格标注，每100px
    step = 100
    annotated = img.copy()
    for x in range(0, w, step):
        cv2.line(annotated, (x, 0), (x, h), (0, 0, 255), 1)
        cv2.putText(annotated, str(x), (x + 3, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    for y in range(0, h, step):
        cv2.line(annotated, (0, y), (w, y), (0, 0, 255), 1)
        cv2.putText(annotated, str(y), (5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

    # 缩放保存以便查看
    small = cv2.resize(annotated, (w // 2, h // 2))
    out_path = "card_positions_grid.png"
    cv2.imwrite(out_path, small)
    print(f"  网格图已保存: {out_path} ({(w//2)}x{(h//2)})")
    print(f"  每格 = 100px, 红线 = 坐标轴")
    print()

    # 3. 交互输入
    print("[2/3] 请查看 {out_path}，找到牌面位置后输入坐标")
    print(f"  屏幕分辨率: {w} x {h}")
    print()

    # ── Hero 牌 ──
    print("━━━ Hero 手牌 ━━━")
    print("  (你的两张手牌，通常在屏幕底部中央)")
    hero1_x = int(input("  Hero牌1 X坐标: ").strip() or "0")
    hero1_y = int(input("  Hero牌1 Y坐标: ").strip() or "0")
    hero1_w = int(input("  Hero牌1 宽(默认55): ").strip() or "55")
    hero1_h = int(input("  Hero牌1 高(默认80): ").strip() or "80")

    hero2_offset = int(input("  Hero牌2 与牌1的X间距(默认60): ").strip() or "60")
    hero2_x = hero1_x + hero2_offset
    hero2_y = hero1_y

    print()
    print("━━━ 公共牌区域 ━━━")
    print("  (翻牌3张/转牌4张/河牌5张并排，在桌子中央)")
    comm_x = int(input("  公共牌区域 X起始: ").strip() or "0")
    comm_y = int(input("  公共牌区域 Y起始: ").strip() or "0")
    comm_w = int(input("  公共牌区域 宽(5张牌跨度,默认350): ").strip() or "350")
    comm_h = int(input("  公共牌区域 高(默认85): ").strip() or "85")
    comm_card_w = int(input("  单张公共牌宽(默认50): ").strip() or "50")
    comm_card_h = int(input("  单张公共牌高(默认75): ").strip() or "75")

    print()
    print("━━━ 行动按钮区域 ━━━")
    print("  (Fold/Call/Raise 按钮, 通常底部中央, 留空跳过)")
    btn_x = input("  按钮区域 X起始(留空跳过): ").strip()
    if btn_x:
        btn_x = int(btn_x)
        btn_y = int(input("  按钮区域 Y起始: ").strip())
        btn_w = int(input("  按钮区域 宽(默认200): ").strip() or "200")
        btn_h = int(input("  按钮区域 高(默认80): ").strip() or "80")
    else:
        btn_x = btn_y = btn_w = btn_h = 0

    # 4. 保存
    print()
    print("[3/3] 保存配置...")

    from utils.config import set as cfg_set

    cfg_set("hero_card_boxes", [
        [hero1_x, hero1_y, hero1_w, hero1_h],
        [hero2_x, hero2_y, hero1_w, hero1_h],
    ])
    cfg_set("community_search_roi", [comm_x, comm_y, comm_w, comm_h])
    cfg_set("community_card_size", [comm_card_w, comm_card_h])
    cfg_set("reference_width", w)
    cfg_set("reference_height", h)

    if btn_x > 0:
        cfg_set("hero_action_roi", [btn_x, btn_y, btn_w, btn_h])

    print("  配置已保存到 config.json")
    print()
    print("=" * 55)
    print("完成!")
    print(f"Hero 1: ({hero1_x}, {hero1_y}) {hero1_w}x{hero1_h}")
    print(f"Hero 2: ({hero2_x}, {hero2_y}) {hero1_w}x{hero1_h}")
    print(f"公共牌: ({comm_x}, {comm_y}) {comm_w}x{comm_h} (每张 {comm_card_w}x{comm_card_h})")
    if btn_x > 0:
        print(f"按钮: ({btn_x}, {btn_y}) {btn_w}x{btn_h}")
    print("=" * 55)


if __name__ == "__main__":
    main()
