from __future__ import annotations

import json

from .codec import (
    board_cards_key,
    bucket_stack,
    canonicalize_cards,
    classify_board_texture,
    ensure_no_duplicate_cards,
    infer_options,
    infer_street,
    normalize_actions_history,
    normalize_position,
    postflop_hand_key,
    preflop_hand_key,
    semantic_action_history_candidates,
)
from .models import NormalizedRequest
from .store import lookup_strategy


def _error_response(message: str, warnings: list[str] | None = None) -> str:
    return json.dumps(
        {
            "status": "error",
            "message": message,
            "strategy": {},
            "range_info": {},
            "debug": {
                "matched_table_id": None,
                "matched_key": None,
                "normalized_request": None,
                "fallbacks": [],
                "warnings": warnings or [],
            },
        }
    )


def normalize_request(payload: dict) -> NormalizedRequest:
    warnings: list[str] = []
    fallbacks: list[str] = []

    if "position" not in payload:
        raise ValueError("Missing required field: position")
    if "my_hand" not in payload:
        raise ValueError("Missing required field: my_hand")

    table_size = int(payload.get("table_size", 9))
    if "table_size" not in payload:
        warnings.append("default applied: table_size=9")
    if table_size not in {6, 9}:
        raise ValueError("table_size must be 6 or 9")

    effective_stack_bb = float(payload.get("effective_stack_bb", 100))
    if "effective_stack_bb" not in payload:
        warnings.append("default applied: effective_stack_bb=100")
    stack_bucket = bucket_stack(effective_stack_bb)
    if effective_stack_bb != stack_bucket:
        fallbacks.append(f"stack_bucket:{effective_stack_bb:g}->{stack_bucket}")

    board = canonicalize_cards(payload.get("board", []))
    if "board" not in payload:
        warnings.append("default applied: board=[]")

    actions_history = payload.get("actions_history", [])
    if "actions_history" not in payload:
        warnings.append("default applied: actions_history=[]")

    players_remaining = int(payload.get("players_remaining", 2))
    if "players_remaining" not in payload:
        warnings.append("default applied: players_remaining=2")
    if players_remaining != 2:
        raise ValueError("Only heads-up situations are supported in v1")

    my_hand = canonicalize_cards(payload["my_hand"])
    if len(my_hand) != 2:
        raise ValueError("my_hand must contain exactly two cards")
    ensure_no_duplicate_cards(my_hand, board)

    street = infer_street(board)
    position = normalize_position(str(payload["position"]), table_size, warnings)
    board_key = board_cards_key(board)
    texture_key = classify_board_texture(board)

    pot_size_bb = float(payload.get("pot_size_bb", 0.0))
    current_bet_to_call_bb = float(payload.get("current_bet_to_call_bb", 0.0))
    normalized_action_history_key = normalize_actions_history(
        actions_history=actions_history,
        street=street,
        pot_size_bb=pot_size_bb,
        current_bet_to_call_bb=current_bet_to_call_bb,
    )
    options = payload.get("options") or infer_options(street, current_bet_to_call_bb, actions_history)
    if "options" not in payload:
        warnings.append(f"default applied: options={options}")

    raise_sizes_allowed = [float(size) for size in payload.get("raise_sizes_allowed", [])]

    hand_key = preflop_hand_key(my_hand) if street == "preflop" else postflop_hand_key(my_hand)
    action_history_candidates = semantic_action_history_candidates(
        street=street,
        position=position,
        actions_history=actions_history,
        normalized_action_history_key=normalized_action_history_key,
    )

    return NormalizedRequest(
        table_size=table_size,
        position=position,
        effective_stack_bb=effective_stack_bb,
        stack_bucket=stack_bucket,
        my_hand=my_hand,
        hand_key=hand_key,
        board=board,
        board_cards_key=board_key,
        board_texture_key=texture_key,
        pot_size_bb=pot_size_bb,
        current_bet_to_call_bb=current_bet_to_call_bb,
        actions_history=actions_history,
        action_history_key=normalized_action_history_key,
        action_history_candidates=action_history_candidates,
        players_remaining=players_remaining,
        options=options,
        raise_sizes_allowed=raise_sizes_allowed,
        street=street,
        warnings=warnings,
        fallbacks=fallbacks,
    )


def _build_strategy_payload(actions: list[dict]) -> tuple[dict, str]:
    grouped: dict[str, dict] = {}
    recommended_action = ""
    best_probability = -1.0

    for row in actions:
        action = row["action"]
        size_bb = row["size_bb"]
        probability = float(row["probability"])
        entry = grouped.setdefault(action, {"prob": None, "sizes": []})
        if size_bb is None:
            entry["prob"] = probability
            if probability > best_probability:
                best_probability = probability
                recommended_action = action
        else:
            entry["sizes"].append({"size_bb": float(size_bb), "prob": probability})

    # Fallback: if no action has size_bb=None, pick the action with highest total probability
    if not recommended_action and grouped:
        best_total = -1.0
        for action, entry in grouped.items():
            total_prob = (entry["prob"] or 0) + sum(s["prob"] for s in entry["sizes"])
            if total_prob > best_total:
                best_total = total_prob
                recommended_action = action

    strategy: dict[str, object] = {}
    for action, entry in grouped.items():
        if entry["prob"] is not None:
            strategy[action] = entry["prob"]
        if entry["sizes"]:
            strategy[f"{action}_sizes"] = entry["sizes"]

    return strategy, recommended_action


def get_gto_strategy(json_input: str) -> str:
    try:
        payload = json.loads(json_input)
    except json.JSONDecodeError as exc:
        return _error_response(f"Malformed JSON: {exc.msg}")

    try:
        normalized = normalize_request(payload)
    except ValueError as exc:
        return _error_response(str(exc))

    match = lookup_strategy(normalized)
    if match is None:
        return json.dumps(
            {
                "status": "error",
                "message": "No strategy found for the normalized situation",
                "strategy": {},
                "range_info": {},
                "debug": {
                    "matched_table_id": None,
                    "matched_key": None,
                    "normalized_request": normalized.to_debug_dict(),
                    "fallbacks": normalized.fallbacks,
                    "warnings": normalized.warnings,
                },
            }
        )

    strategy, recommended_action = _build_strategy_payload(match["actions"])
    response = {
        "status": "success",
        "message": "",
        "strategy": strategy,
        "range_info": {
            "equity": 0.0,
            "range_advantage": 0.0,
            "nut_advantage": 0.0,
            "recommended_action": recommended_action,
        },
        "debug": {
            "matched_table_id": match["table_id"],
            "matched_key": match["matched_key"],
            "normalized_request": normalized.to_debug_dict(),
            "fallbacks": normalized.fallbacks,
            "warnings": normalized.warnings,
        },
    }
    return json.dumps(response)
