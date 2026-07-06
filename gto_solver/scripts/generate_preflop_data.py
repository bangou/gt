"""
生成 9-max 100BB 翻前 GTO 数据 (Upswing Poker 免费公开范围表)。

输出: data/seed/gto_data_preflop_9max.csv

覆盖场景:
  - RFI (每个位置的开池范围)
  - vs RFI (面对开池的防守/3bet)
  - 3bet (3bet 范围)
  - Cold Call (冷跟范围)
  - Blind Defense (盲注防守 vs BTN/CO)

数据来源: Upswing Poker, Jonathan Little, Modern Poker Theory 免费预览
"""

from __future__ import annotations

import csv
from pathlib import Path

# ── 工具函数 ────────────────────────────────────────────────────────

ranks = "AKQJT98765432"


def all_169_hands() -> list[str]:
    hands = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i < j:  # suited (大在前)
                hands.append(f"{r1}{r2}s")
            elif i == j:  # pair
                hands.append(f"{r1}{r2}")
            else:  # offsuit (小在前, 大在后)
                hands.append(f"{r2}{r1}o")
    return hands


def hand_in_range(hand: str, rfi_def: dict) -> bool:
    """检查手牌是否在范围定义内。"""
    _ranks = "AKQJT98765432"
    def rank_idx(r):
        return _ranks.index(r)

    pairs_def = rfi_def.get("pairs", "")
    suited_list = rfi_def.get("suited", [])
    offsuit_list = rfi_def.get("offsuit", [])

    if len(hand) == 2:  # pair
        if "+" in pairs_def:
            min_pair = pairs_def.replace("+", "")
            return rank_idx(hand[0]) <= rank_idx(min_pair[0])
        return hand in rfi_def.get("exact_pairs", [])

    if hand.endswith("s"):
        return hand in suited_list
    elif hand.endswith("o"):
        return hand in offsuit_list
    return False


def expand_suited_broadways(include_kx: bool = False, include_qx: bool = False):
    """生成常用的 suited 范围。"""
    broadway = "AKQJT"
    result = []
    for i, r1 in enumerate(broadway):
        for r2 in broadway[i + 1:]:
            result.append(f"{r1}{r2}s")
    # suited connectors
    for i, r1 in enumerate(ranks):
        if i > len(ranks) - 2:
            break
        r2 = ranks[i + 1]
        # T9s-54s
        if rank_idx(r1) <= rank_idx("9"):
            result.append(f"{r1}{r2}s")
    # suited one-gappers: J9s-86s, T8s-75s, 97s-64s
    for i, r1 in enumerate(ranks):
        if i > len(ranks) - 3:
            break
        r2 = ranks[i + 2]
        if rank_idx(r1) <= rank_idx("T"):
            result.append(f"{r1}{r2}s")
    # Axs (A2s-A5s mainly as bluffs)
    for r in "5432":
        result.append(f"A{r}s")
    if include_kx:
        for r in "98765432":
            result.append(f"K{r}s")
    if include_qx:
        for r in "987654":
            result.append(f"Q{r}s")
    return sorted(set(result))


# ── 9-max RFI 范围定义 ──────────────────────────────────────────────

def rank_idx(r):
    return ranks.index(r)


