"""
roi_config.py - 牌桌各区域的 ROI（Region of Interest）配置

来源：在实际发牌截图中自动检测并校准。
分辨率：1920x1080（WePoker 窗口全屏）

座位布局（6人桌，顺时针）：
          ┌────────────────────────────────────┐
          │          牌局信息                    │
   座位0  │  公共牌                    座位1    │
   座位5  │  底池                      座位2    │
   座位4  │                           座位3 BTN │
          │  Hero手牌+按钮                      │
          └────────────────────────────────────┘
"""

# ──────────────────────────────────────────
# 各区域配置（1920x1080，窗口全屏）
# ──────────────────────────────────────────

ROI_CONFIG = {
    # --- 座位区域 ---
    "seats": {
        0: {"name": "座位0", "rect": (156, 200, 97, 120)},     # 左上
        1: {"name": "座位1", "rect": (1650, 200, 118, 129)},   # 右上
        2: {"name": "座位2", "rect": (1659, 360, 109, 119)},   # 右中
        3: {"name": "座位3", "rect": (1612, 530, 161, 119)},   # 右下（庄位BTN）
        4: {"name": "座位4", "rect": (133, 530, 210, 163)},    # 左下
        5: {"name": "座位5", "rect": (121, 360, 138, 109)},    # 左中
    },

    # --- 牌桌中央区域 ---
    "community_cards": {
        "rect": (864, 270, 178, 104),     # 公共牌
    },

    "pot": {
        "rect": (793, 400, 350, 149),     # 底池金额
    },

    # --- Hero 区域（你的手牌 + 操作按钮） ---
    # 检测到手牌实际位置: (828,476) 和 (935,476) 每张 52x75
    "hero": {
        "rect": (735, 450, 498, 377),     # 底部中央大框（y从牌位置开始）
        "sub_areas": {
            "cards":     (80, 20, 330, 110),    # 手牌区域（覆盖已知牌坐标）
            "actions":   (0, 150, 498, 227),   # 操作按钮区域
            "stack":     (330, 20, 168, 110),  # 筹码区域
        }
    },

    # --- Dealer 标记 ---
    "dealer_marker": {
        "rect": (1612, 530, 161, 119),     # 座位3 = BTN 区域
    },

    # --- 游戏信息 ---
    "game_info": {
        "rect": (906, 50, 117, 115),      # 顶部信息
    },
}

# 实际检测到的牌坐标（用于验证）
# Hero 手牌: (828, 476) 和 (935, 476) 每张 52x75
VERIFIED_CARD_POSITIONS = [(828, 476, 52, 75), (935, 476, 52, 75)]


def resolve_roi(key: str, sub_key: str = None) -> tuple:
    """获取指定区域的绝对坐标"""
    config = ROI_CONFIG.get(key)
    if not config:
        raise KeyError(f"未知区域: {key}")

    if sub_key:
        parent_rect = config["rect"]
        sub = config["sub_areas"][sub_key]
        return (
            parent_rect[0] + sub[0],
            parent_rect[1] + sub[1],
            sub[2],
            sub[3],
        )

    if isinstance(config, dict) and "rect" in config:
        return config["rect"]
    raise KeyError(f"区域 {key} 没有 rect 配置")


def get_seat_rect(seat_index: int) -> tuple:
    """获取指定座位的区域坐标"""
    seat = ROI_CONFIG["seats"].get(seat_index)
    if not seat:
        raise KeyError(f"无效座位号: {seat_index}（有效值 0-5）")
    return seat["rect"]


def get_all_seat_rects() -> dict:
    """获取所有座位区域"""
    return {idx: seat["rect"] for idx, seat in ROI_CONFIG["seats"].items()}
