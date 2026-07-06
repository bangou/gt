"""
临时数据库 — 识别期间存储牌面裁剪图，关闭时自动去重入库。

用法:
    db = TempDB("data/temp/temp_cards.db")
    db.save_card("Ah", "A", "h", True, 0.95, png_bytes, 908, 873, 50, 73)
    ...
    new_count = db.dedup_and_merge()  # 关闭时调用
    db.clear()
"""

from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS temp_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    rank TEXT NOT NULL,
    suit TEXT NOT NULL,
    is_red INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.0,
    source_screenshot TEXT DEFAULT '',
    position_x INTEGER DEFAULT 0,
    position_y INTEGER DEFAULT 0,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    image_blob BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_temp_cards_name ON temp_cards(card_name);
"""

_REAL_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "cards" / "real"    # 真正截图裁剪库
_RENDER_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "cards" / "render"  # 渲染模板库


class TempDB:
    """SQLite 临时牌面数据库。"""

    def __init__(self, db_path: str | Path = "data/temp/temp_cards.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── connection management ──────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    # ── CRUD ────────────────────────────────────────────────────────

    def save_card(
        self,
        card_name: str,
        rank: str,
        suit: str,
        is_red: bool,
        confidence: float,
        card_image: np.ndarray,
        position_x: int = 0,
        position_y: int = 0,
        width: int = 0,
        height: int = 0,
        source: str = "",
    ) -> int:
        """保存一张牌面裁剪图到临时库。返回 row id。"""
        _, png_bytes = cv2.imencode(".png", card_image)
        blob = png_bytes.tobytes()

        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO temp_cards
                   (card_name, rank, suit, is_red, confidence, source_screenshot,
                    position_x, position_y, width, height, image_blob)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (card_name, rank, suit, int(is_red), confidence, source,
                 position_x, position_y, width, height, blob),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_all_cards(self) -> list[dict]:
        """获取临时库中所有牌面记录。"""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM temp_cards ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM temp_cards").fetchone()[0]
        finally:
            conn.close()

    def clear(self) -> None:
        """清空临时表（关闭时调用，入库完成后）。"""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM temp_cards")
            conn.commit()
        finally:
            conn.close()

    # ── 去重入库 ───────────────────────────────────────────────────

    def dedup_and_merge(self) -> int:
        """
        将临时库中的牌面与正式模板库比对，新牌自动入库。

        规则:
        - 对每张临时牌, 用正式库的指标对比
        - 同名(card_name)且已有 raw 模板 → 跳过
        - 新名或正式库缺乏 real 的 → 存入 templates/cards/real/<name>.png
        - 不修改 render 库（render 库由人工/脚本从 GTO1 同步）

        Returns: 新增入库的牌面数量
        """
        real_index_path = _REAL_DIR / "index.json"

        # 确保 real 目录和 index 存在
        _REAL_DIR.mkdir(parents=True, exist_ok=True)
        if not real_index_path.exists():
            with open(real_index_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

        with open(real_index_path, "r", encoding="utf-8") as f:
            real_index = json.load(f)

        cards = self.get_all_cards()
        new_count = 0

        for card in cards:
            name = card["card_name"]
            if not name or len(name) < 2:
                continue

            # real 库已有 → 跳过
            if name in real_index:
                continue

            # 解码图像
            blob = card["image_blob"]
            if not blob:
                continue
            img_array = np.frombuffer(blob, np.uint8)
            card_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if card_img is None or card_img.size == 0:
                continue

            h, w = card_img.shape[:2]
            if h < 20 or w < 15:
                continue

            # 存入 real 库：只存原始截图裁剪（raw），不做 render 处理
            cv2.imwrite(str(_REAL_DIR / f"{name}.png"), card_img)

            real_index[name] = {
                "file": f"{name}.png",
                "rank": card["rank"],
                "suit": card["suit"],
                "is_red": bool(card["is_red"]),
                "confidence": card["confidence"],
                "width": w,
                "height": h,
            }
            new_count += 1

        # 写回 real index.json
        with open(real_index_path, "w", encoding="utf-8") as f:
            json.dump(real_index, f, indent=2, ensure_ascii=False)

        return new_count
