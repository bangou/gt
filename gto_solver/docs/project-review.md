# GTO Strategy Assistant — 项目状态报告 V1.0

> 生成日期: 2026-07-06 | 版本: v0.3.0 | 语言: 中文
>
> 本文档供 Claude Code 及其他 LLM 快速了解项目全貌、模块状态和下一步方向。

---

## 1. 项目概述

**WePoker 实时 GTO 策略助手** — 一个运行在 Windows 上的桌面软件。

**核心功能**: 只通过屏幕图像分析，实时识别用户在 WePoker 中的手牌、公共牌和下注信息，基于离线 GTO 表格提供策略建议，通过可调透明度的 HUD 和主窗口显示。

**核心约束**:
- 零注入 (不读取/修改游戏进程内存)
- 零错误 (牌面识别采用模板匹配+5帧投票，要求 100% 准确率)
- 离线运行 (所有识别和查询均在本地完成)
- 合规警告 (WePoker 可能禁止此类辅助工具，用户自担风险)

---

## 2. 技术栈

```
语言:     Python 3.11+
截图:     mss (DXGI 高速截图, ~17ms/帧)
图像:     OpenCV (cv2) — 模板匹配, 轮廓分析, HSV 颜色空间
GUI:      tkinter (当前主界面), 未来升级 WS_EX_LAYERED HUD
GTO:      SQLite (离线策略数据库, 2,470 行)
包管理:   pyproject.toml + requirements.txt
测试:     pytest 4/4 passed
版本:     v0.3.0 (语义版本, 本地 git tag)
```

---

## 3. 整体架构

```
[屏幕捕获] → [区域定位] → [牌面检测] → [牌面识别] → [局势解析]
                                ↓
                    [5帧多数投票 (3/5)]
                                ↓
                    [临时数据库 (SQLite)]
                                ↓
                    [GTO 解算库查询] → [HUD + 主窗口显示]
```

### 数据流

```
mss 截图 (BGR numpy, ~17ms)
  → ROI 裁剪 (座位/公共牌/底池/Hero 区, 硬编码 1920×1080)
  → CardDetector 找牌 (多阈值轮廓分析 200→140)
  → MultiFrameVoter 5帧投票 (连续5帧独立识别, ≥3/5一致才输出)
  → CardMatcher 模板匹配 (rank ROI + 最暗像素法红黑判定 + Hu 矩花色细分)
  → 结果存入 TempDB (SQLite, 自动去重)
  → GameStateBridge 组装 GTO 查询 JSON
  → get_gto_strategy(json) 查询 SQLite 策略库
  → 策略建议 → UI 显示
```

---

## 4. 目录结构

