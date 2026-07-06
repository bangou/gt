"""
GameState → GTO Query JSON 桥接。

将识别结果（手牌、公共牌、位置、底池/下注金额）组装成
符合 GTO 查询协议的标准 JSON。

用法:
    bridge = GameStateBridge()
    json_str = bridge.build_query(
        hero_cards=["Ah", "Kh"],
        community_cards=["Qh", "Jd", "4s"],
        position="BTN",
        pot_size_bb=15.0,
        current_bet_to_call_bb=5.0,
        ...
    )
"""

from __future__ import annotations

import json


class GameStateBridge:
    """识别结果 → GTO 查询协议 JSON。"""

    def __init__(self):
        self._last_state: dict | None = None

    def build_query(
        self,
        *,
        hero_cards: list[str],
        community_cards: list[str] | None = None,
        table_size: int = 6,
        position: str = "BTN",
        effective_stack_bb: float = 100.0,
        pot_size_bb: float = 0.0,
        current_bet_to_call_bb: float = 0.0,
        actions_history: list[dict] | None = None,
        players_remaining: int | None = None,
        raise_sizes_allowed: list[float] | None = None,
    ) -> str:
        """
        构建 GTO 查询 JSON。

        Args:
            hero_cards: 手牌，如 ["Ah", "Kh"]。
            community_cards: 公共牌，如 ["Qh", "Jd", "4s"]。
            table_size: 桌人数（6 或 9）。
            position: 标准位置字符串。
            effective_stack_bb: 有效筹码（BB 数）。
            pot_size_bb: 底池大小（BB 数）。
            current_bet_to_call_bb: 当前需要跟注的金额（BB 数）。
            actions_history: 行动历史。
            players_remaining: 剩余玩家数。
            raise_sizes_allowed: 允许的加注尺度。

        Returns:
            符合 GTO 查询协议的 JSON 字符串。
        """
        board_len = len(community_cards or [])

        # 推断 options
        if current_bet_to_call_bb > 0:
            options = ["fold", "call", "raise"]
        elif board_len == 0:
            options = ["fold", "raise"]
        else:
            options = ["check", "bet"]

        # 推断 players_remaining
        if players_remaining is None:
            players_remaining = 2  # 默认 HU

        payload: dict = {
            "table_size": table_size,
            "position": position,
            "effective_stack_bb": effective_stack_bb,
            "my_hand": hero_cards,
            "board": community_cards or [],
            "pot_size_bb": pot_size_bb,
            "current_bet_to_call_bb": current_bet_to_call_bb,
            "actions_history": actions_history or [],
            "players_remaining": players_remaining,
            "options": options,
            "raise_sizes_allowed": raise_sizes_allowed or [],
        }

        self._last_state = payload
        return json.dumps(payload, ensure_ascii=False)

    def build_from_recognized(
        self,
        hero_names: list[str],
        community_names: list[str],
        position: str = "BTN",
        table_size: int = 6,
        pot_size_bb: float = 0.0,
        bet_to_call_bb: float = 0.0,
    ) -> str:
        """
        从识别结果快速构建查询（便捷方法）。

        Args:
            hero_names: 识别出的手牌名，如 ["Ah", "Kh"]。
            community_names: 识别出的公共牌名。
            position: 位置字符串。
            table_size: 桌人数。
            pot_size_bb: 底池（BB）。
            bet_to_call_bb: 跟注额（BB）。

        Returns:
            GTO 查询 JSON 字符串。
        """
        return self.build_query(
            hero_cards=hero_names,
            community_cards=community_names,
            table_size=table_size,
            position=position,
            pot_size_bb=pot_size_bb,
            current_bet_to_call_bb=bet_to_call_bb,
        )

    def query_gto(self, query_json: str) -> dict | None:
        """
        调用 GTO 解算库查询策略。

        Returns:
            解析后的 GTO 响应 dict，失败返回 None。
        """
        try:
            from gto.api import get_gto_strategy
            response_str = get_gto_strategy(query_json)
            return json.loads(response_str)
        except Exception:
            return None

    @property
    def last_state(self) -> dict | None:
        """最近一次构建的查询 payload。"""
        return self._last_state
