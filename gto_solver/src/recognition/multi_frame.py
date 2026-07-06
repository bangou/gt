"""
5帧投票器 — 连续抓 N 帧，独立识别，多数一致才输出。

原理:
- mss (DXGI) 截图约 17ms/帧，5 帧 < 100ms
- 每帧独立用 CardMatcher 识别
- N 帧中对每张牌位置投票，同名出现 >= majority 帧才输出
- 单帧噪声（闪烁、UI 遮挡）被多数过滤掉

用法:
    voter = MultiFrameVoter(frames=5, majority_threshold=0.6)
    cards = voter.vote_hero_cards(capture_fn, hero_boxes, matcher, temp_db)
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from utils.temp_db import TempDB


class MultiFrameVoter:
    """连续抓 N 帧，独立识别，多数投票。"""

    def __init__(self, frames: int = 5, majority_threshold: float = 0.6):
        """
        Args:
            frames: 抓帧数量（默认 5）。
            majority_threshold: 多数比例阈值（默认 0.6 = 3/5）。
        """
        self.frame_count = max(3, frames)
        self.majority_needed = max(2, int(self.frame_count * majority_threshold))

    # ── Hero 手牌 ──────────────────────────────────────────────────

    def vote_hero_cards(
        self,
        capture_fn: Callable[[], np.ndarray],
        hero_boxes: list[tuple[int, int, int, int]],
        matcher,
        temp_db: TempDB | None = None,
    ) -> tuple[list[str], list[float]]:
        """
        5 帧投票识别 Hero 手牌。

        Args:
            capture_fn: () -> BGR screenshot 截图函数。
            hero_boxes: [(x, y, w, h), ...] 每张牌的区域。
            matcher: CardMatcher 实例。
            temp_db: 可选，临时数据库（存入牌面裁剪图）。

        Returns:
            (card_names, confidences): 投票通过的牌名和置信度。
            如果投票失败，返回空列表。
        """
        if not hero_boxes:
            return [], []

        num_cards = len(hero_boxes)
        # frame_votes[card_index][frame_index] = name
        frame_votes: list[list[str | None]] = [[] for _ in range(num_cards)]
        frame_confs: list[list[float]] = [[] for _ in range(num_cards)]
        frame_images: list[list[np.ndarray | None]] = [[] for _ in range(num_cards)]

        for _ in range(self.frame_count):
            frame = capture_fn()
            if frame is None or frame.size == 0:
                continue

            for ci, (bx, by, bw, bh) in enumerate(hero_boxes):
                if by + bh > frame.shape[0] or bx + bw > frame.shape[1]:
                    frame_votes[ci].append(None)
                    frame_confs[ci].append(0.0)
                    frame_images[ci].append(None)
                    continue

                card_img = frame[by:by + bh, bx:bx + bw]
                result = matcher.match(card_img)
                if result:
                    name, score = result
                    frame_votes[ci].append(name)
                    frame_confs[ci].append(score)
                    frame_images[ci].append(card_img.copy())
                else:
                    frame_votes[ci].append(None)
                    frame_confs[ci].append(0.0)
                    frame_images[ci].append(None)

        # 投票
        final_names: list[str] = []
        final_confs: list[float] = []

        for ci in range(num_cards):
            votes = [v for v in frame_votes[ci] if v is not None]
            if not votes:
                return [], []  # 没有任何识别结果 → 全部失败

            counter = Counter(votes)
            most_common_name, count = counter.most_common(1)[0]

            if count >= self.majority_needed:
                final_names.append(most_common_name)
                # 取该名字对应的最高分
                best_conf = max(
                    frame_confs[ci][fi]
                    for fi, v in enumerate(frame_votes[ci])
                    if v == most_common_name
                )
                final_confs.append(best_conf)

                # 存入临时数据库（最佳帧的图像）
                if temp_db is not None:
                    best_idx = max(
                        (fi for fi, v in enumerate(frame_votes[ci]) if v == most_common_name),
                        key=lambda fi: frame_confs[ci][fi],
                    )
                    best_img = frame_images[ci][best_idx]
                    if best_img is not None:
                        t = matcher.templates.get(most_common_name, {})
                        temp_db.save_card(
                            card_name=most_common_name,
                            rank=t.get("rank", most_common_name[0]),
                            suit=t.get("suit", most_common_name[1]),
                            is_red=t.get("is_red", False),
                            confidence=best_conf,
                            card_image=best_img,
                            position_x=hero_boxes[ci][0],
                            position_y=hero_boxes[ci][1],
                            width=hero_boxes[ci][2],
                            height=hero_boxes[ci][3],
                        )
            else:
                return [], []  # 投票未通过

        return final_names, final_confs

    # ── 公共牌 ──────────────────────────────────────────────────────

    def vote_community_cards(
        self,
        capture_fn: Callable[[], np.ndarray],
        comm_roi: tuple[int, int, int, int],
        matcher,
        temp_db: TempDB | None = None,
    ) -> list[str]:
        """
        5 帧投票识别公共牌。

        Args:
            capture_fn: () -> BGR screenshot。
            comm_roi: (x, y, w, h) 公共牌搜索区域。
            matcher: CardMatcher 实例。
            temp_db: 可选临时数据库。

        Returns:
            投票通过的卡牌名称列表。
        """
        rx, ry, rw, rh = comm_roi
        # 对每帧，在搜索区域内滑动匹配
        all_frame_names: list[set[str]] = []

        for _ in range(self.frame_count):
            frame = capture_fn()
            if frame is None or frame.size == 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            search = gray[ry:ry + rh, rx:rx + rw]

            frame_found: dict[str, float] = {}  # name -> best score
            for name in matcher.templates:
                rank_img = matcher.templates[name]["rank_img"]
                th, tw = rank_img.shape[:2]
                if th > search.shape[0] or tw > search.shape[1]:
                    continue

                result = cv2.matchTemplate(search, rank_img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val > 0.65:
                    # 去重：附近 15px 内的同名只保留最高分
                    px, py = max_loc
                    bx, by = rx + px - 3, ry + py - 3
                    if by < 0 or bx < 0:
                        continue
                    card_img = frame[by:by + 75, bx:bx + 52]
                    card_r = matcher.match(card_img) if card_img.size > 0 else None
                    if card_r and card_r[1] > 0.65:
                        cname, cscore = card_r
                        if cname not in frame_found or cscore > frame_found[cname]:
                            frame_found[cname] = cscore

            all_frame_names.append(set(frame_found.keys()))

        if not all_frame_names:
            return []

        # 投票：在所有帧中都出现至少 majority_needed 次的牌名
        all_names = set().union(*all_frame_names)
        confirmed = []
        for name in all_names:
            count = sum(1 for s in all_frame_names if name in s)
            if count >= self.majority_needed:
                confirmed.append(name)

        return sorted(confirmed)