```
gto_solver/
├── CLAUDE.md                    # AI 入口文件
├── VERSION                      # 当前版本号 (0.3.0)
├── pyproject.toml               # Python 包配置
├── requirements.txt             # 依赖清单
├── .gitignore
│
├── src/                         # 34 个 Python 文件
│   ├── capture/                 # ✅ 模块 1: 屏幕捕获
│   │   ├── window_manager.py    #   pygetwindow 找 WePoker 窗口
│   │   └── screen_capture.py    #   mss DXGI 高速截图
│   ├── roi/                     # ✅ 模块 2: 区域定位
│   │   ├── roi_config.py        #   硬编码 1920×1080 ROI
│   │   ├── roi_manager.py       #   区域裁剪
│   │   └── calibrate.py         #   自动校准 (绿色桌面检测)
│   ├── recognition/             # ✅ 模块 3: 牌面识别
│   │   ├── card_detector.py     #   多阈值轮廓检测
│   │   ├── card_templates.py    #   rank ROI 模板匹配 (CardMatcher)
│   │   ├── card_recognizer.py   #   多层 fallback (模板→OCR→颜色)
│   │   ├── multi_frame.py       #   5帧投票器 (MultiFrameVoter)
│   │   ├── action_detector.py   #   行动触发检测 (HSV 颜色)
│   │   ├── number_reader.py     #   数字读取 (模板匹配+手动回退)
│   │   └── seat_detector.py     #   座位占用检测 (加权投票)
│   ├── parser/                  # 🟡 模块 4: 局势解析
│   │   ├── models.py            #   Card/Suit/Rank/Street/GameState
│   │   ├── seat_assigner.py     #   Dealer→角色分配 (BTN/SB/BB/UTG/HJ/CO)
│   │   └── game_state_bridge.py #   识别结果→GTO 查询 JSON 桥接
│   ├── gto/                     # ✅ 模块 5: GTO 解算库
│   │   ├── api.py               #   get_gto_strategy() 入口
│   │   ├── engine.py            #   查询引擎 (normalize + lookup)
│   │   ├── codec.py             #   协议编解码 (preflop_hand_key, classify_board_texture 等)
│   │   ├── store.py             #   SQLite 查询 (lookup_strategy)
│   │   ├── importer.py          #   CSV/JSONL 导入
│   │   ├── bootstrap.py         #   数据库初始化
│   │   └── models.py            #   NormalizedRequest
│   ├── controller/              # 🟡 模块 6+8: 主界面与事件循环
│   │   └── app.py               #   tkinter GUI (开始/停止, 实时显示, GTO查询)
│   ├── display/                 # ❌ 模块 6: HUD (空壳)
│   └── utils/                   # ✅ 工具
│       ├── config.py            #   配置管理 (json 持久化)
│       └── temp_db.py           #   临时数据库 (关闭时自动去重入库)
│
├── templates/cards/             # 扑克牌模板库 (三个独立库)
│   ├── render/                  #   渲染模板库 (模板匹配用, 209 文件, 52 张牌 raw+bin+rank+suit)
│   ├── real/                    #   真实截图库 (识别中采集的原始 WePoker 牌面, 关闭时自动入库)
│   └── community/               #   公共牌模板 (3 张, 主要用于测试)
│
├── data/
│   ├── seed/                    # 4 个 CSV 种子文件 (2,470 行策略数据)
│   │   ├── gto_data.csv         #   原始 Codex 数据 (30 行)
│   │   ├── gto_data_rfi_9max.csv       #   9-max RFI 数据 (1,352 行)
│   │   ├── gto_data_rfi_6max.csv       #   6-max RFI 数据 (845 行)
│   │   └── gto_data_blind_defense_9max.csv  #   盲注防守数据 (249 行)
│   └── sqlite/gto_solver.db     #   SQLite 策略库 (2,470 行, 16 个场景)
│
├── screenshots/test/            # 41 张 WePoker 真实截图 (测试集)
│
├── tests/                       # 4 个 pytest + 1 个管道测试
│   ├── test_api.py              #   GTO 解算库 3 个测试
│   ├── test_importer.py         #   CSV 导入测试
│   ├── test_pipeline.py         #   离线端到端管道测试
│   └── conftest.py              #   pytest 路径配置
│
├── scripts/
│   └── generate_preflop_data.py # 翻前数据生成脚本 (Upswing Poker 范围表)
│
├── openspec/specs/              # OpenSpec 主规格 (4 个 capability)
│   ├── screen-analysis/spec.md
│   ├── gto-solver/spec.md
│   ├── display-hud/spec.md
│   └── controller/spec.md
│
└── docs/
    ├── prd.md                   # 完整 PRD V2.0 (中文)
    └── project-review.md        # 本文档
```

---

## 5. 模板数据库体系 (重要)

项目有三个独立的模板库，职责各不相同，**不能混用**:

| 库 | 路径 | 功能 | 来源 |
|----|------|------|------|
| **render** | `templates/cards/render/` | 模板匹配用, 每张牌有 raw/bin/rank/suit 四种格式 + index.json | 从 gto_agent 迁移 + 截图自动提取补齐 |
| **real** | `templates/cards/real/` | 存储真正 WePoker 截图裁剪的原始牌面, 每张一个 PNG + index.json | 识别过程中 TempDB.dedup_and_merge() 自动写入 |
| **community** | `templates/cards/community/` | 公共牌模板 (仅 3 张, 主要用于测试) | 从 gto_agent 迁移 |

