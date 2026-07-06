"""
离线端到端测试 — 用已有截图模拟完整识别管线。

cd gto_solver
PYTHONPATH="src" python -X utf8 tests/test_pipeline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2
from recognition.card_templates import CardMatcher
from recognition.multi_frame import MultiFrameVoter
from utils.temp_db import TempDB

# 用测试截图模拟"截图函数"
TEST_SHOTS = sorted(Path("screenshots/test").glob("hand*.png"))
if not TEST_SHOTS:
    print("❌ 找不到测试截图，请确保 screenshots/test/ 下有 .png 文件")
    sys.exit(1)

print(f"测试截图: {len(TEST_SHOTS)} 张")
print()

# 按阶段分组
deal_shots = [f for f in TEST_SHOTS if "_deal" in f.stem]
flop_shots = [f for f in TEST_SHOTS if "_flop" in f.stem]
turn_shots = [f for f in TEST_SHOTS if "_turn" in f.stem]
river_shots = [f for f in TEST_SHOTS if "_river" in f.stem]

print(f"  deal: {len(deal_shots)} | flop: {len(flop_shots)} | turn: {len(turn_shots)} | river: {len(river_shots)}")
print()

# 初始化
matcher = CardMatcher()
temp_db = TempDB("data/temp/test_pipeline.db")
hero_boxes = [(908, 873, 50, 73), (963, 873, 50, 73)]
comm_roi = (800, 465, 300, 50)

# ── 模拟 5 帧投票（用同一张截图重复 5 次，模拟稳态场景）──
# 这不是真正的 5 帧投票（因为截图为同一帧），
# 但可以验证数据流和 temp_db 的存储功能。
print("=" * 60)
print("离线管道测试")
print("=" * 60)

total_hero_ok = 0
total_hero = 0

for shot in deal_shots[:5] + flop_shots[:3]:
    img = cv2.imread(str(shot))
    if img is None:
        continue
    stage = shot.stem.split("_")[-1]

    # 模拟 5 帧：同一张图重复 5 次
    call_count = [0]

    def mock_capture():
        call_count[0] += 1
        return img.copy()

    # 用真正的 MultiFrameVoter（5 帧会投出全票，因为是同一张图）
    voter = MultiFrameVoter(frames=5, majority_threshold=0.6)
    hero_names, hero_confs = voter.vote_hero_cards(
        mock_capture, hero_boxes, matcher, temp_db,
    )

    total_hero += 2  # 期望 2 张
    total_hero_ok += len(hero_names)

    status = "✅" if len(hero_names) == 2 else "⚠️"
    hero_str = " ".join(
        f"{n}({c:.0%})" for n, c in zip(hero_names, hero_confs)
    ) if hero_names else "未识别"
    print(f"  {status} {shot.stem:20s} | Hero: {hero_str:25s} | frames: {call_count[0]}")

    # 公共牌（仅 flop+）
    if stage in ("flop", "turn", "river"):
        comm_names = voter.vote_community_cards(mock_capture, comm_roi, matcher, temp_db)
        comm_status = "✅" if (stage == "flop" and len(comm_names) >= 3) or \
                              (stage == "turn" and len(comm_names) >= 4) or \
                              (stage == "river" and len(comm_names) >= 5) else "⚠️"
        print(f"    公共牌: {' '.join(comm_names) if comm_names else '未识别':30s} {comm_status}")

print()
print(f"Hero 识别: {total_hero_ok}/{total_hero}")
print(f"临时库记录: {temp_db.count()}")

# 测试去重入库
if temp_db.count() > 0:
    new_count = temp_db.dedup_and_merge()
    print(f"入库新增: {new_count} 张")

# 清理
temp_db.clear()
Path("data/temp/test_pipeline.db").unlink(missing_ok=True)
print("✅ 管道测试完成")
