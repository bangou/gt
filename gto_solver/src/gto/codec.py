from __future__ import annotations

from typing import Iterable


RANK_ORDER = {rank: index for index, rank in enumerate("23456789TJQKA", start=2)}
VALID_SUITS = {"c", "d", "h", "s"}
STACK_BUCKETS = (50, 100, 200)
POSTFLOP_SIZE_BUCKETS = (25, 33, 50, 75, 100, 150, 250)


def canonicalize_card(card: str) -> str:
    if not isinstance(card, str) or len(card) != 2:
        raise ValueError(f"Invalid card token: {card!r}")

    rank = card[0].upper()
    suit = card[1].lower()
    if rank not in RANK_ORDER or suit not in VALID_SUITS:
        raise ValueError(f"Invalid card token: {card!r}")
    return f"{rank}{suit}"


def canonicalize_cards(cards: Iterable[str]) -> list[str]:
    return [canonicalize_card(card) for card in cards]


def ensure_no_duplicate_cards(my_hand: list[str], board: list[str]) -> None:
    cards = my_hand + board
    if len(set(cards)) != len(cards):
        raise ValueError("Duplicate cards are not allowed across hand and board")


def infer_street(board: list[str]) -> str:
    length = len(board)
    if length == 0:
        return "preflop"
    if length == 3:
        return "flop"
    if length == 4:
        return "turn"
    if length == 5:
        return "river"
    raise ValueError("Board length must be 0, 3, 4, or 5")


def bucket_stack(effective_stack_bb: float) -> int:
    return min(STACK_BUCKETS, key=lambda bucket: abs(bucket - effective_stack_bb))


def normalize_position(position: str, table_size: int, warnings: list[str]) -> str:
    normalized = position.upper()

    if normalized == "MP":
        mapped = "LJ" if table_size == 9 else "HJ"
        warnings.append(f"position defaulted: MP->{mapped}")
        return mapped

    canonical_by_table_size = {
        6: {"UTG", "HJ", "CO", "BTN", "SB", "BB", "UNKNOWN"},
        9: {"UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB", "BB", "UNKNOWN"},
    }

    if normalized not in canonical_by_table_size[table_size]:
        raise ValueError(f"Invalid position {position!r} for table_size={table_size}")

    return normalized


def _sort_cards(cards: list[str]) -> list[str]:
    return sorted(
        cards,
        key=lambda card: (RANK_ORDER[card[0]], card[1]),
        reverse=True,
    )


def preflop_hand_key(my_hand: list[str]) -> str:
    first, second = _sort_cards(my_hand)
    first_rank, second_rank = first[0], second[0]
    if first_rank == second_rank:
        return f"{first_rank}{second_rank}"

    suited_suffix = "s" if first[1] == second[1] else "o"
    return f"{first_rank}{second_rank}{suited_suffix}"


def postflop_hand_key(my_hand: list[str]) -> str:
    sorted_cards = _sort_cards(my_hand)
    return "".join(sorted_cards)


def board_cards_key(board: list[str]) -> str | None:
    if not board:
        return None
    return "-".join(board)


def classify_board_texture(board: list[str]) -> str:
    if not board:
        return "preflop"

    ranks = [RANK_ORDER[card[0]] for card in board]
    suits = [card[1] for card in board]
    unique_suits = len(set(suits))
    highest_rank = max(ranks)
    broadway_density = sum(rank >= RANK_ORDER["T"] for rank in ranks)
    rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}
    sorted_unique_ranks = sorted(set(ranks))

    if highest_rank == RANK_ORDER["A"]:
        high_rank_bucket = "ace_high"
    elif highest_rank >= RANK_ORDER["T"]:
        high_rank_bucket = "broadway_high"
    elif highest_rank >= RANK_ORDER["7"]:
        high_rank_bucket = "middle_high"
    else:
        high_rank_bucket = "low_high"

    max_count = max(rank_counts.values())
    if max_count >= 3:
        pairedness = "trips"
    elif max_count == 2:
        pairedness = "paired"
    else:
        pairedness = "unpaired"

    if unique_suits == 1:
        suit_texture = "monotone"
    elif unique_suits == len(board):
        suit_texture = "rainbow"
    else:
        suit_texture = "two_tone"

    if len(sorted_unique_ranks) >= 4 and any(
        sorted_unique_ranks[index + 3] - sorted_unique_ranks[index] <= 4
        for index in range(len(sorted_unique_ranks) - 3)
    ):
        connectivity = "four_to_straight"
    else:
        gaps = [
            sorted_unique_ranks[index + 1] - sorted_unique_ranks[index]
            for index in range(len(sorted_unique_ranks) - 1)
        ]
        if gaps and max(gaps) <= 1:
            connectivity = "connected"
        elif gaps and max(gaps) <= 3:
            connectivity = "semi_connected"
        else:
            connectivity = "disconnected"

    return (
        f"{high_rank_bucket}|{pairedness}|{suit_texture}|"
        f"{connectivity}|{broadway_density}"
    )


