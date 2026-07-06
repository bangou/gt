"""
Card and GameState data models for PokerGTO Assistant.

Core type definitions used across all modules.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Suit & Rank ──

class Suit(Enum):
    SPADES = "s"
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"


class Rank(Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


@dataclass(frozen=True)
class Card:
    """一张扑克牌"""
    rank: Rank
    suit: Suit

    def __str__(self):
        return f"{self.rank.value}{self.suit.value}"

    def __repr__(self):
        return f"Card({self.rank.value}{self.suit.value})"


# ── Street ──

class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


# ── Action ──

class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"


@dataclass
class Action:
    """一个行动记录"""
    player_position: int
    action_type: ActionType
    amount: float = 0.0


# ── Seat ──

@dataclass
class Seat:
    """一个座位信息"""
    position: int          # 0-5
    name: str = ""
    stack: float = 0.0
    last_bet: float = 0.0
    is_active: bool = True
    cards: list = field(default_factory=list)  # 只有 hero 能看到


# ── Suggestion ──

@dataclass
class Suggestion:
    """策略建议输出"""
    action: ActionType = ActionType.FOLD
    amount: float = 0.0
    confidence: float = 0.0       # 0-1
    equity: float = 0.0           # 当前胜率
    explanation: str = ""


# ── GameState ──

@dataclass
class GameState:
    """一局牌的完整状态快照"""
    hand_number: int = 0
    street: Street = Street.PREFLOP
    dealer_position: int = 0
    hero_position: int = 0

    seats: list = field(default_factory=list)       # list[Seat]
    hero_cards: list = field(default_factory=list)  # list[Card]
    community_cards: list = field(default_factory=list)  # list[Card]

    pot: float = 0.0
    current_bet: float = 0.0      # 当前最大下注
    current_player: int = -1      # 当前该谁

    last_actions: list = field(default_factory=list)  # list[Action]

    suggestion: Optional[Suggestion] = None
