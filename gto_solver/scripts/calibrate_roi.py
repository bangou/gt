"""
WePoker H5 牌面位置标定工具

用法:
    cd gto_solver
    PYTHONPATH="src" python -X utf8 scripts/calibrate_roi.py

功能:
    截取当前屏幕，在 GUI 中调整 Hero 牌框、公共牌 ROI，
    实时预览裁剪结果，最后保存到 config.json。

操作:
    - 拖拽滑块调整 X/Y/宽/高
    - 点击"截图刷新"更新画面
    - 左右箭头微调位置
    - 点击"保存配置"写入 config.json
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


class CalibrationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WePoker H5 — 牌面区域标定")
        self.geometry("1100x750")
        self.resizable(True, True)

        # 当前全屏截图
        self._frame: np.ndarray | None = None
        self._photo: ImageTk.PhotoImage | None = None

        # 控件变量
        self._vars = {
            "hero1_x": tk.IntVar(value=880),
            "hero1_y": tk.IntVar(value=855),
            "hero2_x": tk.IntVar(value=940),
            "hero2_y": tk.IntVar(value=855),
            "hero_w": tk.IntVar(value=50),
            "hero_h": tk.IntVar(value=73),
            "comm_x": tk.IntVar(value=750),
            "comm_y": tk.IntVar(value=460),
            "comm_w": tk.IntVar(value=350),
            "comm_h": tk.IntVar(value=55),
        }

        self._build_ui()
        self._capture_and_display()

    def _build_ui(self):
        # 左侧: 画面预览
        self._canvas = tk.Canvas(self, width=960, height=540, bg="black")
        self._canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # 右侧: 控制面板
        ctrl = ttk.Frame(self, width=220)
        ctrl.pack(side="right", fill="y", padx=5, pady=5)

        ttk.Button(ctrl, text="截图刷新", command=self._capture_and_display).pack(pady=5)

        # 预设
        ttk.Label(ctrl, text="预设分辨率", font=("", 10, "bold")).pack(pady=(10, 0))
        presets = ttk.Frame(ctrl)
        presets.pack()
        ttk.Button(presets, text="1920x1080", command=lambda: self._preset(1920, 1080)).pack(side="left", padx=2)
        ttk.Button(presets, text="2560x1440", command=lambda: self._preset(2560, 1440)).pack(side="left", padx=2)
        ttk.Button(presets, text="3840x2160", command=lambda: self._preset(3840, 2160)).pack(side="left", padx=2)

        # Hero 牌 1
        ttk.Label(ctrl, text="Hero 牌 1", font=("", 10, "bold")).pack(pady=(10, 0))
        self._add_slider(ctrl, "hero1_x", "X", 0, 1920)
        self._add_slider(ctrl, "hero1_y", "Y", 0, 1080)
        self._add_slider(ctrl, "hero_w", "宽", 20, 120)
        self._add_slider(ctrl, "hero_h", "高", 30, 150)

        # Hero 牌 2 (相对偏移)
        ttk.Label(ctrl, text="Hero 牌 2 (偏移)", font=("", 10, "bold")).pack(pady=(10, 0))
        self._hero2_dx = tk.IntVar(value=60)
        self._hero2_dy = tk.IntVar(value=0)
        for label, var, rng in [("X偏移", self._hero2_dx, (20, 120)), ("Y偏移", self._hero2_dy, (-30, 30))]:
            f = ttk.Frame(ctrl)
            f.pack(fill="x", padx=5, pady=1)
            ttk.Label(f, text=label, width=5).pack(side="left")
            ttk.Scale(f, from_=rng[0], to=rng[1], variable=var, orient="horizontal", length=140,
                      command=lambda *a: self._update_vars_from_offset()).pack(side="left")
            ttk.Label(f, textvariable=var, width=4).pack(side="left")

        # 公共牌
        ttk.Label(ctrl, text="公共牌区域", font=("", 10, "bold")).pack(pady=(10, 0))
        self._add_slider(ctrl, "comm_x", "X", 0, 1920)
        self._add_slider(ctrl, "comm_y", "Y", 0, 1080)
        self._add_slider(ctrl, "comm_w", "宽", 100, 600)
        self._add_slider(ctrl, "comm_h", "高", 20, 120)

        # 按钮
        ttk.Button(ctrl, text="保存配置", command=self._save_config).pack(pady=(15, 5))

        self._status = ttk.Label(ctrl, text="就绪")
        self._status.pack()

    def _add_slider(self, parent, key, label, from_, to):
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=5, pady=1)
        ttk.Label(f, text=label, width=5).pack(side="left")
        ttk.Scale(f, from_=from_, to=to, variable=self._vars[key], orient="horizontal", length=160,
                  command=lambda *a: self._redraw()).pack(side="left")
        ttk.Label(f, textvariable=self._vars[key], width=4).pack(side="left")

    def _update_vars_from_offset(self):
        self._vars["hero2_x"].set(self._vars["hero1_x"].get() + self._hero2_dx.get())
        self._vars["hero2_y"].set(self._vars["hero1_y"].get() + self._hero2_dy.get())
        self._redraw()

    def _preset(self, w, h):
        scale_x = w / 1920
        scale_y = h / 1080
        for key in ["hero1_x", "hero2_x", "hero_w", "comm_x", "comm_w"]:
            self._vars[key].set(int(self._vars[key].get() * scale_x))
        for key in ["hero1_y", "hero2_y", "hero_h", "comm_y", "comm_h"]:
            self._vars[key].set(int(self._vars[key].get() * scale_y))

    def _capture_and_display(self):
        try:
            from capture.screen_capture import ScreenCapture
            cap = ScreenCapture()
            self._frame = cap.capture_monitor(1)
            self._status.config(text=f"截图: {self._frame.shape[1]}x{self._frame.shape[0]}")
        except Exception as e:
            self._status.config(text=f"截图失败: {e}")
            return
        self._redraw()

    def _redraw(self):
        if self._frame is None:
            return

        img = self._frame.copy()
        h, w = img.shape[:2]

        # 缩放以适应 canvas
        scale = min(960 / w, 540 / h) if w > 0 else 1.0
        display_w = int(w * scale)
        display_h = int(h * scale)

        # 画 ROI 框
        def draw_roi(x, y, rw, rh, color):
            cv2.rectangle(img, (x, y), (x + rw, y + rh), color, 2)

        v = self._vars
        h1x, h1y, hw, hh = v["hero1_x"].get(), v["hero1_y"].get(), v["hero_w"].get(), v["hero_h"].get()
        h2x, h2y = v["hero2_x"].get(), v["hero2_y"].get()
        draw_roi(h1x, h1y, hw, hh, (0, 255, 0))  # 绿框 = Hero 1
        draw_roi(h2x, h2y, hw, hh, (0, 255, 255))  # 黄框 = Hero 2
        draw_roi(v["comm_x"].get(), v["comm_y"].get(), v["comm_w"].get(), v["comm_h"].get(), (255, 0, 255))  # 紫框 = 公共牌

        # 标注
        cv2.putText(img, "Hero1 (green)", (h1x, h1y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        cv2.putText(img, "Hero2 (yellow)", (h2x, h2y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(img, "Community (purple)", (v["comm_x"].get(), v["comm_y"].get() - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)

        # 缩放到显示尺寸
        display = cv2.resize(img, (display_w, display_h))
        display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)

        self._photo = ImageTk.PhotoImage(Image.fromarray(display_rgb))
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

    def _save_config(self):
        from utils.config import set as cfg_set
        v = self._vars
        cfg_set("hero_card_boxes", [
            [v["hero1_x"].get(), v["hero1_y"].get(), v["hero_w"].get(), v["hero_h"].get()],
            [v["hero2_x"].get(), v["hero2_y"].get(), v["hero_w"].get(), v["hero_h"].get()],
        ])
        cfg_set("community_search_roi", [
            v["comm_x"].get(), v["comm_y"].get(), v["comm_w"].get(), v["comm_h"].get(),
        ])
        cfg_set("reference_width", 1920)
        cfg_set("reference_height", 1080)
        self._status.config(text="配置已保存到 config.json ✅")


if __name__ == "__main__":
    app = CalibrationApp()
    app.mainloop()