def infer_options(
    street: str,
    current_bet_to_call_bb: float,
    actions_history: list[dict],
) -> list[str]:
    if current_bet_to_call_bb > 0:
        return ["fold", "call", "raise"]

    if street == "preflop":
        current_street_actions = []
        for item in actions_history:
            if item.get("street", "").lower() == "preflop":
                current_street_actions = item.get("actions", [])
                break
        if current_street_actions:
            return ["check", "raise"]
        return ["fold", "raise"]

    return ["check", "bet"]


def _format_bb_amount(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _closest_postflop_bucket(percent: float) -> int:
    return min(POSTFLOP_SIZE_BUCKETS, key=lambda bucket: abs(bucket - percent))


def normalize_action_token(
    token: str,
    street: str,
    pot_size_bb: float,
    current_bet_to_call_bb: float,
) -> str:
    if token == "hero_to_act":
        return token

    if token in {"fold", "call", "check"}:
        return token

    if token.startswith("raise_") and token.endswith("bb"):
        raw_amount = float(token[len("raise_") : -len("bb")])
        if street == "preflop":
            return f"raise_{_format_bb_amount(raw_amount)}bb"
        denominator = current_bet_to_call_bb if current_bet_to_call_bb > 0 else pot_size_bb
        denominator = denominator if denominator > 0 else 1.0
        bucket = _closest_postflop_bucket((raw_amount / denominator) * 100)
        return f"raise_{bucket}p"

    if token.startswith("bet_") and token.endswith("bb"):
        raw_amount = float(token[len("bet_") : -len("bb")])
        if street == "preflop":
            return f"bet_{_format_bb_amount(raw_amount)}bb"
        denominator = pot_size_bb if pot_size_bb > 0 else 1.0
        bucket = _closest_postflop_bucket((raw_amount / denominator) * 100)
        return f"bet_{bucket}p"

    return token


def normalize_actions_history(
    actions_history: list[dict],
    street: str,
    pot_size_bb: float,
    current_bet_to_call_bb: float,
) -> str:
    if not actions_history:
        return f"{street}:hero_to_act"

    parts: list[str] = []
    for item in actions_history:
        item_street = item.get("street", "").lower()
        actions = item.get("actions", [])
        normalized_actions = [
            normalize_action_token(action, item_street, pot_size_bb, current_bet_to_call_bb)
            for action in actions
        ]
        parts.append(f"{item_street}:{'-'.join(normalized_actions)}")
    return "/".join(parts)


def semantic_action_history_candidates(
    street: str,
    position: str,
    actions_history: list[dict],
    normalized_action_history_key: str,
) -> list[str]:
    candidates = [normalized_action_history_key]

    preflop_actions: list[str] = []
    flop_actions: list[str] = []
    for item in actions_history:
        item_street = item.get("street", "").lower()
        if item_street == "preflop":
            preflop_actions = item.get("actions", [])
        elif item_street == "flop":
            flop_actions = item.get("actions", [])

    if street == "preflop" and not preflop_actions:
        candidates.append("RFI")
    elif street == "flop":
        if (
            position == "BTN"
            and preflop_actions
            and preflop_actions[0].startswith("raise_")
            and "call" in preflop_actions
            and flop_actions == ["hero_to_act"]
        ):
            candidates.append("BTN_vs_BB_SRP_cbet")
        if (
            position == "BB"
            and preflop_actions
            and preflop_actions[0].startswith("raise_")
            and "call" in preflop_actions
            and flop_actions
            and flop_actions[0].startswith("bet_")
            and flop_actions[-1] == "hero_to_act"
        ):
            candidates.append("BB_vs_BTN_SRP_vs_cbet")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped
