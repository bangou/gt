from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class NormalizedRequest:
    table_size: int
    position: str
    effective_stack_bb: float
    stack_bucket: int
    my_hand: list[str]
    hand_key: str
    board: list[str] = field(default_factory=list)
    board_cards_key: str | None = None
    board_texture_key: str = "preflop"
    pot_size_bb: float = 0.0
    current_bet_to_call_bb: float = 0.0
    actions_history: list[dict] = field(default_factory=list)
    action_history_key: str = "preflop:hero_to_act"
    action_history_candidates: list[str] = field(default_factory=list)
    players_remaining: int = 2
    options: list[str] = field(default_factory=list)
    raise_sizes_allowed: list[float] = field(default_factory=list)
    street: str = "preflop"
    warnings: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)

    def to_debug_dict(self) -> dict:
        return asdict(self)
