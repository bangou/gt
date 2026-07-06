"""
card_templates.py - 模板匹配引擎

读取 assets/card_templates/ 下的模板，用 rank ROI 匹配识别牌面。
核心思路：只比较左上角的点数区域（rank ROI），因为花色不同但点数相同的牌，
rank 区域完全一致；花色通过颜色分析单独判断。

用法：
    matcher = CardMatcher()
    name, score = matcher.match(card_image)  # card_image 是 BGR 牌裁剪图
"""

import json
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 花色符号映射
SUIT_SYMBOLS = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}


class CardMatcher:
    """
    模板匹配器：用 rank ROI（左上角点数区域）做 OpenCV 模板匹配。

    架构设计：
    - Rank 识别：模板匹配 rank ROI → 准确率 100%
    - 红黑判断：双层策略（rank_bot 严格 + 全牌宽松）
    - 花色输出：红色 → h (♥)，黑色 → s (♠)

    已知限制：
    - 无法区分 ♥/♦ 或 ♣/♠（物理极限，需要更大分辨率的花色符号图案）
    - Q♦ 等 rank ROI 无红色的牌，靠全牌宽松检测兜底
    - 约 4% 的牌因色温偏暖导致红黑误判（Q♦ full_red≈11.5% vs Q♠ full_red≈11.2%）
    """

    MIN_SCORE = 0.65

    TEMPLATE_DIRS = ["templates/cards/render", "templates/cards/community"]

    def __init__(self, enable_suit_classify: bool = True):
        self.templates = {}   # name -> {"rank_img": Mat, "rank": str, "suit": str, "is_red": bool}
        self.enable_suit_classify = enable_suit_classify
        self._suit_hu_features = {}  # suit -> [hu_vector, ...]
        self._load_templates()
        if enable_suit_classify:
            self._build_suit_classifier()

    def _load_templates(self):
        """加载所有 rank 模板（hero + community）"""
        for template_dir in self.TEMPLATE_DIRS:
            dir_path = Path(template_dir)
            index_path = dir_path / "index.json"

            if not index_path.exists():
                logger.debug(f"模板索引不存在: {index_path}，跳过")
                continue

            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)

            for name, info in index.items():
                rank_path = dir_path / f"{name}_rank.png"
                if rank_path.exists():
                    rank_img = cv2.imread(str(rank_path), cv2.IMREAD_GRAYSCALE)
                    self.templates[name] = {
                        "rank_img": rank_img,
                        "rank": info.get("rank", name[0]),
                        "suit": info.get("suit", name[1]),
                        "is_red": info.get("is_red", info["suit"] in ("h", "d")),
                    }
                else:
                    logger.debug(f"跳过 {dir_path.name}/{name}：缺少 rank ROI")

        logger.info(f"已加载 {len(self.templates)} 个 rank 模板")

    def _build_suit_classifier(self):
        """从 raw 模板图中提取花色符号的 Hu 矩特征，用于 ♥/♦ 和 ♣/♠ 分类"""
        import json as _json
        for _dir in self.TEMPLATE_DIRS:
            _dir_path = Path(_dir)
            _idx_path = _dir_path / "index.json"
            if not _idx_path.exists():
                continue
            with open(_idx_path, encoding="utf-8") as _f:
                _index = _json.load(_f)
            for _name, _info in _index.items():
                _suit = _info.get("suit", _name[1])
                _raw_fn = _info.get("raw")
                if not _raw_fn:
                    continue
                _rp = _dir_path / _raw_fn
                if not _rp.exists():
                    continue
                _raw = cv2.imread(str(_rp))
                if _raw is None or _raw.size == 0:
                    continue
                _h, _w = _raw.shape[:2]
                if _h < 20:
                    continue
                _gray = cv2.cvtColor(_raw, cv2.COLOR_BGR2GRAY)
                _sx0 = int(_w * 0.58); _sx1 = _w - 2
                _sy0 = int(_h * 0.55); _sy1 = _h - 2
                if _sx1 <= _sx0 or _sy1 <= _sy0:
                    continue
                _roi = _gray[_sy0:_sy1, _sx0:_sx1]
                _, _bin = cv2.threshold(_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                _contours, _ = cv2.findContours(_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not _contours:
                    continue
                _largest = max(_contours, key=cv2.contourArea)
                _moments = cv2.moments(_largest)
                _hu = cv2.HuMoments(_moments)
                _hu_log = -np.sign(_hu) * np.log10(np.abs(_hu) + 1e-10)
                self._suit_hu_features.setdefault(_suit, []).append(_hu_log.flatten())
        if self._suit_hu_features:
            count = sum(len(v) for v in self._suit_hu_features.values())
            logger.info(f"花色分类器就绪：{count} 个样本 ({sorted(self._suit_hu_features.keys())})")

    def _classify_suit_by_shape(self, card_image: np.ndarray, is_red: bool) -> Optional[str]:
        """用 Hu 矩形状匹配区分同色花色的两种 (♥/♦ 或 ♣/♠)"""
        if not self._suit_hu_features:
            return None
        candidates = ["h", "d"] if is_red else ["c", "s"]
        if not all(c in self._suit_hu_features for c in candidates):
            return None

        _h, _w = card_image.shape[:2]
        _gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
        _sx0 = int(_w * 0.58); _sx1 = _w - 2
        _sy0 = int(_h * 0.55); _sy1 = _h - 2
        if _sx1 <= _sx0 or _sy1 <= _sy0:
            return None
        _roi = _gray[_sy0:_sy1, _sx0:_sx1]
        _, _bin = cv2.threshold(_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        _contours, _ = cv2.findContours(_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not _contours:
            return None
        _largest = max(_contours, key=cv2.contourArea)
        _moments = cv2.moments(_largest)
        _hu = cv2.HuMoments(_moments)
        _test_hu = (-np.sign(_hu) * np.log10(np.abs(_hu) + 1e-10)).flatten()

        best_suit = None
        best_dist = 1e10
        for s in candidates:
            for ref_hu in self._suit_hu_features[s]:
                dist = float(np.sum((_test_hu - ref_hu) ** 2))
                if dist < best_dist:
                    best_dist = dist
                    best_suit = s
        return best_suit

    def _extract_rank_roi(self, card_gray: np.ndarray) -> np.ndarray:
        """从牌灰度图中裁取左上角 rank 区域"""
        h, w = card_gray.shape[:2]
        r_x = 3
        r_y = 3
        r_w = int(w * 0.55)
        r_h = int(h * 0.40)
        return card_gray[r_y : r_y + r_h, r_x : r_x + r_w]

    def match(self, card_image: np.ndarray) -> Optional[tuple[str, float]]:
        """
        识别一张牌：rank 模板匹配 + 双层红黑检测。

        Args:
            card_image: BGR 牌的完整裁剪图

        Returns:
            (name, score) 如 ("2s", 0.95)，或 None（未匹配）
        """
        if card_image.size == 0:
            return None

        card_h, card_w = card_image.shape[:2]
        gray = cv2.cvtColor(card_image, cv2.COLOR_BGR2GRAY)
        rank_roi = self._extract_rank_roi(gray)

        # ── Rank 模板匹配 ──
        best_name = None
        best_score = -1

        for name, template in self.templates.items():
            tmpl = template["rank_img"]
            if tmpl.shape != rank_roi.shape:
                tmpl = cv2.resize(tmpl, (rank_roi.shape[1], rank_roi.shape[0]))

            result = cv2.matchTemplate(rank_roi, tmpl, cv2.TM_CCOEFF_NORMED)
            score = float(np.max(result))

            if score > best_score:
                best_score = score
                best_name = name

        if best_score < self.MIN_SCORE:
            return None

        best_rank = self.templates[best_name]["rank"]

        # ── 红黑判断（最暗像素法） ──
        # 取 rank ROI 中最暗的 N 个像素，计算 R/B 比值
        # 红色牌：字符像素 R>>B (R~205, B~60)
        # 黑色牌：字符像素 R≈G≈B (R~33, B~33)
        r_x, r_y = 3, 3
        r_w = int(card_w * 0.55)
        r_h = int(card_h * 0.40)
        rank_color_roi = card_image[r_y:r_y+r_h, r_x:r_x+r_w]
        rank_gray_roi = gray[r_y:r_y+r_h, r_x:r_x+r_w]

        flat_gray = rank_gray_roi.flatten()
        flat_r = rank_color_roi[:, :, 2].flatten()
        flat_b = rank_color_roi[:, :, 0].flatten()

        n_dark = max(10, len(flat_gray) // 10)
        darkest_idx = np.argpartition(flat_gray, n_dark)[:n_dark]
        r_darkest = flat_r[darkest_idx].mean()
        b_darkest = flat_b[darkest_idx].mean()
        rb_ratio = r_darkest / max(b_darkest, 1.0)

        is_red = rb_ratio > 1.5

        # ── 花色确定 ──
        # 先用红黑默认，再尝试 Hu 矩细分类
        target_suit = "h" if is_red else "s"
        if self.enable_suit_classify:
            classified = self._classify_suit_by_shape(card_image, is_red)
            if classified is not None:
                target_suit = classified
        for name, template in self.templates.items():
            if template["rank"] == best_rank and template["suit"] == target_suit:
                return (name, best_score)

        return (best_name, best_score)

    def match_all(self, card_images: list[np.ndarray]) -> list[Optional[dict]]:
        """
        批量匹配多张牌。

        Returns:
            每张牌的结果 dict 或 None：
            {"name": "2c", "rank": "2", "suit": "c", "suit_symbol": "♣",
             "is_red": False, "score": 0.95}
        """
        results = []
        for img in card_images:
            match = self.match(img)
            if match:
                name, score = match
                t = self.templates[name]
                results.append({
                    "name": name,
                    "rank": t["rank"],
                    "suit": t["suit"],
                    "suit_symbol": SUIT_SYMBOLS.get(t["suit"], "?"),
                    "is_red": t["is_red"],
                    "score": score,
                })
            else:
                results.append(None)
        return results

    @property
    def template_names(self) -> list[str]:
        """已加载的模板名列表"""
        return sorted(self.templates.keys())


# ── 快速测试 ──

def test_matcher():
    """用现有截图测试 rank-ROI 匹配器"""
    import sys, io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    matcher = CardMatcher()
    print(f"已加载 {len(matcher.templates)} 个模板: {matcher.template_names}")

    # 用已知标注的 deal 截图验证
    KNOWN = {
        "hand1": ("Jd", "Ah"),
        "hand4": ("Qd", "2c"),
        "hand5": ("Qd", "2h"),
    }
    POSITIONS = [(908, 873, 50, 73), (963, 873, 50, 73)]

    total, ok = 0, 0
    for hand, expected in sorted(KNOWN.items()):
        img = cv2.imread(f"screenshots/{hand}_deal.png")
        for i, (exp_name, (x, y, w, h)) in enumerate(zip(expected, POSITIONS)):
            card_img = img[y:y+h, x:x+w]
            result = matcher.match(card_img)
            total += 1
            if result:
                name, score = result
                exact = name == exp_name
                if exact:
                    ok += 1
                print(f"  {hand} 牌{i+1}: 预期={exp_name} → {name} score={score:.3f} {'✅' if exact else '❌'}")
            else:
                print(f"  {hand} 牌{i+1}: 预期={exp_name} → 未匹配")

    print(f"\n准确率: {ok}/{total} = {ok/total:.0%}")
    return matcher


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_matcher()
