"""
screen_capture.py - 高性能屏幕截图

核心思路：
  比 PIL 自带的 ImageGrab 快数倍，因为它直接调用 Windows API 从 DXGI 读显存，
  而不是走 GDI 路径做"回读"。

  使用场景：
    - 截取整个屏幕
    - 截取指定窗口区域
    - 连续截图（用于实时监控循环）

  用法示例：
      cap = ScreenCapture()
      # 截全屏
      img = cap.capture()
      # 截指定区域
      img = cap.capture({"left": 100, "top": 200, "width": 800, "height": 600})
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import mss
    import mss.tools
except ImportError:
    mss = None

logger = logging.getLogger(__name__)

# 可选的输出格式常量
FORMAT_PIL = "pil"       # PIL.Image
FORMAT_NUMPY = "numpy"   # numpy.ndarray (OpenCV 格式: HWC/BGR)
FORMAT_BYTES = "bytes"   # 原始 PNG 字节


class ScreenCapture:
    """高性能屏幕截图器"""

    def __init__(self):
        if mss is None:
            raise ImportError(
                "mss 库未安装。请执行: pip install mss"
            )
        self._sct = mss.mss()
        self._monitors = self._sct.monitors
        logger.info(f"截图器初始化完成，检测到 {len(self._monitors)} 个显示器")

    @property
    def monitor_count(self) -> int:
        """显示器数量"""
        return len(self._monitors) - 1  # monitors[0] 是"所有显示器合并"

    def capture(
        self,
        region: Optional[dict] = None,
        output_format: str = FORMAT_NUMPY,
    ) -> np.ndarray:
        """
        截取屏幕区域

        Args:
            region: 区域字典 {"left", "top", "width", "height"}
                    为 None 时截取主显示器全屏
            output_format: 输出格式 ("numpy" / "pil" / "bytes")

        Returns:
            截图数据，格式由 output_format 决定
        """
        if region is None:
            # 默认截取主显示器（monitors[1]）
            region = self._sct.monitors[1]

        raw = self._sct.grab(region)

        if output_format == FORMAT_BYTES:
            return mss.tools.to_png(raw.rgb, raw.size)

        # 转换为 numpy 数组 (H, W, C)
        img = np.array(raw)

        if output_format == FORMAT_PIL:
            from PIL import Image
            return Image.fromarray(img)

        # FORMAT_NUMPY: OpenCV 默认 BGR 格式
        return img[:, :, :3]  # 去掉 alpha 通道

    def capture_monitor(self, monitor_index: int = 1) -> np.ndarray:
        """截取指定显示器的全屏"""
        if monitor_index < 0 or monitor_index >= len(self._monitors):
            raise ValueError(f"无效显示器索引 {monitor_index}，可用: 1-{len(self._monitors)-1}")
        return self.capture(self._sct.monitors[monitor_index])

    def capture_window_region(self, window_rect: dict) -> np.ndarray:
        """
        截取窗口区域（由 window_manager 提供 rect）

        Args:
            window_rect: {"left", "top", "width", "height"}

        Returns:
            numpy 数组 (HWC/BGR)
        """
        return self.capture(window_rect)

    def save_screenshot(self, filepath: str, region: Optional[dict] = None) -> str:
        """
        截屏并保存为 PNG 文件

        Args:
            filepath: 保存路径
            region: 区域（None=全屏）

        Returns:
            保存的文件路径
        """
        img = self.capture(region, FORMAT_PIL)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        logger.info(f"截图已保存: {path}")
        return str(path)


def quick_capture() -> np.ndarray:
    """快速截取主屏幕（一行调用）"""
    cap = ScreenCapture()
    return cap.capture()
