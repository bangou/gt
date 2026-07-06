# GTO Strategy Assistant — LLM Handoff Package v0.3.0

> 本文件为其他 LLM（Claude Code、Codex、GPT 等）提供完整的项目上下文，
> 使其能够快速理解项目全貌并继续开发工作。

---

## 项目概述

**WePoker 实时 GTO 策略助手** — Windows 桌面软件, 纯屏幕图像分析。
识别手牌/公共牌/下注信息 → 离线 GTO 表格查询 → 策略建议 → HUD 显示。

## 核心约束

- 零注入 (不碰游戏进程内存)
- 零错误 (模板匹配+5帧投票, 实测 142/142=100%)
- 离线运行 (SQLite 本地策略库)
- Python 3.11+ / OpenCV / mss / tkinter

---

## 目录结构

```
gto_solver/
├── CLAUDE.md              # AI 入口文件
├── VERSION                 # 0.3.0
├── pyproject.toml / requirements.txt
├── src/                    # 34 Python 文件
│   ├── capture/            # 屏幕捕获 (mss DXGI)
│   ├── roi/                # 区域定位 (硬编码 1920×1080)
│   ├── recognition/        # 牌面识别 (CardDetector, CardMatcher, 5帧投票)
│   ├── parser/             # 局势解析 (GameState→JSON)
│   ├── gto/                # GTO 解算库 (SQLite, get_gto_strategy)
│   ├── controller/         # tkinter 主界面
│   ├── display/            # HUD 空壳
│   └── utils/              # 配置 + 临时数据库
├── templates/cards/
│   ├── render/             # 模板匹配库 (209文件, 52张牌 raw+bin+rank+suit)
│   ├── real/               # 真实截图库 (识别时自动入库)
│   └── community/          # 公共牌模板 (3张)
├── data/
│   ├── seed/               # 4 CSV 文件 (2,470行策略数据)
│   └── sqlite/gto_solver.db
├── screenshots/test/       # 41 张 WePoker 真实截图
├── tests/                  # pytest 4/4 passed + pipeline test
├── docs/
│   ├── prd.md              # PRD V2.0 (中文)
│   └── project-review.md   # 完整项目报告 (中文)
└── openspec/specs/         # 4 个 capability specs
```

---

## 识别流水线 (核心链路)

```
mss 截图 (~17ms)
  → ActionTrigger.is_hero_turn() [HSV 颜色检测按钮]
  → MultiFrameVoter.vote_hero_cards() [5帧独立识别, ≥3/5一致]
  → CardMatcher.match() [rank ROI 模板匹配 + 最暗像素红黑判定 + Hu矩花色细分]
  → TempDB.save_card() [存入临时 SQLite]
  → GameStateBridge.build_from_recognized() [识别结果→GTO查询JSON]
  → get_gto_strategy(json) [SQLite策略查询]
  → UI 显示推荐动作/频率/可信度
```

### 关键模块

| 模块 | 文件 | 功能 |
|------|------|------|
| CardMatcher | `recognition/card_templates.py` | 模板匹配: rank ROI + cv2.TM_CCOEFF_NORMED, 阈值0.65, 红黑判定(R/B比值>1.5=红), Hu矩花色细分 |
| MultiFrameVoter | `recognition/multi_frame.py` | 5帧投票: 连续5帧独立识别, ≥3/5一致输出 |
| TempDB | `utils/temp_db.py` | 临时数据库: 存裁剪图, 关闭时 dedup_and_merge() → real库 |
| GameStateBridge | `parser/game_state_bridge.py` | 识别结果→GTO查询JSON→调用get_gto_strategy() |
| ActionTrigger | `recognition/action_detector.py` | HSV颜色检测Fold/Call/Raise按钮 |
| NumberReader | `recognition/number_reader.py` | 数字识别 (模板匹配+手动回退) |
| get_gto_strategy | `gto/engine.py` | JSON in → SQLite lookup → JSON out |

---

## 模板数据库体系 (重要!)

三个独立的模板库, **不能混用**:

| 库 | 路径 | 功能 | 来源 |
|----|------|------|------|
| render | `templates/cards/render/` | 模板匹配用, 52张牌×4格式+index.json | gto_agent迁移+截图自动提取 |
| real | `templates/cards/real/` | 真实WePoker牌面截图, 每张1个PNG+index.json | 关闭时TempDB自动写入 |
| community | `templates/cards/community/` | 公共牌模板, 仅3张 | gto_agent迁移 |

---

## GTO 数据库

SQLite: `data/sqlite/gto_solver.db`
- 2,470 行, 16 个场景
- 9-max RFI: 1,352行 (UTG~BTN 全169手牌范围)
- 6-max RFI: 845行
- BB盲注防守: 249行
- 翻后示例: 30行 (Codex原始)

---

## 测试

```bash
cd gto_solver
PYTHONPATH="src" python -m pytest tests/ -v   # 4 passed
PYTHONPATH="src" python tests/test_pipeline.py  # Hero 16/16=100%
```

---

## 下一步方向 (按优先级)

1. 🔴 真实 WePoker 测试 — `python -m src.controller.app`
2. 🔴 HUD 透明悬浮窗 — WS_EX_LAYERED 替代 tkinter
3. 🟡 翻后 GTO 数据 — flop/turn/river 纹理策略
4. 🟡 vs RFI/3bet 数据
5. 🟡 多分辨率适配 — 硬编码→动态缩放
6. 🟢 数字/按钮模板录制

---

## 关键命令

```bash
# 运行主界面
cd gto_solver && PYTHONPATH="src" python -m src.controller.app

# 生成翻前数据
PYTHONPATH="src" python scripts/generate_preflop_data.py

# 导入 CSV 到数据库
PYTHONPATH="src" python -c "
from gto.importer import init_db, import_csv_to_db
conn = init_db('data/sqlite/gto_solver.db')
print(import_csv_to_db(conn, 'data/seed/gto_data_rfi_9max.csv'))
conn.close()
"

# 测试 GTO 查询
PYTHONPATH="src" python -c "
from gto.api import get_gto_strategy
import json
q = json.dumps({'table_size':9,'position':'BTN','my_hand':['Ah','Kh'],'pot_size_bb':1.5,'current_bet_to_call_bb':0})
print(get_gto_strategy(q))
"
```

---

## 文档索引

- `docs/prd.md` — 完整开发蓝图 (中文, V2.0)
- `docs/project-review.md` — 项目状态报告 (中文, V1.0)
- `CLAUDE.md` — AI 入口文件 (英文)
- `openspec/specs/*/spec.md` — 4 个 capability 规格

---

*生成日期: 2026-07-06 | 版本: v0.3.0 | 维护者: Claude Code + bangou*
