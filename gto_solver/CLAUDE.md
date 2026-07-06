# GTO Solver — WePoker 实时 GTO 策略助手

## 项目概述

一个运行在 Windows 上的桌面软件，**只通过屏幕图像分析**，
实时识别用户在 WePoker 中的手牌、公共牌和下注信息，
基于离线 GTO 表格提供策略建议，通过可调透明度的 HUD 和主窗口显示。

> 📖 完整蓝图见 [`docs/prd.md`](docs/prd.md)

## 技术栈

- **语言**: Python 3.11+
- **桌面**: Windows native API（`win32gui`, `BitBlt`）+ 可调透明度 HUD（`WS_EX_LAYERED`）
- **图像处理**: OpenCV (`cv2`), NumPy
- **GTO 解算**: SQLite（离线策略数据库）
- **AI 工作流**: OpenSpec（spec-driven）+ Comet（5 阶段开发）+ Superpowers（技能库）

## 项目结构

```
gto_solver/
├── src/                    # 源代码
│   ├── capture/            # 模块 1+2: 屏幕捕获与界面检测
│   ├── recognition/        # 模块 3: 手牌/公共牌识别
│   ├── parser/             # 模块 4: 局势解析器
│   ├── gto/                # 模块 5: GTO 解算库
│   ├── display/            # 模块 6: HUD 与主窗口
│   ├── controller/         # 模块 8: 主控制器与事件循环
│   └── utils/              # 模块 7: 配置、日志、模板录制
├── templates/              # 卡片/按钮/数字模板图像
├── data/                   # SQLite GTO 策略数据库
├── docs/                   # 文档与 PRD
├── tests/                  # 测试
├── openspec/               # OpenSpec 规格与变更管理
└── .claude/                # Claude Code 技能与规则
```

## 核心原则

- **零注入**: 绝不读取/修改游戏进程内存，纯屏幕图像分析
- **零错误**: 手牌和公共牌识别采用模板匹配+多帧投票，必须达到 100% 准确率
- **离线运行**: 所有识别和查询均在本地完成，无需网络
- **合规警告**: WePoker 可能禁止此类辅助工具，用户自担风险

## 开发规范

- 所有变更走 Comet 5 阶段流程：`open → design → build → verify → archive`
- 采用 spec-driven 开发：主规格在 `openspec/specs/`，每个变更的 delta spec 通过归档同步回主规格
- commit 采用 conventional commits（`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`）
- 语义版本号（`VERSION` 文件），每次 push 自动 bump + tag
- 每 30 分钟自动推送 GitHub（`https://github.com/bangou/gt.git`）

## GTO 查询协议

详见 [`docs/prd.md` §5](docs/prd.md) — 输入/输出 JSON schema、confidence 字段、降级策略。

## 当前状态

| 模块 | 状态 |
|------|------|
| 基础设施 | 🔄 Phase 0: 搭建中 |
| 1+2+3+4: 屏幕分析管线 | ⏳ 待 Comet open |
| 5: GTO 解算库 | ⏳ 待 Comet open |
| 6+7+8: 显示+配置+控制器 | ⏳ 后续 |