### render 库详情

```
52 张牌 × 4 种格式 = 208 个文件 + 1 个 index.json = 209 个文件
- raw.png: 原始彩色牌面裁剪
- bin.png: OTSU 二值化 (形态学去噪)
- rank.png: 左上角点数区域 (3~55%宽 × 3~40%高) — 模板匹配用这个
- suit.png: 右下角花色区域 (58%宽 × 55%高 ~ 右下角)
```

`CardMatcher` 加载 `render/` 库做模板匹配，`CardRecognizer` 通过 `CardMatcher.match()` 识别牌面。

### real 库详情

```
路径: templates/cards/real/
格式: 每张牌一个 {name}.png + index.json
来源: 软件关闭时 TempDB.dedup_and_merge() 从临时库选出新牌自动写入
用途: 保存真实的 WePoker 牌面截图，作为训练/验证数据
```

---

## 6. 识别流水线详解

### 6.1 5 帧投票机制

```
MultiFrameVoter(frames=5, majority_threshold=0.6)
```

- 连续用 `mss` 截 5 帧 (~17ms/帧, 5 帧 < 100ms)
- 每帧独立用 `CardMatcher.match()` 识别
- 5 帧中对每张牌位置统计出现最多的名字
- 同名出现 ≥ 3/5 才输出
- 单帧噪声 (闪烁、UI 遮挡) 被多数投票过滤
- **实测**: 5 帧全部完成 < 200ms, 实时完全可行

### 6.2 CardMatcher 识别流程

```
card_image (BGR 牌面裁剪图)
  → 灰度化
  → 提取 rank ROI (左上角 3~55%宽 × 3~40%高)
  → 与所有 render/ 模板的 rank.png 做 cv2.matchTemplate (TM_CCOEFF_NORMED)
  → 取最高分, 阈值 0.65
  → 红黑判定: 取 rank ROI 最暗 10% 像素, 计算 R/B 比值, >1.5 = 红色
  → 花色判别: Hu 矩形状匹配 (区分 ♥/♦ 或 ♣/♠)
  → 返回 (name, score)
```

**在 41 张真实 WePoker 截图上实测:**
- Hero 手牌: 82/82 = 100%
- 公共牌: 60/60 = 100%
- 总计: 142/142 = 100%

### 6.3 行动触发检测

```
ActionTrigger.is_hero_turn(frame)
  → 提取 Hero 操作区域 (默认底部 1/4 中央 60%)
  → HSV 颜色检测:
    - 红色: (0,80,80)-(10,255,255) + (160,80,80)-(180,255,255) → Fold
    - 绿色: (35,50,50)-(85,255,255) → Call
    - 蓝色: (95,50,50)-(130,255,255) → Raise
  → 至少 2 种按钮颜色 > 1.5% 像素 → 轮到自己
```

⚠️ 当前为颜色检测兜底方案，未来可升级为按钮模板匹配。

### 6.4 端到端流程

```
1. 用户点击"开始识别"
2. 后台线程:
   a. mss 截图 → ActionTrigger.is_hero_turn()
   b. 如果轮到自己 → MultiFrameVoter.vote_hero_cards() (5 帧)
   c. 同时 vote_community_cards() (5 帧)
   d. 结果存入 TempDB
   e. GameStateBridge.build_from_recognized() → GTO 查询 JSON
   f. bridge.query_gto() → 策略建议
   g. 结果推送到 UI 队列
3. UI 每 50ms 轮询队列, 更新显示:
   - 手牌/公共牌
   - GTO 推荐动作 + 频率 + 可信度
   - 帧率/耗时/周期
   - 临时库/正式库数量
4. 关闭窗口 → TempDB.dedup_and_merge() 新牌入 real 库 → TempDB.clear()
```

---

