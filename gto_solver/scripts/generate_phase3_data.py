"""
生成阶段 3 GTO 数据: vs RFI 防守 + vs 3bet 决策 + 翻后牌面纹理

覆盖场景:
  3a. vs RFI — 各位置面对开池的 3bet/call/fold 决策 (Upswing Poker 公开范围)
  3b. vs 3bet — 开池后面对 3bet 的 4bet/call/fold 决策
  3c. 翻后 cbet — 8 种常见牌面纹理的 cbet 频率与防守范围

输出: data/seed/gto_data_vs_rfi.csv, gto_data_vs_3bet.csv, gto_data_postflop.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

# ── 工具函数 (复用 generate_preflop_data.py 的模式) ────────────────────

ranks = "AKQJT98765432"


def rank_idx(r: str) -> int:
    return ranks.index(r)


def all_hands() -> list[str]:
    """169 种手牌组合 (标准顺序)"""
    hands = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i < j:
                hands.append(f"{r1}{r2}s")
            elif i == j:
                hands.append(f"{r1}{r2}")
            else:
                hands.append(f"{r2}{r1}o")
    return hands


def in_pair_range(hand: str, min_pair: str) -> bool:
    """检查手牌是否 >= min_pair (如 in_pair_range('TT', '77') -> True)"""
    if len(hand) != 2 or hand[0] != hand[1]:
        return False
    return rank_idx(hand[0]) <= rank_idx(min_pair[0])


def in_range(hand: str, rdef: dict) -> bool:
    """检查手牌是否在范围定义内 (与 generate_preflop_data.py 一致)"""
    pairs_min = rdef.get("pairs", "")
    suited = rdef.get("suited", [])
    offsuit = rdef.get("offsuit", [])

    if len(hand) == 2 and hand[0] == hand[1]:
        if "+" in pairs_min:
            return in_pair_range(hand, pairs_min.replace("+", ""))
        return hand in rdef.get("exact_pairs", [])
    if hand.endswith("s"):
        return hand in suited
    if hand.endswith("o"):
        return hand in offsuit
    return False


# ── 范围定义 ──────────────────────────────────────────────────────────

# 面对各位置 open 时的 3bet 范围 (value + bluff)
# 格式: "位置" → {"pairs", "suited", "offsuit"}
VS_OPEN_3BET = {
    # 面对 EP (UTG/UTG1) open → 极紧 value 3bet
    "vs_ep": {
        "pairs": "QQ+",
        "suited": ["AKs", "AQs", "KQs"],
        "offsuit": ["AKo"],
    },
    # 面对 MP (UTG2/LJ) open
    "vs_mp": {
        "pairs": "JJ+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs"],
        "offsuit": ["AKo", "AQo"],
    },
    # 面对 HJ open
    "vs_hj": {
        "pairs": "TT+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "A5s", "A4s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo"],
    },
    # 面对 CO open
    "vs_co": {
        "pairs": "99+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "JTs",
                   "A5s", "A4s", "T9s", "98s", "KTs", "QTs"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo"],
    },
    # 面对 BTN open (在盲注位)
    "vs_btn_sb": {
        "pairs": "88+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "JTs",
                   "A5s", "A4s", "T9s", "98s", "87s", "KTs", "QTs", "A3s",
                   "A2s", "K9s", "Q9s", "J9s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "A9o", "KTo"],
    },
    # 面对 BTN open (在 BB — 最宽)
    "vs_btn_bb": {
        "pairs": "77+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "JTs",
                   "A5s", "A4s", "T9s", "98s", "87s", "76s", "KTs", "QTs",
                   "A3s", "A2s", "K9s", "Q9s", "J9s", "T8s", "65s", "54s",
                   "A9s", "A8s", "K8s", "Q8s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo",
                    "A9o", "KTo", "QTo", "JTo", "A8o", "K9o", "T9o"],
    },
}

# 面对 open 时的 call 范围 (cold call 或盲注 call)
VS_OPEN_CALL = {
    # 冷跟 EP open → 几乎不冷跟
    "vs_ep": {
        "pairs": "TT+",  # 小对子只 set mine / 大对子平跟设陷阱
        "suited": ["AKs", "AQs"],  # suited broadway
        "offsuit": [],
    },
    # 冷跟 MP open
    "vs_mp": {
        "pairs": "99+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "JTs", "T9s", "98s"],
        "offsuit": ["AKo", "AQo"],
    },
    # 冷跟 HJ open
    "vs_hj": {
        "pairs": "77+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "JTs", "T9s", "98s", "87s",
                   "ATs", "KJs", "QJs", "KTs", "QTs", "A5s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo"],
    },
    # 冷跟 CO open (BTN 冷跟)
    "vs_co": {
        "pairs": "55+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "JTs", "T9s", "98s", "87s",
                   "76s", "65s", "ATs", "KJs", "QJs", "KTs", "QTs", "J9s",
                   "T8s", "A5s", "A4s", "A3s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo"],
    },
    # SB vs BTN open
    "vs_btn_sb": {
        "pairs": "55+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "JTs", "T9s", "98s", "87s",
                   "76s", "65s", "ATs", "KJs", "QJs", "KTs", "QTs", "J9s",
                   "T8s", "A5s", "A4s", "A3s", "A2s", "A9s", "A8s", "A7s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "A9o", "KTo", "QTo"],
    },
    # BB vs BTN open (最宽防守)
    "vs_btn_bb": {
        "pairs": "22+",
        "suited": ["AKs", "AQs", "AJs", "KQs", "JTs", "T9s", "98s", "87s",
                   "76s", "65s", "54s", "ATs", "KJs", "QJs", "KTs", "QTs",
                   "J9s", "T8s", "97s", "86s", "75s", "64s", "A5s", "A4s",
                   "A3s", "A2s", "K9s", "Q9s", "J8s", "T7s", "96s", "85s",
                   "A9s", "A8s", "A7s", "A6s", "K8s", "Q8s", "J7s", "K7s",
                   "Q7s", "K6s", "Q6s"],
        "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                    "T9o", "98o", "A9o", "KTo", "QTo", "A8o", "A7o", "K9o",
                    "Q9o", "J9o", "T8o", "A6o", "A5o", "K8o", "Q8o", "J8o"],
    },
}

# 位置→面对 open 类别映射
POS_TO_VS_LABEL = {
    "UTG1": "vs_ep",
    "UTG2": "vs_ep",   # facing UTG+1 open (earliest)
    "LJ":   "vs_mp",   # facing UTG2 or earlier
    "HJ":   "vs_hj",   # facing LJ or earlier
    "CO":   "vs_hj",   # simplified: facing HJ (weighted average of LJ→MP)
    "BTN":  "vs_co",   # facing CO open (most common cold-call)
    "SB":   "vs_btn_sb",
    "BB":   "vs_btn_bb",
}

# vs 3bet 范围 (hero open → 面对 3bet)
VS_3BET_RANGES = {
    # EP open, face 3bet
    "ep_face_3bet": {
        "4bet": {
            "pairs": "KK+",
            "suited": ["AKs"],
            "offsuit": ["AKo"],
        },
        "call": {
            "pairs": "QQ+",
            "suited": ["AKs", "AQs", "KQs"],
            "offsuit": ["AKo", "AQo"],
        },
    },
    # MP open, face 3bet
    "mp_face_3bet": {
        "4bet": {
            "pairs": "KK+",
            "suited": ["AKs", "AQs"],
            "offsuit": ["AKo"],
        },
        "call": {
            "pairs": "JJ+",
            "suited": ["AKs", "AQs", "AJs", "KQs", "ATs"],
            "offsuit": ["AKo", "AQo"],
        },
    },
    # CO/BTN open, face 3bet
    "lp_face_3bet": {
        "4bet": {
            "pairs": "QQ+",
            "suited": ["AKs", "AQs", "AJs", "KQs"],
            "offsuit": ["AKo", "AQo"],
        },
        "call": {
            "pairs": "99+",
            "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "JTs",
                       "T9s", "98s", "KTs", "QTs", "A5s"],
            "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo"],
        },
    },
    # SB open, face BB 3bet
    "sb_face_3bet": {
        "4bet": {
            "pairs": "JJ+",
            "suited": ["AKs", "AQs", "AJs", "KQs", "ATs"],
            "offsuit": ["AKo", "AQo", "AJo"],
        },
        "call": {
            "pairs": "77+",
            "suited": ["AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs", "JTs",
                       "T9s", "98s", "87s", "KTs", "QTs", "J9s", "A5s",
                       "A4s", "A3s", "A9s", "A8s"],
            "offsuit": ["AKo", "AQo", "AJo", "KQo", "ATo", "KJo", "QJo", "JTo",
                        "A9o", "KTo"],
        },
    },
}

POS_TO_VS3BET_LABEL = {
    "UTG":  "ep_face_3bet",
    "UTG1": "ep_face_3bet",
    "UTG2": "mp_face_3bet",
    "LJ":   "mp_face_3bet",
    "HJ":   "mp_face_3bet",
    "CO":   "lp_face_3bet",
    "BTN":  "lp_face_3bet",
    "SB":   "sb_face_3bet",
}

# 翻后牌面纹理分类
POSTFLOP_TEXTURES = {
    "dry_low": {
        "desc": "干燥低张 (如 7♥2♣3♦)",
        "cbet_freq": 75.0,
        "check_freq": 25.0,
        "cbet_size": 33,  # % pot
    },
    "dry_high": {
        "desc": "干燥高张 (如 K♥7♣2♦)",
        "cbet_freq": 65.0,
        "check_freq": 35.0,
        "cbet_size": 33,
    },
    "wet_connected": {
        "desc": "湿润连张 (如 J♥T♣8♦)",
        "cbet_freq": 50.0,
        "check_freq": 50.0,
        "cbet_size": 50,
    },
    "wet_two_broadway": {
        "desc": "两张高牌 (如 K♥Q♣5♦)",
        "cbet_freq": 70.0,
        "check_freq": 30.0,
        "cbet_size": 33,
    },
    "ace_high_dry": {
        "desc": "A高干燥 (如 A♥7♣2♦)",
        "cbet_freq": 80.0,
        "check_freq": 20.0,
        "cbet_size": 33,
    },
    "paired_low": {
        "desc": "低对子面 (如 8♥8♣2♦)",
        "cbet_freq": 55.0,
        "check_freq": 45.0,
        "cbet_size": 33,
    },
    "paired_high": {
        "desc": "高对子面 (如 K♥K♣5♦)",
        "cbet_freq": 60.0,
        "check_freq": 40.0,
        "cbet_size": 33,
    },
    "monotone": {
        "desc": "同花面 (如 9♥6♥2♥)",
        "cbet_freq": 45.0,
        "check_freq": 55.0,
        "cbet_size": 50,
    },
}

# 对应 codec.py 的 board_texture_key 格式: high_rank|pairedness|suit|conn|broadway_count
# 这些是简化版，用于匹配各种具体牌面的归类
TEXTURE_KEY_MAP = {
    "dry_low":             "middle_high|unpaired|rainbow|disconnected|0",
    "dry_high":            "broadway_high|unpaired|rainbow|disconnected|1",
    "wet_connected":       "middle_high|unpaired|two_tone|connected|0",
    "wet_two_broadway":    "broadway_high|unpaired|rainbow|semi_connected|2",
    "ace_high_dry":        "ace_high|unpaired|rainbow|disconnected|0",
    "paired_low":          "middle_high|paired|rainbow|disconnected|0",
    "paired_high":         "broadway_high|paired|rainbow|disconnected|1",
    "monotone":            "middle_high|unpaired|monotone|semi_connected|0",
}


# ── CSV 写入 ─────────────────────────────────────────────────────────

CSV_FIELDS = [
    "table_size", "position", "effective_stack_bb", "street",
    "hand_key", "board_texture_key", "action_history_key",
    "action", "size_bb", "probability", "source", "notes",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path.name}: {len(rows):,} 行")


# ── 3a: vs RFI 生成 ──────────────────────────────────────────────────

def generate_vs_rfi(table_size: int, output_path: Path) -> None:
    """面对开池: 每个位置 → 3bet/call/fold 决策。"""
    all_h = all_hands()
    rows = []

    for pos, label in POS_TO_VS_LABEL.items():
        # 只生成对 table_size 有效的位置
        valid_6 = {"HJ", "CO", "BTN", "SB", "BB"}
        valid_9 = {"UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB", "BB"}
        valid = valid_6 if table_size == 6 else valid_9
        if pos not in valid:
            continue

        threebet_def = VS_OPEN_3BET.get(label, {})
        call_def = VS_OPEN_CALL.get(label, {})

        for hand in all_h:
            in_3bet = in_range(hand, threebet_def) if threebet_def else False
            in_call = in_range(hand, call_def) if call_def else False

            if in_3bet:
                # 范围内 → 3bet
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                    "action": "raise",
                    "size_bb": 9.0,
                    "probability": 100.0,
                    "source": f"vs_Open_Ranges_{table_size}max",
                    "notes": f"vs_open_label={label}",
                })
            elif in_call:
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                    "action": "call",
                    "size_bb": "",
                    "probability": 100.0,
                    "source": f"vs_Open_Ranges_{table_size}max",
                    "notes": f"vs_open_label={label}",
                })
            else:
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-hero_to_act",
                    "action": "fold",
                    "size_bb": "",
                    "probability": 100.0,
                    "source": f"vs_Open_Ranges_{table_size}max",
                    "notes": f"vs_open_label={label}",
                })

    write_csv(output_path, rows)


# ── 3b: vs 3bet 生成 ─────────────────────────────────────────────────

def generate_vs_3bet(table_size: int, output_path: Path) -> None:
    """Hero open → 被 3bet → 4bet/call/fold。"""
    all_h = all_hands()
    rows = []

    for pos, label in POS_TO_VS3BET_LABEL.items():
        valid_6 = {"UTG", "HJ", "CO", "BTN", "SB"}
        valid_9 = {"UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB"}
        valid = valid_6 if table_size == 6 else valid_9
        if pos not in valid:
            continue

        rdef = VS_3BET_RANGES.get(label, {})
        fourbet_def = rdef.get("4bet", {})
        call_def = rdef.get("call", {})

        for hand in all_h:
            in_4bet = in_range(hand, fourbet_def) if fourbet_def else False
            in_call = in_range(hand, call_def) if call_def else False

            if in_4bet:
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-raise_9bb-hero_to_act",
                    "action": "raise",
                    "size_bb": 22.0,  # 4bet to ~22bb
                    "probability": 100.0,
                    "source": f"vs_3bet_{table_size}max",
                    "notes": f"vs3bet_label={label}",
                })
            elif in_call:
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-raise_9bb-hero_to_act",
                    "action": "call",
                    "size_bb": "",
                    "probability": 100.0,
                    "source": f"vs_3bet_{table_size}max",
                    "notes": f"vs3bet_label={label}",
                })
            else:
                rows.append({
                    "table_size": table_size,
                    "position": pos,
                    "effective_stack_bb": 100,
                    "street": "preflop",
                    "hand_key": hand,
                    "board_texture_key": "none",
                    "action_history_key": "preflop:raise_2.5bb-raise_9bb-hero_to_act",
                    "action": "fold",
                    "size_bb": "",
                    "probability": 100.0,
                    "source": f"vs_3bet_{table_size}max",
                    "notes": f"vs3bet_label={label}",
                })

    write_csv(output_path, rows)


# ── 3c: 翻后 cbet 生成 ────────────────────────────────────────────────

def generate_postflop(table_size: int, output_path: Path) -> None:
    """翻后 cbet 与防守: 8 种牌面纹理 × BTN/BB。"""
    all_h = all_hands()
    rows = []

    # BTN vs BB SRP → BTN cbet (hero=BTN)
    for texture_name, info in POSTFLOP_TEXTURES.items():
        texture_key = TEXTURE_KEY_MAP[texture_name]
        cbet = info["cbet_freq"]
        check = info["check_freq"]
        size = info["cbet_size"]

        rows.append({
            "table_size": table_size,
            "position": "BTN",
            "effective_stack_bb": 100,
            "street": "flop",
            "hand_key": "ANY",
            "board_texture_key": texture_key,
            "action_history_key": "BTN_vs_BB_SRP_cbet",
            "action": "bet",
            "size_bb": size,
            "probability": cbet,
            "source": f"Postflop_Heuristic_{table_size}max",
            "notes": f"texture={texture_name} desc={info['desc']}",
        })
        rows.append({
            "table_size": table_size,
            "position": "BTN",
            "effective_stack_bb": 100,
            "street": "flop",
            "hand_key": "ANY",
            "board_texture_key": texture_key,
            "action_history_key": "BTN_vs_BB_SRP_cbet",
            "action": "check",
            "size_bb": "",
            "probability": check,
            "source": f"Postflop_Heuristic_{table_size}max",
            "notes": f"texture={texture_name} desc={info['desc']}",
        })

    # BB vs BTN SRP → BB vs cbet (hero=BB)
    # BB check → BTN cbet → BB: fold/call/raise
    for texture_name, info in POSTFLOP_TEXTURES.items():
        texture_key = TEXTURE_KEY_MAP[texture_name]
        cbet = info["cbet_freq"]

        # BB defense: fold ~cbet% of range, call rest, raise with strong
        # 简化: fold 30-50%, call 40-55%, raise 10-15% depending on texture
        if "dry" in texture_name or "ace_high" in texture_name:
            fold = 35.0
            call = 55.0
            raise_pct = 10.0
        elif "wet" in texture_name or "monotone" in texture_name:
            fold = 50.0
            call = 40.0
            raise_pct = 10.0
        else:
            fold = 40.0
            call = 48.0
            raise_pct = 12.0

        rows.append({
            "table_size": table_size,
            "position": "BB",
            "effective_stack_bb": 100,
            "street": "flop",
            "hand_key": "ANY",
            "board_texture_key": texture_key,
            "action_history_key": "BB_vs_BTN_SRP_vs_cbet",
            "action": "fold",
            "size_bb": "",
            "probability": fold,
            "source": f"Postflop_Heuristic_{table_size}max",
            "notes": f"texture={texture_name} desc={info['desc']}",
        })
        rows.append({
            "table_size": table_size,
            "position": "BB",
            "effective_stack_bb": 100,
            "street": "flop",
            "hand_key": "ANY",
            "board_texture_key": texture_key,
            "action_history_key": "BB_vs_BTN_SRP_vs_cbet",
            "action": "call",
            "size_bb": "",
            "probability": call,
            "source": f"Postflop_Heuristic_{table_size}max",
            "notes": f"texture={texture_name} desc={info['desc']}",
        })
        rows.append({
            "table_size": table_size,
            "position": "BB",
            "effective_stack_bb": 100,
            "street": "flop",
            "hand_key": "ANY",
            "board_texture_key": texture_key,
            "action_history_key": "BB_vs_BTN_SRP_vs_cbet",
            "action": "raise",
            "size_bb": 50,
            "probability": raise_pct,
            "source": f"Postflop_Heuristic_{table_size}max",
            "notes": f"texture={texture_name} desc={info['desc']}",
        })

    write_csv(output_path, rows)


# ── 主入口 ──────────────────────────────────────────────────────────

def main() -> None:
    seed_dir = Path("data/seed")
    seed_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("阶段 3 GTO 数据生成")
    print("=" * 60)

    # 3a: vs RFI (9-max + 6-max)
    print("\n[3a] vs RFI 防守数据...")
    generate_vs_rfi(9, seed_dir / "gto_data_vs_rfi_9max.csv")
    generate_vs_rfi(6, seed_dir / "gto_data_vs_rfi_6max.csv")

    # 3b: vs 3bet (9-max + 6-max)
    print("\n[3b] vs 3bet 决策树数据...")
    generate_vs_3bet(9, seed_dir / "gto_data_vs_3bet_9max.csv")
    generate_vs_3bet(6, seed_dir / "gto_data_vs_3bet_6max.csv")

    # 3c: 翻后纹理
    print("\n[3c] 翻后牌面纹理数据...")
    generate_postflop(9, seed_dir / "gto_data_postflop_cbet_9max.csv")
    generate_postflop(6, seed_dir / "gto_data_postflop_cbet_6max.csv")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    total = 0
    files = list(seed_dir.glob("gto_data_vs_*.csv")) + list(seed_dir.glob("gto_data_postflop_*.csv"))
    for csv_file in sorted(files):
        with open(csv_file) as f:
            count = sum(1 for _ in f) - 1
        total += count
        print(f"  {csv_file.name}: {count:,} 行")
    print(f"\n阶段 3 新增总计: {total:,} 行")


if __name__ == "__main__":
    main()