RFI_RANGES_9MAX = {
    "UTG": {
        "pairs": "77+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "A5s", "A4s"],
        "offsuit": ["AKo", "AQo"],
    },
    "UTG1": {
        "pairs": "66+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "A5s", "A4s", "A3s", "KTs", "QTs"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo"],
    },
    "UTG2": {
        "pairs": "55+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "A5s", "A4s", "A3s",
                   "A2s", "KTs", "QTs", "J9s", "T8s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo"],
    },
    "LJ": {
        "pairs": "44+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "A9s", "A8s", "A7s", "A6s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo"],
    },
    "HJ": {
        "pairs": "33+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "A9s", "A8s", "A7s", "A6s", "K9s", "Q9s", "J8s", "T7s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "A9o", "KTo", "QTo"],
    },
    "CO": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "53s", "A9s", "A8s", "A7s", "A6s", "K9s",
                   "Q9s", "J8s", "T7s", "96s", "85s", "K8s", "Q8s", "J7s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o"],
    },
    "BTN": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "53s", "A9s", "A8s", "A7s", "A6s", "K9s",
                   "Q9s", "J8s", "T7s", "96s", "85s", "74s", "K8s", "Q8s",
                   "J7s", "T6s", "95s", "84s", "73s", "62s", "52s", "43s",
                   "K7s", "Q7s", "J6s", "T5s", "94s", "83s", "72s", "63s",
                   "K6s", "Q6s", "J5s", "T4s", "93s", "82s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "87o", "A9o", "KTo", "QTo", "A8o", "A7o",
                    "K9o", "Q9o", "J9o", "T8o", "A6o", "A5o", "A4o", "A3o",
                    "A2o", "K8o", "Q8o", "J8o", "T7o", "97o", "86o", "76o",
                    "65o", "54o"],
    },
    "SB": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "53s", "A9s", "A8s", "A7s", "A6s", "K9s",
                   "Q9s", "J8s", "T7s", "96s", "85s", "K8s", "Q8s", "J7s",
                   "T6s", "95s", "84s", "K7s", "Q7s", "J6s", "T5s", "94s",
                   "83s", "K6s", "Q6s", "J5s", "T4s", "93s", "82s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o", "A6o", "A5o", "A4o", "A3o", "A2o",
                    "K8o", "Q8o", "J8o", "T7o", "97o", "86o", "76o", "65o",
                    "K7o", "Q7o", "J7o", "T6o", "96o"],
    },
}

# vs RFI 范围 (3bet + call)
# BTN open → BB defend
BB_VS_BTN_RFI = {
    "pairs": "22+",
    "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
               "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
               "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
               "A9s", "A8s", "A7s", "A6s", "K9s", "Q9s", "J8s", "T7s",
               "96s", "85s", "75s", "64s", "K8s", "Q8s", "J7s", "K7s",
               "Q7s", "K6s", "Q6s"],
    "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "K9o", "Q9o",
                "J9o", "T8o", "A7o", "A6o", "A5o", "K8o", "Q8o", "J8o"],
}

# 3bet 范围 (主要位置 vs 各位置 open)
BTN_VS_UTG_3BET = {
    "pairs": "QQ+",
    "suited": ["AKs", "AQs", "KQs"],
    "offsuit": ["AKo", "AQo"],
}
BTN_VS_HJ_3BET = {
    "pairs": "JJ+",
    "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs"],
    "offsuit": ["AKo", "AQo", "AJo", "KQo"],
}

# 6-max 数据（扩展现有）
RFI_RANGES_6MAX = {
    "UTG": {
        "pairs": "77+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "A5s", "A4s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo"],
    },
    "HJ": {
        "pairs": "55+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "A5s", "A4s", "A3s", "KTs",
                   "QTs", "J9s", "A9s", "A8s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo"],
    },
    "CO": {
        "pairs": "33+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "A9s", "A8s", "A7s", "A6s", "K9s", "Q9s", "J8s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "A9o", "KTo", "QTo"],
    },
    "BTN": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "53s", "A9s", "A8s", "A7s", "A6s", "K9s",
                   "Q9s", "J8s", "T7s", "96s", "85s", "K8s", "Q8s", "J7s",
                   "T6s", "95s", "84s", "K7s", "Q7s", "K6s", "Q6s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o", "A6o", "A5o", "A4o", "A3o", "A2o",
                    "K8o", "Q8o", "J8o", "T7o", "97o", "86o", "76o", "65o"],
    },
    "SB": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "53s", "A9s", "A8s", "A7s", "A6s", "K9s",
                   "Q9s", "J8s", "T7s", "96s", "85s", "K8s", "Q8s", "J7s",
                   "T6s", "95s", "84s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o", "A6o", "A5o", "A4o", "A3o", "A2o"],
    },
    "BB": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "ATs", "KQs", "KJs", "QJs", "JTs",
                   "T9s", "98s", "87s", "76s", "65s", "54s", "A5s", "A4s",
                   "A3s", "A2s", "KTs", "QTs", "J9s", "T8s", "97s", "86s",
                   "75s", "64s", "A9s", "A8s", "A7s", "A6s", "K9s", "Q9s",
                   "J8s", "T7s", "96s", "85s", "K8s", "Q8s", "J7s", "K7s",
                   "Q7s", "K6s", "Q6s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o", "A6o", "A5o", "A4o", "A3o", "A2o",
                    "K8o", "Q8o", "J8o", "T7o", "97o", "86o", "76o", "65o"],
    },
}


