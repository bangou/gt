"""
seat_assigner.py - 座位角色动态分配

核心逻辑：
  1. 检测 D 标记在哪个座位位置
  2. 检测哪些座位有人
  3. 根据人数和 D 位置动态分配角色

  6人桌顺时针: UTG -> HJ -> CO -> BTN(D) -> SB -> BB
  2人桌: BTN(D)+SB -> BB
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 6人桌标准顺时针顺序
SEAT_ORDER_6MAX = [0, 1, 2, 3, 4, 5]  # 座位0-5按顺时针排列


def assign_roles(dealer_seat: int, active_seats: list[int]) -> dict:
    """
    根据庄位和活跃玩家分配角色。

    Args:
        dealer_seat: D 标记所在的座位号 (0-5)
        active_seats: 活跃玩家座位号列表

    Returns:
        {seat_index: role_name}
        例: {3: "BTN", 4: "SB", 5: "BB", 0: "UTG", 1: "HJ", 2: "CO"}
    """
    if not active_seats:
        return {}

    # 顺时针排列活跃座位
    clockwise = []
    # 从 dealer 的下一个座位开始顺时针遍历
    for offset in range(1, 7):
        seat = (dealer_seat + offset) % 6
        if seat in active_seats:
            clockwise.append(seat)

    n_players = len(active_seats)
    result = {}

    # 庄位
    result[dealer_seat] = "BTN"

    if n_players == 2:
        # 2人桌: BTN+SB(庄位) / BB
        for s in active_seats:
            if s != dealer_seat:
                result[s] = "BB"
                break

    elif n_players >= 3:
        # 按顺时针分配 SB, BB, UTG, HJ, CO
        roles_clockwise = ["SB", "BB", "UTG", "HJ", "CO"]
        for seat, role in zip(clockwise, roles_clockwise):
            if seat != dealer_seat:
                result[seat] = role

        # 补充剩下的人
        remaining = [s for s in clockwise if s not in result and s != dealer_seat]
        extra_roles = ["UTG", "HJ", "CO", "MP", "MP2", "EP"]
        for seat, role in zip(remaining, extra_roles):
            if seat not in result:
                result[seat] = role

    # 任何未被分配的角色默认为空
    for s in active_seats:
        if s not in result:
            result[s] = f"玩家{s}"

    return result


def get_hero_role(dealer_seat: int, hero_seat: int, active_seats: list[int]) -> str:
    """获取你的角色（如 BTN/SB/BB/UTG 等）"""
    roles = assign_roles(dealer_seat, active_seats)
    return roles.get(hero_seat, f"座位{hero_seat}")


# ── 快速测试 ──
if __name__ == "__main__":
    print("=== 座位分配测试 ===")

    # 场景1: 6人满桌，D在座位3
    print("\n--- 6人满桌，D在座位3 ---")
    r = assign_roles(3, [0, 1, 2, 3, 4, 5])
    for s, role in sorted(r.items()):
        print(f"  座位{s}: {role}")

    # 场景2: 2人桌，你在座位4(含D)，对手在座位1
    print("\n--- 2人桌，D在座位4 ---")
    r = assign_roles(4, [4, 1])
    for s, role in sorted(r.items()):
        print(f"  座位{s}: {role}")

    # 场景3: 3人桌，D在座位3
    print("\n--- 3人桌，D在座位3 ---")
    r = assign_roles(3, [3, 4, 1])
    for s, role in sorted(r.items()):
        print(f"  座位{s}: {role}")