## 7. GTO 数据库

### 当前覆盖

| 数据 | 行数 | 说明 |
|------|------|------|
| Codex 原始 | 30 行 | 翻前 RFI (AKs, 72o 等) + 翻后 cbet/defense 示例 |
| 9-max RFI | 1,352 行 | UTG~BTN 各位置完整 169 手牌范围 (Upswing Poker 公开表) |
| 6-max RFI | 845 行 | UTG~BTN 各位置 (Upswing Poker 公开表) |
| BB 盲注防守 | 249 行 | BB vs BTN open (call/3bet/fold) |
| **总计** | **2,470 行** | **16 个场景** |

### 已覆盖的场景

- 翻前 RFI: 9-max (8 个位置), 6-max (6 个位置)
- 盲注防守: BB vs BTN open
- 翻后 cbet (Codex 原有 2 个示例)
- 翻后 vs cbet defense (Codex 原有 1 个示例)

### 尚未覆盖

- 9-max SB RFI 完整范围
- vs RFI (面对开池的 3bet/call/fold 决策, 各位置)
- vs 3bet (面对 3bet 的决策)
- Cold Call (冷跟范围)
- 翻后全纹理 (flop/turn/river 各类 board texture 的策略)
- 多人底池

---

## 8. 模块完成度评估

| 模块 | 完成度 | 可用性 | 备注 |
|------|--------|--------|------|
| 1. 屏幕捕获 | 90% | ✅ | mss DXGI, 窗口查找, 硬编码坐标 |
| 2. 区域定位 | 80% | ✅ | 1920×1080 硬编码, 自动校准可用 |
| 3. 牌面识别 | 95% | ✅ | 100% 准确率 (实测), 5 帧投票, Hu 矩花色细分 |
| 4. 局势解析 | 70% | ✅ | GameState→JSON, 座位分配; 数字识别需模板 |
| 5. GTO 解算库 | 70% | ✅ | 2,470 行 16 场景; 翻后数据不足 |
| 6. HUD 显示 | 0% | ❌ | 空壳, tkinter 仅用于调试 |
| 7. 配置工具 | 80% | ✅ | config.json + TempDB |
| 8. 主控制器 | 60% | ✅ | tkinter 界面可用; 缺少真正的 WS_EX_LAYERED HUD |
| **综合** | **~60%** | **🟡 可联调, 不可实战** | 识别管线完整, GTO 翻前可用, HUD 缺失 |

---

## 9. 已完成的测试

```
$ pytest tests/ -v
tests/test_api.py::test_normal_query_returns_check_bet_strategy PASSED
tests/test_api.py::test_unsupported_spot_returns_error PASSED
tests/test_api.py::test_missing_optional_fields_use_defaults PASSED
tests/test_importer.py::test_import_csv_to_db... PASSED
============================== 4 passed ==============================

$ python tests/test_pipeline.py
Hero 识别: 16/16 = 100%
管道测试完成
```

---

## 10. 下一步方向 (按优先级)

| 优先级 | 方向 | 说明 |
|--------|------|------|
| 🔴 P0 | **真实 WePoker 测试** | 打开游戏, 运行 `python -m src.controller.app`, 验证端到端 |
| 🔴 P0 | **HUD 透明悬浮窗** | tkinter → WS_EX_LAYERED 透明顶层窗口覆盖游戏 |
| 🟡 P1 | **翻后 GTO 数据** | flop/turn/river 常见纹理策略 |
| 🟡 P1 | **vs RFI/3bet 数据** | 面对开池/3bet 的决策数据 |
| 🟡 P1 | **多分辨率适配** | 硬编码 1920×1080 → 窗口比例动态缩放 |
| 🟢 P2 | **数字模板录制** | 从 WePoker 截取 0-9 使 number_reader 精确 |
| 🟢 P2 | **按钮模板录制** | 精确模板匹配替代颜色检测 |

---

*本文档自动生成, 版本 V1.0 | 生成日期: 2026-07-06*