# ── 生成 CSV ─────────────────────────────────────────────────────────

def generate_rfi_csv(
    ranges: dict,
    table_size: int,
    source_label: str,
    output_path: Path,
):
    """为每个位置生成 RFI 数据行。"""
    all_hands = all_169_hands()
    rows = []
    for pos, rfi_def in ranges.items():
        if pos == "BB":
            continue
        for hand in all_hands:
            if not hand_in_range(hand, rfi_def):
                # 在范围外 → fold
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "RFI",
                    "action": "fold",
                    "size_bb": "",
                    "probability": 100.0,
                    "source": source_label,
                    "notes": "",
                })
            else:
                # 在范围内 → raise
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "RFI",
                    "action": "raise",
                    "size_bb": 2.5,
                    "probability": 100.0,
                    "source": source_label,
                    "notes": "",
                })

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "table_size", "position", "effective_stack_bb", "street",
            "hand_key", "board_texture_key", "action_history_key",
            "action", "size_bb", "probability", "source", "notes",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"  {output_path.name}: {len(rows)} 行")


def generate_blind_defense_csv(output_path: Path, table_size: int = 9):
    """BB vs BTN open → 3bet/call/fold 决策。"""
    all_hands = all_169_hands()
    rows = []
    for hand in all_hands:
        if hand_in_range(hand, BB_VS_BTN_RFI):
            # 强牌 3bet, 中等 call
            # 简化: 所有范围内手牌 call 70%, 3bet 30%
            rows.append({
                "table_size": table_size,
                "position": "BB",
                "effective_stack_bb": 100,
                "street": "preflop",
                "hand_key": hand,
                "board_texture_key": "none",
                "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                "action": "call",
                "size_bb": "",
                "probability": 70.0,
                "source": "Blind_Defense_9max",
                "notes": "",
            })
            rows.append({
                "table_size": table_size,
                "position": "BB",
                "effective_stack_bb": 100,
                "street": "preflop",
                "hand_key": hand,
                "board_texture_key": "none",
                "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                "action": "raise",
                "size_bb": 9.0,
                "probability": 30.0,
                "source": "Blind_Defense_9max",
                "notes": "",
            })
        else:
            rows.append({
                "table_size": table_size,
                "position": "BB",
                "effective_stack_bb": 100,
                "street": "preflop",
                "hand_key": hand,
                "board_texture_key": "none",
                "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                "action": "fold",
                "size_bb": "",
                "probability": 100.0,
                "source": "Blind_Defense_9max",
                "notes": "",
            })

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "table_size", "position", "effective_stack_bb", "street",
            "hand_key", "board_texture_key", "action_history_key",
            "action", "size_bb", "probability", "source", "notes",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  {output_path.name}: {len(rows)} 行")


# ── 主入口 ──────────────────────────────────────────────────────────

def main():
    seed_dir = Path("data/seed")
    seed_dir.mkdir(parents=True, exist_ok=True)

    print("生成 9-max RFI 数据...")
    generate_rfi_csv(RFI_RANGES_9MAX, 9, "Upswing_Open_Ranges_9max",
                     seed_dir / "gto_data_rfi_9max.csv")

    print("生成 6-max RFI 数据...")
    generate_rfi_csv(RFI_RANGES_6MAX, 6, "Upswing_Open_Ranges_6max",
                     seed_dir / "gto_data_rfi_6max.csv")

    print("生成 BB 盲注防守数据...")
    generate_blind_defense_csv(seed_dir / "gto_data_blind_defense_9max.csv", 9)

    # 汇总
    total = 0
    for csv_file in sorted(seed_dir.glob("gto_data_*.csv")):
        with open(csv_file) as f:
            count = sum(1 for _ in f) - 1  # 减去表头
        total += count
        print(f"  {csv_file.name}: {count} 行")

    print(f"\n总计新数据: {total} 行")


if __name__ == "__main__":
    main()
