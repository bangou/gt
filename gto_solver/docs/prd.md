# WePoker 实时 GTO 策略助手 — 开发蓝图 V2.0

> **版本**: V2.0 | **日期**: 2026-07-06 | **状态**: Phase 0 完成，屏幕分析管线已合并，准备进入 Comet 开发

---

## 1. 项目目标

一个运行在 Windows 上的桌面软件，**只通过屏幕图像分析**，实时识别你的手牌、公共牌和下注信息，基于离线 GTO 表格提供策略建议，通过可调透明度的 HUD 和主窗口显示。

---

## 2. 核心原则

- **零注入**：绝不读取/修改游戏进程内存，纯屏幕图像分析。
- **零错误**：手牌和公共牌识别采用模板匹配+多帧投票，必须达到 100% 准确率。
- **离线运行**：所有识别和查询均在本地完成，无需网络。
- **合规警告**：WePoker 可能禁止此类辅助工具，用户自担风险。

---

## 3. 整体架构

```
[屏幕捕获] → [区域定位] → [牌面检测] → [牌面识别] → [局势解析]
                                                    ↓
                                        [GTO 解算库查询]
                                                    ↓
                                        [HUD + 主窗口显示]
```

### 3.1 数据流

```
截图 (mss/DXGI, BGR numpy)
  → ROI 裁剪 (座位、公共牌、底池、Hero 区)
  → CardDetector 找牌 (多阈值轮廓分析)
  → CardMatcher 模板匹配 (rank ROI + 红黑判定 + Hu 矩花色细分)
  → GameState 组装 (Card/Suit/Rank/Street → JSON)
  → get_gto_strategy(json) 查询 SQLite
  → 策略 → HUD 悬浮窗
```

---

## 4. 模块现状与进度

### 模块 1+2：屏幕捕获与界面状态检测 ← 🟢 已整合

| 项目 | 状态 |
|------|------|
| 窗口查找 | ✅ `src/capture/window_manager.py` — pygetwindow 按标题找 WePoker 窗口 |
| 高速截图 | ✅ `src/capture/screen_capture.py` — mss (DXGI) 截图，numpy/PIL/bytes 多格式 |
| ROI 区域管理 | ✅ `src/roi/roi_manager.py` + `roi_config.py` — 6 座座位+公共牌+底池+Hero 区 |
| 自动校准 | ✅ `src/roi/calibrate.py` — 绿色桌面检测 + 轮廓分析自动标定 |
| 行动触发检测 | ❌ 未实现 — 需要模板匹配"弃牌/跟注/加注"按钮 |
| 庄位标记识别 | ❌ 未实现 |
| 动态坐标缩放 | ❌ 未实现 — 当前硬编码 1920×1080 |
| 多桌预留 | ❌ 未实现 |

### 模块 3：手牌与公共牌高精度识别 ← 🟢 已整合 + 🎉 52 张牌模板库已补齐

| 项目 | 状态 |
|------|------|
| 牌面检测 | ✅ `src/recognition/card_detector.py` — 多阈值轮廓分析，宽高比 0.40-0.90，去重合并 |
| 模板匹配 | ✅ `src/recognition/card_templates.py` — rank ROI 匹配 + 红黑判定 + Hu 矩花色细分 |
| 多层 fallback | ✅ `src/recognition/card_recognizer.py` — 模板匹配 → OCR → 颜色分析 |
| 52 张牌模板库 | ✅ `templates/cards/hero/` — raw/bin/rank/suit 四种格式各 52 张，含 index.json |
| Hero 牌识别准确率 | ✅ **100%** (82/82，41 张真实 WePoker 截图验证) |
| 公共牌识别准确率 | ✅ **100%** (60/60，5 组 flop/turn/river 截图验证) |
| 5 帧投票机制 | ❌ 未实现 — 当前单帧识别，PRD 要求 5 帧多数一致才输出 |
| 座位检测 | ✅ `src/recognition/seat_detector.py` — 加权投票（"+"号、肤色、HoughCircles、纹理） |

### 模块 4：局势解析器 ← 🟡 部分就绪

| 项目 | 状态 |
|------|------|
| GameState 数据模型 | ✅ `src/parser/models.py` — dataclass (Card/Suit/Rank/Street/Action/GameState) |
| 座位角色分配 | ✅ `src/parser/seat_assigner.py` — BTN→顺时针分配 UTG/HJ/CO/BTN/SB/BB |
| 组装 GTO 查询 JSON | ❌ 未实现 — 需要桥接识别结果 → GTO 协议 JSON |
| 下注/底池数字识别 | ❌ 未实现 |
| 行动历史追踪 | ❌ 未实现 |

