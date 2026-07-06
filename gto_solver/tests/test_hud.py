"""
HUD Overlay — 独立演示脚本

用法:
    cd gto_solver
    PYTHONPATH="src" python tests/test_hud.py

功能:
    启动透明 HUD 悬浮窗，循环展示模拟的 GTO 策略数据，
    验证 WS_EX_LAYERED 透明窗口渲染是否正常工作。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from display.hud import HudOverlay


def main() -> None:
    print("HUD 透明悬浮窗演示")
    print("=" * 40)

    # 尝试创建 HUD（即使 WePoker 不在运行也可用，会 fallback 到屏幕右上角）
    hud = HudOverlay(
        target_window_title="WePoker",
        width=380,
        height=260,
        font_size=16,
    )

    hud.start()
    print("HUD 已启动 — 查看屏幕右上角")
    print()

    # 模拟场景序列
    scenarios = [
        {
            "hero": ["Ah", "Kh"],
            "community": [],
            "action": "RAISE",
            "frequency": "fold: 0%  raise: 100%",
            "confidence": "high",
            "status": "running",
            "fps": 20,
            "elapsed_ms": 56,
        },
        {
            "hero": ["Qd", "Jd"],
            "community": ["Kd", "Td", "3s"],
            "action": "BET",
            "frequency": "check: 30%  bet: 70%",
            "confidence": "high",
            "status": "running",
            "fps": 20,
            "elapsed_ms": 58,
        },
        {
            "hero": ["7h", "2s"],
            "community": [],
            "action": "FOLD",
            "frequency": "fold: 100%",
            "confidence": "high",
            "status": "running",
            "fps": 20,
            "elapsed_ms": 52,
        },
        {
            "hero": ["As", "Qs"],
            "community": ["Js", "Ts", "3h", "9c"],
            "action": "RAISE",
            "frequency": "check: 15%  bet: 85%",
            "confidence": "medium",
            "status": "running",
            "fps": 20,
            "elapsed_ms": 61,
        },
        {
            "hero": [],
            "community": [],
            "action": "--",
            "frequency": "",
            "confidence": "",
            "status": "waiting",
            "fps": 0,
            "elapsed_ms": 0,
        },
    ]

    try:
        for i, scenario in enumerate(scenarios):
            print(f"  [{i+1}] {scenario['action']:8s}  {scenario.get('hero_str', ' '.join(scenario['hero'])) or '--'}")
            hud.update(scenario)
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("\n用户中断")

    print()
    print("演示结束，停止 HUD...")
    hud.stop()
    print("HUD 已停止")
    print("=" * 40)


if __name__ == "__main__":
    main()
