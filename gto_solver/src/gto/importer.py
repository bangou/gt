from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


FLAT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gto_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_size INTEGER NOT NULL,
    position TEXT NOT NULL,
    effective_stack_bb INTEGER NOT NULL,
    street TEXT NOT NULL,
    hand_key TEXT NOT NULL,
    board_texture_key TEXT NOT NULL DEFAULT 'none',
    action_history_key TEXT NOT NULL,
    action TEXT NOT NULL,
    size_bb REAL,
    probability REAL NOT NULL,
    source TEXT,
    notes TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gto_strategies_unique
ON gto_strategies (
    table_size,
    position,
    effective_stack_bb,
    street,
    hand_key,
    board_texture_key,
    action_history_key,
    action,
    IFNULL(size_bb, -1)
);
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(FLAT_SCHEMA_SQL)
    connection.commit()
    return connection


def import_csv_to_db(connection: sqlite3.Connection, csv_path: str | Path) -> int:
    insert_sql = """
        INSERT OR IGNORE INTO gto_strategies
        (table_size, position, effective_stack_bb, street, hand_key, board_texture_key,
         action_history_key, action, size_bb, probability, source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    before = connection.total_changes
    rows: list[tuple] = []
    with Path(csv_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            table_size_value = row.get("table_size", "")
            if not table_size_value or table_size_value.startswith("#"):
                continue
            size_value = (row.get("size_bb") or "").strip()
            rows.append(
                (
                    int(table_size_value),
                    (row.get("position") or "").strip(),
                    int(row.get("effective_stack_bb") or 0),
                    (row.get("street") or "").strip(),
                    (row.get("hand_key") or "").strip(),
                    (row.get("board_texture_key") or "none").strip() or "none",
                    (row.get("action_history_key") or "").strip(),
                    (row.get("action") or "").strip(),
                    None if size_value in {"", "NULL", "null"} else float(size_value),
                    float(row.get("probability") or 0.0),
                    (row.get("source") or "").strip(),
                    (row.get("notes") or "").strip(),
                )
            )
    connection.executemany(insert_sql, rows)
    connection.commit()
    return connection.total_changes - before


def import_jsonl_to_db(connection: sqlite3.Connection, jsonl_path: str | Path) -> int:
    insert_sql = """
        INSERT OR IGNORE INTO gto_strategies
        (table_size, position, effective_stack_bb, street, hand_key, board_texture_key,
         action_history_key, action, size_bb, probability, source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    before = connection.total_changes
    rows: list[tuple] = []
    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            size_value = row.get("size_bb")
            rows.append(
                (
                    int(row["table_size"]),
                    row["position"],
                    int(row["effective_stack_bb"]),
                    row["street"],
                    row["hand_key"],
                    row.get("board_texture_key", "none") or "none",
                    row["action_history_key"],
                    row["action"],
                    None if size_value in {"NULL", "null"} else size_value,
                    float(row["probability"]),
                    row.get("source", ""),
                    row.get("notes", ""),
                )
            )
    connection.executemany(insert_sql, rows)
    connection.commit()
    return connection.total_changes - before
