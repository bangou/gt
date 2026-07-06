from __future__ import annotations

import sqlite3
from typing import Any

from .bootstrap import DB_PATH, bootstrap_database
from .models import NormalizedRequest


def ensure_database() -> str:
    bootstrap_database()
    return str(DB_PATH)


def lookup_strategy(normalized_request: NormalizedRequest) -> dict[str, Any] | None:
    ensure_database()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.cursor()

        def fetch_rows(board_keys: list[str], action_key: str) -> list[sqlite3.Row]:
            placeholders = ",".join("?" for _ in board_keys)
            query = f"""
                SELECT action, size_bb, probability, source, notes
                FROM gto_strategies
                WHERE table_size = ?
                  AND position = ?
                  AND effective_stack_bb = ?
                  AND street = ?
                  AND hand_key = ?
                  AND action_history_key = ?
                  AND board_texture_key IN ({placeholders})
                ORDER BY action, size_bb
            """
            params = [
                normalized_request.table_size,
                normalized_request.position,
                normalized_request.stack_bucket,
                normalized_request.street,
                normalized_request.hand_key,
                action_key,
                *board_keys,
            ]
            return cursor.execute(query, params).fetchall()

        board_keys = (
            ["none", normalized_request.board_texture_key]
            if normalized_request.street == "preflop"
            else [normalized_request.board_texture_key]
        )

        matched_action_key = None
        rows: list[sqlite3.Row] = []
        for action_key in normalized_request.action_history_candidates or [normalized_request.action_history_key]:
            rows = fetch_rows(board_keys, action_key)
            if rows:
                matched_action_key = action_key
                break

        if not rows:
            return None

        if matched_action_key and matched_action_key != normalized_request.action_history_key:
            normalized_request.fallbacks.append(
                f"action_history:{normalized_request.action_history_key}->{matched_action_key}"
            )

        actions = [
            {
                "action": row["action"],
                "size_bb": row["size_bb"],
                "probability": row["probability"],
            }
            for row in rows
        ]
        board_selector = "none" if normalized_request.street == "preflop" else normalized_request.board_texture_key
        matched_key = (
            f"{normalized_request.table_size}::{normalized_request.position}::"
            f"{normalized_request.stack_bucket}::{normalized_request.street}::"
            f"{normalized_request.hand_key}::{board_selector}::{matched_action_key}::"
            f"{normalized_request.players_remaining}"
        )
        synthetic_table_id = (
            f"{normalized_request.street}_{normalized_request.table_size}max_"
            f"{normalized_request.position.lower()}_{matched_action_key.lower()}_"
            f"{normalized_request.hand_key.lower()}_{normalized_request.stack_bucket}"
        )
        return {
            "table_id": synthetic_table_id,
            "matched_key": matched_key,
            "actions": actions,
            "source": rows[0]["source"],
        }
    finally:
        connection.close()
