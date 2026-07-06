"""
card_recognizer.py - 单张牌识别

识别流程（多层 fallback）：
  1. 模板匹配（card_templates.CardMatcher）—— 主要方法，用 rank ROI 匹配
  2. OCR（pytesseract）—— 辅助验证
  3. 颜色分析 —— 红色/黑色判断，作为最终回退

用法：
    recognizer = CardRecognizer()
    result = recognizer.recognize(card_image)  # RecognizedCard
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Suit(Enum):
    HEARTS = "h"      # 红桃
    DIAMONDS = "d"    # 方块
    CLUBS = "c"       # 梅花
    SPADES = "s"      # 黑桃


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


@dataclass
class RecognizedCard:
    """识别出的一张牌"""
    rank: Optional[Rank] = None
    suit: Optional[Suit] = None
    is_red: bool = False
    confidence: float = 0.0
    image: Optional[np.ndarray] = None

    @property
    def suit_str(self) -> str:
        if self.suit is None:
            return "?"
        suit_symbols = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
        return suit_symbols.get(self.suit.value, "?")

    @property
    def rank_str(self) -> str:
        return self.rank.value if self.rank else "?"

    def __str__(self):
        return f"{self.rank_str}{self.suit_str}"

    def __repr__(self):
        return f"Card({self})"


class CardRecognizer:
    """
    单张牌识别器。

    识别流程：模板匹配 → OCR → 颜色分析（多层 fallback）
    """

    def __init__(self):
        from recognition.card_templates import CardMatcher
        self._matcher = CardMatcher()

    def recognize(self, card_image: np.ndarray) -> RecognizedCard:
        """
        识别单张牌。

        Args:
            card_image: BGR 牌的裁剪图

        Returns:
            RecognizedCard（含花色、点数、置信度）
        """
        if card_image.size == 0 or card_image.shape[0] < 10 or card_image.shape[1] < 10:
            return RecognizedCard(confidence=0.0)

        # ── 1. 模板匹配（主要方法）──
        match_result = self._matcher.match(card_image)
        if match_result:
            name, score = match_result
            t = self._matcher.templates[name]
            rank = self._rank_from_char(t["rank"])
            suit = self._suit_from_char(t["suit"])
            if rank and suit:
                return RecognizedCard(
                    rank=rank,
                    suit=suit,
                    is_red=t["is_red"],
                    confidence=score,
                    image=card_image.copy(),
                )

        # ── 2. OCR 回退 ──
        rank, suit, ocr_conf = None, None, 0.5
        try:
            text = self._ocr_card(card_image)
            if text:
                rank, suit = self._parse_text(text)
                ocr_conf = 0.8
        except Exception:
            pass

        if rank and suit:
            return RecognizedCard(
                rank=rank,
                suit=suit,
                is_red=suit in (Suit.HEARTS, Suit.DIAMONDS) if suit else False,
                confidence=ocr_conf,
                image=card_image.copy(),
            )

        # ── 3. 最终回退：颜色分析 ──
        h, w = card_image.shape[:2]
        hsv = cv2.cvtColor(card_image, cv2.COLOR_BGR2HSV)
        red_mask = cv2.inRange(hsv, (0, 40, 40), (10, 255, 255))
        red_mask |= cv2.inRange(hsv, (160, 40, 40), (180, 255, 255))
        red_ratio = np.sum(red_mask > 0) / (h * w)
        is_red = red_ratio > 0.05

        return RecognizedCard(
            rank=rank,
            suit=suit,
            is_red=is_red,
            confidence=0.3 if rank else 0.1,
            image=card_image.copy(),
        )

    def _rank_from_char(self, char: str) -> Optional[Rank]:
        """单字符 rank 转 Rank 枚举"""
        char = char.upper()
        for r in Rank:
            if r.value == char:
                return r
        return None

    def _suit_from_char(self, char: str) -> Optional[Suit]:
        """单字符 suit 转 Suit 枚举"""
        char = char.lower()
        for s in Suit:
            if s.value == char:
                return s
        return None

    def _ocr_card(self, card_image: np.ndarray) -> Optional[str]:
        """用 pytesseract 识别牌面文字"""
        try:
            import pytesseract

            # 预处理：放大 + 二值化
            gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

            # 识别左上角（点数+花色符号的位置）
            h, w = binary.shape[:2]
            corner = binary[0 : h // 2, 0 : w // 2]

            text = pytesseract.image_to_string(
                corner,
                config="--psm 10 -c tessedit_char_whitelist=AKQJT98765432",
            )
            return text.strip()

        except ImportError:
            return None
        except Exception as e:
            logger.debug(f"OCR 失败: {e}")
            return None

    def _parse_text(self, text: str) -> tuple[Optional[Rank], Optional[Suit]]:
        """解析 OCR 文本为花色和点数"""
        if not text:
            return None, None

        text = text.strip().upper()

        rank = None
        suit = None

        # 找点数
        for r in Rank:
            if r.value in text:
                rank = r
                break

        # 找花色符号（如果 OCR 能识别 Unicode 花色符号）
        if "♥" in text or "♡" in text:
            suit = Suit.HEARTS
        elif "♦" in text or "♢" in text:
            suit = Suit.DIAMONDS
        elif "♣" in text or "♧" in text:
            suit = Suit.CLUBS
        elif "♠" in text or "♤" in text:
            suit = Suit.SPADES

        return rank, suit

    def recognize_all(self, card_images: list[np.ndarray]) -> list[RecognizedCard]:
        """批量识别多张牌"""
        return [self.recognize(img) for img in card_images]


# ── 快速测试 ──

def test_recognizer_screenshots():
    """用已收集的截图测试识别器的模板匹配准确率"""
    import sys, io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    from pathlib import Path
    from src.recognition.card_detector import CardDetector

    recognizer = CardRecognizer()
    detector = CardDetector()

    deal_files = sorted(Path("screenshots").glob("hand*_deal.png"))
    # 排除无效截图（hand1-5 hero区域无内容）
    valid = [f for f in deal_files if f.stem not in
             ("hand1_deal", "hand2_deal", "hand3_deal", "hand4_deal", "hand5_deal")]

    total, ok = 0, 0
    for f in valid:
        img = cv2.imread(str(f))
        cards = detector.detect(img)
        classified = detector.classify_by_location(cards)
        hero_cards = [c for c in classified["hero"] if c.width > 30 and c.height > 40]

        print(f"\n{f.stem}: {len(hero_cards)} 张 hero 牌")
        for i, c in enumerate(hero_cards):
            rc = recognizer.recognize(c.image)
            total += 1
            if rc.rank and rc.suit:
                ok += 1
                status = "✅"
            elif rc.rank or rc.is_red is not None:
                status = "⚠️"
            else:
                status = "❌"
            print(f"  [{i}] ({c.x},{c.y}) {c.width}x{c.height} → {rc} "
                  f"({status} conf={rc.confidence:.2f})")

    print(f"\n准确率: {ok}/{total} = {ok/total:.0%}")
    return recognizer


def test_recognizer():
    """测试识别器（需要实时屏幕截图）"""
    from src.capture.screen_capture import ScreenCapture
    from src.recognition.card_detector import CardDetector

    cap = ScreenCapture()
    screenshot = cap.capture_monitor(1)

    detector = CardDetector()
    cards = detector.detect(screenshot)
    classified = detector.classify_by_location(cards)

    recognizer = CardRecognizer()
    hero_cards = [c.image for c in classified["hero"]]

    results = recognizer.recognize_all(hero_cards)
    print(f"Hero 手牌识别结果:")
    for i, rc in enumerate(results):
        color_str = "红色" if rc.is_red else "黑色"
        print(f"  牌{i + 1}: {rc} ({color_str}, 置信度{rc.confidence:.0%})")

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 优先用离线截图测试
    from pathlib import Path
    if Path("screenshots").exists() and list(Path("screenshots").glob("hand*_deal.png")):
        test_recognizer_screenshots()
    else:
        test_recognizer()