### 模块 5：GTO 解算库 ← 🟡 Alpha 版

| 项目 | 状态 |
|------|------|
| `get_gto_strategy()` | ✅ `src/gto/engine.py` — JSON in / JSON out |
| SQLite 存储 | ✅ `src/gto/store.py` + `importer.py` — UNIQUE 约束，CSV/JSONL 导入 |
| 协议完整性 | ✅ 可选字段默认值、check/bet 动作、confidence 字段、降级查询 |
| 测试 | ✅ 4/4 pytest passed |
| 数据量 | ⚠️ SQLite 30 行，覆盖 6 个场景 — **仅可联调，不可实战** |
| 翻前 9-max 全覆盖 | ❌ 未实现 |
| 翻后数据 | ❌ 仅 2 个 heuristic 示例 |

### 模块 6：策略显示与 HUD ← ❌ 未开始

### 模块 7：配置与工具 ← ❌ 未开始

### 模块 8：主控制器与事件循环 ← ❌ 未开始

---

## 5. 项目文件结构

```
gto1.0/gto_solver/
├── CLAUDE.md                    # AI 入口文件
├── VERSION                      # 语义版本号
├── pyproject.toml               # Python 包配置
├── requirements.txt             # opencv-python, numpy, pyautogui, pywin32, pytest
├── .gitignore
│
├── src/
│   ├── capture/                 # ✅ 模块 1: 屏幕捕获
│   │   ├── window_manager.py    #    找 WePoker 窗口
│   │   └── screen_capture.py    #    mss DXGI 截图
│   ├── roi/                     # ✅ 模块 2: 区域定位
│   │   ├── roi_config.py        #    硬编码 ROI（1920×1080）
│   │   ├── roi_manager.py       #    区域裁剪
│   │   └── calibrate.py         #    自动校准
│   ├── recognition/             # ✅ 模块 3: 牌面识别
│   │   ├── card_detector.py     #    多阈值轮廓检测
│   │   ├── card_templates.py    #    rank ROI 模板匹配
│   │   ├── card_recognizer.py   #    多层 fallback 识别器
│   │   └── seat_detector.py     #    座位占用检测
│   ├── parser/                  # 🟡 模块 4: 局势解析
│   │   ├── models.py            #    Card/Suit/Rank/GameState dataclass
│   │   └── seat_assigner.py     #    Dealer→座位角色分配
│   ├── gto/                     # 🟡 模块 5: GTO 解算库 (Alpha)
│   │   ├── api.py               #    get_gto_strategy() 入口
│   │   ├── engine.py            #    查询引擎
│   │   ├── codec.py             #    协议编解码
│   │   ├── store.py             #    SQLite 查询
│   │   ├── importer.py          #    CSV/JSONL 导入
│   │   ├── bootstrap.py         #    数据库初始化
│   │   └── models.py            #    NormalizedRequest
│   ├── display/                 # ❌ 模块 6: 空壳
│   ├── controller/              # ❌ 模块 8: 空壳
│   └── utils/                   # ❌ 模块 7: 空壳
│
├── templates/cards/             # 🎉 52 张牌模板库
│   ├── hero/                    #    52 张 raw + bin + rank + suit + index.json
│   └── community/               #    3 张社区牌模板
│
├── data/
│   ├── seed/gto_data.csv        #    翻前+翻后示例数据 (30 行)
│   └── sqlite/gto_solver.db     #    SQLite 策略库
│
├── screenshots/test/            #    41 张 WePoker 真实截图 (测试集)
│
├── tests/
│   ├── test_api.py              #    GTO 解算库 3 个测试
│   ├── test_importer.py         #    CSV 导入测试
│   └── conftest.py
│
├── openspec/
│   └── specs/                   #    4 个主 spec (screen-analysis, gto-solver, display-hud, controller)
│
└── docs/
    └── prd.md                   #    本文档
```

---

## 6. GTO 查询协议

### 输入

```json
{
  "table_size": 6,
  "position": "BTN",
  "effective_stack_bb": 100,
  "my_hand": ["Ah", "Kh"],
  "board": ["Qh", "Jd", "4s", "8d", "2c"],
  "pot_size_bb": 15.0,
  "current_bet_to_call_bb": 5.0,
  "actions_history": [
    {"street": "preflop", "actions": ["fold", "raise_3bb", "call", "fold", "fold", "hero_to_act"]},
    {"street": "flop", "actions": ["check", "bet_5bb", "hero_to_act"]}
  ],
  "players_remaining": 2,
  "options": ["fold", "call", "raise"],
  "raise_sizes_allowed": [5.0, 10.0, 15.0]
}
```

