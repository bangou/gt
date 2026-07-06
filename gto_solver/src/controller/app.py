"""
GTO Strategy Assistant — 主界面与事件循环

用法:
    cd gto_solver
    python -m src.controller.app

功能:
    - "开始识别"按钮 → 启动后台识别线程
    - 每周期: 截图 → 5帧投票 → 识别 → 显示 → 存临时库
    - "停止识别"按钮 → 停止识别线程
    - 关闭窗口 → 临时库去重入库 → 清空临时库
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

import cv2
import numpy as np

# 将 src/ 加入路径，确保模块可导入
import sys
_src = Path(__file__).resolve().parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def _get_matcher():
    """延迟导入 CardMatcher（避免启动慢）。"""
    from recognition.card_templates import CardMatcher
    return CardMatcher()


def _get_voter():
    from recognition.multi_frame import MultiFrameVoter
    return MultiFrameVoter(frames=5, majority_threshold=0.6)


def _get_temp_db():
    from utils.temp_db import TempDB
    return TempDB("data/temp/temp_cards.db")


def _get_config():
    from utils.config import get, get_all
    return get_all()


# ── 识别线程 ────────────────────────────────────────────────────────

class RecognitionThread(threading.Thread):
    """后台识别线程: 持续截图 → 5帧投票 → 推送结果到 UI 队列。"""

    def __init__(self, result_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.queue = result_queue
        self.stop = stop_event
        self._capture = None
        self._matcher = None
        self._voter = None
        self._temp_db = None
        self._config = None

    def run(self) -> None:
        # 懒初始化（在线程内避免 tkinter 冲突）
        try:
            from capture.screen_capture import ScreenCapture
            self._capture = ScreenCapture()
        except Exception as e:
            self.queue.put(("error", f"截图模块初始化失败: {e}"))
            return

        self._matcher = _get_matcher()
        self._voter = _get_voter()
        self._temp_db = _get_temp_db()
        self._config = _get_config()

        # GTO 桥接
        from parser.game_state_bridge import GameStateBridge
        bridge = GameStateBridge()

        hero_boxes_raw = self._config.get("hero_card_boxes", [[908, 873, 50, 73], [963, 873, 50, 73]])
        hero_boxes = [tuple(b) for b in hero_boxes_raw]
        comm_roi_raw = self._config.get("community_search_roi", [800, 465, 300, 50])
        comm_roi = tuple(comm_roi_raw)

        # 行动触发检测
        try:
            from recognition.action_detector import ActionTrigger
            action_roi_raw = self._config.get("hero_action_roi", None)
            action_trigger = ActionTrigger(
                action_roi=tuple(action_roi_raw) if action_roi_raw else None,
            )
        except Exception:
            action_trigger = None

        # 数字读取
        try:
            from recognition.number_reader import NumberReader
            number_reader = NumberReader()
        except Exception:
            number_reader = None

        cycle = 0
        while not self.stop.is_set():
            cycle += 1
            t0 = time.perf_counter()

            def capture():
                try:
                    return self._capture.capture_monitor(1)
                except Exception:
                    return None

            # 行动触发检测
            is_turn = False
            if action_trigger is not None:
                frame_sample = capture()
                is_turn = action_trigger.is_hero_turn(frame_sample) if frame_sample is not None else False
            else:
                is_turn = True  # 无检测器时默认开启

            gto_result = None
            hero_names: list[str] = []
            hero_confs: list[float] = []
            comm_names: list[str] = []

            if is_turn:
                # Hero 5帧投票
                hero_names, hero_confs = self._voter.vote_hero_cards(
                    capture, hero_boxes, self._matcher, self._temp_db,
                )

                # 公共牌 5帧投票
                if hero_names:
                    comm_names = self._voter.vote_community_cards(
                        capture, comm_roi, self._matcher, self._temp_db,
                    )

                # GTO 查询
                if hero_names:
                    try:
                        query_json = bridge.build_from_recognized(
                            hero_names=hero_names,
                            community_names=comm_names,
                            table_size=6,
                        )
                        gto_result = bridge.query_gto(query_json)
                    except Exception:
                        gto_result = None

            elapsed = (time.perf_counter() - t0) * 1000
            fps = 1000 / max(elapsed, 1)

            self.queue.put((
                "result",
                {
                    "hero": hero_names,
                    "hero_confs": hero_confs,
                    "community": comm_names,
                    "fps": round(fps),
                    "cycle": cycle,
                    "elapsed_ms": round(elapsed, 1),
                    "temp_count": self._temp_db.count(),
                    "template_count": len(self._matcher.templates),
                    "is_turn": is_turn,
                    "gto": gto_result,
                },
            ))

            # 如果没找到牌或不是自己的回合，等久一点（节省 CPU）
            if not hero_names or not is_turn:
                time.sleep(0.3)


# ── 主界面 ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GTO Strategy Assistant")
        self.geometry("500x480")
        self.resizable(True, True)

        self.result_queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: RecognitionThread | None = None
        self._temp_db = _get_temp_db()
        self._hud: object | None = None  # HudOverlay or None

        self._build_ui()
        self._poll_queue()

        # 窗口关闭 → 入库清理
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}

        # 控制按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        self.btn_start = ttk.Button(btn_frame, text="开始识别", command=self._start)
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = ttk.Button(btn_frame, text="停止识别", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=5)

        # 状态栏
        self.lbl_status = ttk.Label(self, text="状态: 就绪", font=("", 10, "bold"))
        self.lbl_status.pack(anchor="w", **pad)

        # 分隔线
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # 识别结果
        card_frame = ttk.LabelFrame(self, text="识别结果")
        card_frame.pack(fill="x", **pad)

        self.lbl_hero = ttk.Label(card_frame, text="手牌: --", font=("Consolas", 14))
        self.lbl_hero.pack(anchor="w", **pad)

        self.lbl_comm = ttk.Label(card_frame, text="公共牌: --", font=("Consolas", 14))
        self.lbl_comm.pack(anchor="w", **pad)

        self.lbl_vote = ttk.Label(card_frame, text="投票: --")
        self.lbl_vote.pack(anchor="w", **pad)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # GTO 策略建议
        gto_frame = ttk.LabelFrame(self, text="GTO 建议")
        gto_frame.pack(fill="x", **pad)

        self.lbl_gto_action = ttk.Label(gto_frame, text="推荐动作: --", font=("Consolas", 12, "bold"))
        self.lbl_gto_action.pack(anchor="w", **pad)

        self.lbl_gto_freq = ttk.Label(gto_frame, text="频率: --", font=("Consolas", 10))
        self.lbl_gto_freq.pack(anchor="w", **pad)

        self.lbl_gto_conf = ttk.Label(gto_frame, text="可信度: --")
        self.lbl_gto_conf.pack(anchor="w", **pad)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # 性能信息
        perf_frame = ttk.LabelFrame(self, text="性能")
        perf_frame.pack(fill="x", **pad)

        self.lbl_fps = ttk.Label(perf_frame, text="帧率: --")
        self.lbl_fps.pack(anchor="w", **pad)

        self.lbl_cycle = ttk.Label(perf_frame, text="周期: 0")
        self.lbl_cycle.pack(anchor="w", **pad)

        self.lbl_elapsed = ttk.Label(perf_frame, text="耗时: -- ms")
        self.lbl_elapsed.pack(anchor="w", **pad)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)

        # 模板库状态
        tmpl_frame = ttk.LabelFrame(self, text="模板库")
        tmpl_frame.pack(fill="x", **pad)

        self.lbl_templates = ttk.Label(tmpl_frame, text="正式库: -- 张")
        self.lbl_templates.pack(anchor="w", **pad)

        self.lbl_temp = ttk.Label(tmpl_frame, text="临时库: -- 张")
        self.lbl_temp.pack(anchor="w", **pad)

        # 日志区域
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=2)
        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(log_frame, height=6, font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=2)

        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    # ── 日志 ─────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── 开始/停止 ────────────────────────────────────────────────

    def _start(self) -> None:
        self._log("启动识别线程...")
        self.stop_event.clear()
        self.thread = RecognitionThread(self.result_queue, self.stop_event)
        self.thread.start()
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="状态: 识别中...")

        # 启动 HUD 悬浮窗
        self._start_hud()

    def _stop(self) -> None:
        self._log("停止识别线程...")
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="状态: 已停止")

        # 停止 HUD
        self._stop_hud()

    # ── HUD 管理 ────────────────────────────────────────────────

    def _start_hud(self) -> None:
        """启动透明 HUD 悬浮窗。"""
        try:
            from display.hud import HudOverlay
            self._hud = HudOverlay(
                target_window_title="WePoker",
                width=380,
                height=260,
                font_size=16,
            )
            self._hud.start()
            self._log("HUD 悬浮窗已启动")
        except ImportError as e:
            self._log(f"HUD 启动失败 (缺少依赖): {e}")
            self._hud = None
        except Exception as e:
            self._log(f"HUD 启动失败: {e}")
            self._hud = None

    def _stop_hud(self) -> None:
        """停止 HUD 悬浮窗。"""
        if self._hud is not None:
            try:
                self._hud.stop()
                self._log("HUD 悬浮窗已停止")
            except Exception as e:
                self._log(f"HUD 停止出错: {e}")
            self._hud = None

    def _update_hud(self, hero: list[str], comm: list[str], gto: dict | None, data: dict) -> None:
        """将最新数据推送到 HUD 悬浮窗。"""
        if self._hud is None:
            return

        try:
            hud_data: dict = {
                "hero": hero,
                "community": comm,
                "fps": data.get("fps", 0),
                "elapsed_ms": data.get("elapsed_ms", 0),
            }

            is_turn = data.get("is_turn", True)
            if not is_turn:
                hud_data["status"] = "waiting"
                hud_data["action"] = "--"
            elif gto and gto.get("status") == "success":
                hud_data["status"] = "running"
                strategy = gto.get("strategy", {})
                range_info = gto.get("range_info", {})
                hud_data["action"] = range_info.get("recommended_action", "--")

                # 组装频率字符串
                freq_parts = []
                for action in ["fold", "check", "call", "bet", "raise"]:
                    if action in strategy and isinstance(strategy[action], (int, float)):
                        freq_parts.append(f"{action}: {strategy[action]:.0f}%")
                hud_data["frequency"] = "  ".join(freq_parts) if freq_parts else ""

                hud_data["confidence"] = gto.get("confidence", "unknown")
                equity = range_info.get("equity", 0)
                if equity:
                    hud_data["frequency"] += f"  |  Equity: {equity:.1f}%"
            elif hero:
                hud_data["status"] = "running"
                hud_data["action"] = "识别中..."
            else:
                hud_data["status"] = "idle"
                hud_data["action"] = "--"

            self._hud.update(hud_data)
        except Exception:
            pass  # HUD 更新失败不影响主界面

    # ── 关闭 ─────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self._log("正在关闭...")
        self._stop()

        # 去重入库
        temp_count = self._temp_db.count()
        if temp_count > 0:
            self._log(f"临时库有 {temp_count} 张牌面，开始去重入库...")
            try:
                new_count = self._temp_db.dedup_and_merge()
                self._log(f"入库完成: 新增 {new_count} 张模板")
            except Exception as e:
                self._log(f"入库出错: {e}")
            self._temp_db.clear()
            self._log("临时库已清理")
        else:
            self._log("临时库为空，跳过入库")

        self.destroy()

    # ── 队列轮询 ─────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        """每 50ms 检查结果队列，更新 UI。"""
        try:
            while True:
                msg_type, data = self.result_queue.get_nowait()
                if msg_type == "error":
                    self._log(f"错误: {data}")
                    self.lbl_status.config(text="状态: 错误")
                elif msg_type == "result":
                    self._update_display(data)
        except queue.Empty:
            pass

        self.after(50, self._poll_queue)

    def _update_display(self, data: dict) -> None:
        """更新 UI 显示。"""
        hero = data["hero"]
        comm = data["community"]
        confs = data.get("hero_confs", [])
        gto = data.get("gto")
        is_turn = data.get("is_turn", True)

        if hero:
            hero_str = " ".join(
                f"{n}({c:.0%})" for n, c in zip(hero, confs)
            ) if confs else " ".join(hero)
            self.lbl_hero.config(text=f"手牌: {hero_str}")
        elif not is_turn:
            self.lbl_hero.config(text="手牌: 等待回合...")
        else:
            self.lbl_hero.config(text="手牌: --")

        if comm:
            self.lbl_comm.config(text=f"公共牌: {' '.join(comm)}")
        else:
            self.lbl_comm.config(text="公共牌: --")

        vote_count = len([h for h in hero if h])
        self.lbl_vote.config(
            text=f"投票: {vote_count}/2  多数阈值: 3/5  {'✅ 通过' if hero else '⏳ 等待'}"
        )

        # GTO 策略显示
        if gto and gto.get("status") == "success":
            strategy = gto.get("strategy", {})
            range_info = gto.get("range_info", {})
            confidence = gto.get("confidence", "unknown")

            # 组装频率字符串
            freq_parts = []
            for action in ["fold", "check", "call", "bet", "raise"]:
                if action in strategy and isinstance(strategy[action], (int, float)):
                    freq_parts.append(f"{action}: {strategy[action]:.0f}%")
            freq_str = "  ".join(freq_parts) if freq_parts else "--"

            self.lbl_gto_action.config(
                text=f"推荐动作: {range_info.get('recommended_action', '--').upper()}"
            )
            self.lbl_gto_freq.config(text=f"频率: {freq_str}")

            conf_color = {"high": "绿色", "medium": "黄色", "low": "红色"}.get(confidence, "")
            self.lbl_gto_conf.config(text=f"可信度: {confidence} ({conf_color})")

            # ── 更新 HUD 悬浮窗 ──
            self._update_hud(hero, comm, gto, data)
        else:
            self.lbl_gto_action.config(text="推荐动作: --")
            self.lbl_gto_freq.config(text="频率: --")
            self.lbl_gto_conf.config(text="可信度: --")

            # HUD 也更新手牌/公共牌（即使没有 GTO 结果）
            self._update_hud(hero, comm, gto, data)

        self.lbl_fps.config(text=f"帧率: {data['fps']} fps")
        self.lbl_cycle.config(text=f"周期: {data['cycle']}")
        self.lbl_elapsed.config(text=f"耗时: {data['elapsed_ms']} ms")
        self.lbl_templates.config(text=f"正式库: {data['template_count']} 张")
        self.lbl_temp.config(text=f"临时库: {data['temp_count']} 张")


# ── 入口 ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