- `effective_stack_bb`、`board`、`actions_history` 可选，缺省默认值（100BB、空牌面、空历史）。

### 输出

```json
{
  "status": "success",
  "strategy": {
    "fold": 15.2,
    "call": 20.8,
    "raise": 64.0,
    "raise_sizes": [
      {"size_bb": 5.0, "prob": 40.0},
      {"size_bb": 10.0, "prob": 24.0}
    ]
  },
  "range_info": {
    "equity": 48.5,
    "recommended_action": "raise"
  },
  "confidence": "high",
  "debug": {}
}
```

- 动作支持 `check`/`bet`/`fold`/`call`/`raise`。
- `confidence`: `"high"` (精确匹配), `"medium"` (模糊匹配), `"low"` (默认回退)。

---

## 7. 数据源与升级提醒

**当前阶段**：使用免费公开范围表，覆盖翻前核心，翻后使用启发式规则。

**📌 升级提醒**：当以下任一条件满足时，提示订阅 GTO Wizard 一个月（约 $49）：
- 软件进入实际使用测试阶段
- 翻后策略明显不足或用户反馈建议质量低
- 主动询问如何提升策略准确性

采集方式为人工+浏览器脚本导出，禁止自动抓取。

---

## 8. 开发进度日志

| 日期 | 事项 | 备注 |
|------|------|------|
| 2026-07-06 | Phase 0 基础设施 | CLAUDE.md、.gitignore、Python 骨架、OpenSpec 4 个主 spec |
| 2026-07-06 | PRD V1.0 定稿 | 写入 `docs/prd.md` |
| 2026-07-06 | 模块 5 Alpha 集成 | Codex 交付 `src/gto/`，4/4 tests passed，SQLite 30 行，6 场景 |
| 2026-07-06 | **gto_agent 屏幕分析管线合并** | capture + roi + recognition + parser 模块从 `D:\gto_agent` 迁移到 `src/` |
| 2026-07-06 | **52 张牌模板库补齐** | 从 41 张真实截图中自动提取 23 张缺失 raw 模板，52/52 raw+bin+rank+suit 齐全 |
| 2026-07-06 | **识别准确率验证** | Hero 82/82=100%, 公共牌 60/60=100%, 合计 142/142=100% |
| 2026-07-06 | PRD V2.0 | 重写本文档，反映最新模块状态、文件结构、进度日志 |
| 2026-07-06 | **管线补全: 5帧投票+临时库+主界面** | `multi_frame.py`、`temp_db.py`、`config.py`、`controller/app.py`（tkinter GUI） |
| 2026-07-06 | **Change A 补全: 触发检测+数字识别+JSON桥接+GTO查询** | `action_detector.py`、`number_reader.py`、`game_state_bridge.py`，主界面接入 GTO 策略显示 |
| 2026-07-06 | **数据库分离** | render 库（模板匹配用，209 文件） vs real 库（截图裁剪入库用） |
| 2026-07-06 | **GTO 数据扩充 (B)** | 9-max RFI + 6-max RFI + BB 盲注防守，**2,440 行新数据导入，SQLite 总计 2,470 行，16 个场景** |
| 2026-07-06 | **多分辨率适配 (F)** | `roi_config.py` 支持动态缩放，`src/utils/coords.py` 统一坐标计算（基准 1920×1080 → 实际窗口比例） |

---

## 9. 下一步方向

按优先级排列：

| 优先级 | 方向 | 说明 |
|--------|------|------|
| 🔴 P0 | **Change A: 屏幕分析管线补全** | 5 帧投票、行动触发检测、数字识别、GameState→JSON 桥接、端到端测试 |
| 🔴 P0 | **Change B: GTO 数据扩充** | 9-max 100BB 翻前全覆盖、翻后常见纹理、vs open / blind defense 场景 |
| 🟡 P1 | **Change C: HUD + 控制器** | 透明悬浮窗、事件循环、端到端跑通 |
| 🟢 P2 | 动态分辨率适配 | 窗口相对坐标替代硬编码、基准 1920×1080 → 动态缩放 |
| 🟢 P2 | 配置与模板录制工具 | config.json、log 系统、模板重录工具 |

---

*文档版本: V2.0 | 创建日期: 2026-07-06 | 维护者: Claude Code + 用户*
