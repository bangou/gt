"""
Transparent HUD Overlay using WS_EX_LAYERED + UpdateLayeredWindow.

Renders GTO strategy recommendations as a click-through transparent
overlay floating above the WePoker game window. Uses per-pixel alpha
via UpdateLayeredWindow for smooth anti-aliased text.

Architecture:
    HudOverlay runs in its own daemon thread. The main recognition
    thread pushes updates via hud.update(data_dict). The render
    loop re-renders only when data changes, at ~20 FPS.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

try:
    import win32gui
    import win32con
    import win32api
except ImportError:
    win32gui = None

logger = logging.getLogger(__name__)

# ── Win32 constants (not all exported by win32con) ──────────────────────

ULW_ALPHA = 2
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1

# CreateDIBitmap flags
CBM_INIT = 4
DIB_RGB_COLORS = 0
BI_RGB = 0

# Window class name (unique per process)
WND_CLASS = "GTO_HUD_Overlay_V1"


class HudOverlay:
    """Transparent click-through HUD overlay above WePoker.

    Usage:
        hud = HudOverlay(target_window_title="WePoker")
        hud.start()
        hud.update({"hero": ["Ah", "Kh"], "action": "RAISE", ...})
        # ... later ...
        hud.stop()
    """

    def __init__(
        self,
        target_window_title: str = "WePoker",
        width: int = 380,
        height: int = 260,
        font_size: int = 16,
    ):
        if win32gui is None:
            raise ImportError("pywin32 is required for HUD overlay. pip install pywin32")

        self.target_title = target_window_title
        self.width = width
        self.height = height
        self.font_size = font_size

        self._hwnd: Optional[int] = None
        self._running = False
        self._lock = threading.Lock()
        self._current_data: dict = {}
        self._thread: Optional[threading.Thread] = None

        # Load fonts once
        self._font, self._big_font, self._small_font = self._load_fonts()

    # ── Font loading ───────────────────────────────────────────────────

    def _load_fonts(self):
        """Load fonts; fall back through multiple paths."""
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/consola.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]

        def try_load(size: int) -> ImageFont.FreeTypeFont:
            for path in font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        return (
            try_load(self.font_size),       # normal
            try_load(self.font_size + 14),  # big (action)
            try_load(self.font_size - 3),   # small (details)
        )

    # ── Window creation ────────────────────────────────────────────────

    def _register_class(self) -> None:
        """Register the window class (idempotent)."""
        hinst = win32api.GetModuleHandle(None)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            if msg == win32con.WM_PAINT:
                # Force re-render
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = wnd_proc
        wc.hInstance = hinst
        wc.lpszClassName = WND_CLASS
        wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH)
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW

        try:
            win32gui.RegisterClass(wc)
        except Exception:
            # Already registered by another HudOverlay instance
            pass

    def _create_window(self) -> None:
        """Create the WS_EX_LAYERED + WS_EX_TRANSPARENT popup window."""
        self._register_class()

        hinst = win32api.GetModuleHandle(None)

        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT   # click-through
            | win32con.WS_EX_TOPMOST        # always on top
            | win32con.WS_EX_NOACTIVATE     # don't steal focus
            | win32con.WS_EX_TOOLWINDOW     # hide from taskbar
        )

        x, y = self._calculate_position()

        self._hwnd = win32gui.CreateWindowEx(
            ex_style,
            WND_CLASS,
            "GTO HUD",
            win32con.WS_POPUP,
            x, y, self.width, self.height,
            0, 0, hinst, None,
        )

        logger.info("HUD window created: hwnd=%d, pos=(%d,%d), size=%dx%d",
                     self._hwnd, x, y, self.width, self.height)

    # ── Positioning ────────────────────────────────────────────────────

    def _find_target_rect(self) -> Optional[tuple[int, int, int, int]]:
        """Find the WePoker window rect. Returns (left, top, right, bottom) or None."""
        results = []

        # WePoker H5 可能在 Edge/Chrome 浏览器里 — 匹配关键词
        # 支持: "WePoker", "wepoker", "WePoker-H5"
        keywords = ["wepoker", "poker"]

        def enum_cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                title = win32gui.GetWindowText(hwnd)
                if title:
                    title_lower = title.lower()
                    if any(kw in title_lower for kw in keywords):
                        rect = win32gui.GetWindowRect(hwnd)
                        results.append((title, rect))
            except Exception:
                pass
            return True

        win32gui.EnumWindows(enum_cb, None)

        if results:
            # 优先选不含 "edge" 的 (独立客户端)
            for title, rect in results:
                if "edge" not in title.lower() and "chrome" not in title.lower():
                    logger.info("HUD target (client): '%s' rect=%s", title[:50], rect)
                    return rect
            # 回退: 包含 WePoker 的 Edge 窗口
            for title, rect in results:
                logger.info("HUD target (browser): '%s' rect=%s", title[:50], rect)
                return rect

        # 最后尝试: 活动窗口
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            if title:
                logger.info("HUD fallback: foreground window '%s'", title[:50])
                return win32gui.GetWindowRect(hwnd)
        except Exception:
            pass

        logger.warning("HUD: no target window found")
        return None

    def _calculate_position(self) -> tuple[int, int]:
        """Where to place the HUD. Prefer top-left area of WePoker window (above cards, below title)."""
        rect = self._find_target_rect()
        if rect:
            left, top, right, bottom = rect
            # Top-left of game area, offset from window edge
            # For browser: game area starts ~80px from top (tabs+title bar), ~8px from left
            x = max(0, left) + 20
            y = max(0, top) + 80
            # Clamp to screen
            screen_w = win32api.GetSystemMetrics(0)
            screen_h = win32api.GetSystemMetrics(1)
            x = max(0, min(x, screen_w - self.width))
            y = max(0, min(y, screen_h - self.height))
            logger.info("HUD position: (%d,%d) from window rect (%d,%d,%d,%d)", x, y, left, top, right, bottom)
            return (x, y)

        # Fallback: upper-left area of primary monitor
        return (50, 100)

    # ── Rendering ──────────────────────────────────────────────────────

    def _render_frame(self, data: dict) -> Image.Image:
        """Render HUD content onto a transparent RGBA image."""
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Semi-transparent dark panel background
        panel_alpha = 170
        margin = 8
        draw.rounded_rectangle(
            [(margin, margin), (self.width - margin, self.height - margin)],
            radius=14,
            fill=(15, 18, 28, panel_alpha),
            outline=(60, 180, 75, 210),   # greenish border
            width=2,
        )

        y = 22
        left_pad = 28

        # ── Hero cards ──
        hero = data.get("hero", [])
        hero_str = "  ".join(hero) if hero else "--  --"
        draw.text((left_pad, y), f"♠ {hero_str}", fill=(255, 255, 255, 255), font=self._font)
        y += 32

        # ── Community cards ──
        comm = data.get("community", [])
        comm_str = "  ".join(comm) if comm else "--  --  --"
        draw.text((left_pad, y), f"♣ {comm_str}", fill=(220, 220, 230, 255), font=self._font)
        y += 36

        # ── Separator ──
        draw.line(
            [(left_pad, y), (self.width - left_pad, y)],
            fill=(70, 75, 90, 180), width=1,
        )
        y += 14

        # ── GTO Action (big, colored) ──
        action = data.get("action", "--")
        action_upper = action.upper()
        action_colors = {
            "RAISE": (80, 255, 80, 255),
            "BET":   (80, 255, 80, 255),
            "CALL":  (255, 255, 80, 255),
            "CHECK": (255, 255, 80, 255),
            "FOLD":  (255, 80, 80, 255),
        }
        color = action_colors.get(action_upper, (255, 255, 255, 255))

        # Action arrow
        arrow = "▶" if action_upper in ("RAISE", "BET") else ("◆" if action_upper in ("CALL", "CHECK") else "■")
        draw.text((left_pad, y), f"{arrow} {action_upper}", fill=color, font=self._big_font)
        y += 44

        # ── Frequencies ──
        freq = data.get("frequency", "")
        if freq:
            draw.text((left_pad, y), freq, fill=(200, 205, 220, 255), font=self._small_font)
            y += 22

        # ── Confidence ──
        conf = data.get("confidence", "")
        if conf:
            conf_colors = {
                "high":   (80, 255, 80, 255),
                "medium": (255, 255, 80, 255),
                "low":    (255, 80, 80, 255),
            }
            c = conf_colors.get(conf, (160, 160, 170, 255))
            draw.text((left_pad, y), f"可信度: {conf.upper()}", fill=c, font=self._small_font)
            y += 22

        # ── Performance ──
        fps = data.get("fps", 0)
        elapsed = data.get("elapsed_ms", 0)
        draw.text(
            (left_pad, y),
            f"FPS: {fps}  延迟: {elapsed}ms",
            fill=(140, 145, 160, 255),
            font=self._small_font,
        )
        y += 20

        # ── Status indicator ──
        status = data.get("status", "idle")
        status_colors = {
            "running":  (80, 255, 80, 255),
            "idle":     (140, 145, 160, 255),
            "waiting":  (255, 200, 80, 255),
            "error":    (255, 80, 80, 255),
        }
        sc = status_colors.get(status, (140, 145, 160, 255))
        status_text = {
            "running": "● 识别中",
            "idle":    "○ 待机",
            "waiting": "◐ 等待回合",
            "error":   "✕ 错误",
        }.get(status, "○ 待机")
        draw.text((left_pad, y), status_text, fill=sc, font=self._small_font)

        return img

    # ── Window update ──────────────────────────────────────────────────

    def _update_window(self, img: Image.Image) -> None:
        """Blit the rendered RGBA image to the layered window.

        Uses UpdateLayeredWindow with per-pixel alpha for smooth
        anti-aliased text on a fully transparent background.
        """
        if self._hwnd is None:
            return

        hdc_screen = win32gui.GetDC(0)
        hdc_mem = win32gui.CreateCompatibleDC(hdc_screen)

        # Build BITMAPINFOHEADER (40 bytes)
        # typedef struct {
        #   DWORD biSize; LONG biWidth; LONG biHeight; WORD biPlanes;
        #   WORD biBitCount; DWORD biCompression; ...
        # } BITMAPINFOHEADER;
        bmi = (ctypes.c_ubyte * 44)()       # BITMAPINFO = header (40) + one RGBA mask (4)
        ctypes.c_uint32.from_buffer(bmi, 0).value = 40       # biSize
        ctypes.c_int32.from_buffer(bmi, 4).value = self.width
        ctypes.c_int32.from_buffer(bmi, 8).value = -self.height  # negative = top-down
        ctypes.c_uint16.from_buffer(bmi, 12).value = 1       # biPlanes
        ctypes.c_uint16.from_buffer(bmi, 14).value = 32      # biBitCount
        ctypes.c_uint32.from_buffer(bmi, 16).value = BI_RGB

        # Raw BGRA pixel data
        rgba = img.tobytes("raw", "BGRA")
        buf = (ctypes.c_ubyte * len(rgba)).from_buffer_copy(rgba)

        hbm = ctypes.windll.gdi32.CreateDIBitmap(
            ctypes.c_void_p(hdc_screen),
            ctypes.cast(bmi, ctypes.c_void_p),
            CBM_INIT,
            ctypes.cast(buf, ctypes.c_void_p),
            ctypes.cast(bmi, ctypes.c_void_p),
            DIB_RGB_COLORS,
        )

        if not hbm:
            logger.error("CreateDIBitmap failed")
            win32gui.DeleteDC(hdc_mem)
            win32gui.ReleaseDC(0, hdc_screen)
            return

        old_bmp = win32gui.SelectObject(hdc_mem, hbm)

        # BLENDFUNCTION for per-pixel alpha
        bf = (ctypes.c_ubyte * 4)()
        bf[0] = AC_SRC_OVER
        bf[1] = 0       # reserved
        bf[2] = 255     # SourceConstantAlpha (opaque blend; alpha from pixel)
        bf[3] = AC_SRC_ALPHA

        x, y = self._calculate_position()

        # UpdateLayeredWindow
        ctypes.windll.user32.UpdateLayeredWindow(
            ctypes.c_void_p(self._hwnd),
            ctypes.c_void_p(hdc_screen),
            ctypes.byref(ctypes.c_int(x)),
            ctypes.byref(ctypes.c_int(y)),
            ctypes.byref(ctypes.c_int(self.width)),
            ctypes.byref(ctypes.c_int(self.height)),
            ctypes.c_void_p(hdc_mem),
            ctypes.byref(ctypes.c_int(0)),   # ptSrc.x
            ctypes.byref(ctypes.c_int(0)),   # ptSrc.y
            0,                                # crKey
            ctypes.cast(bf, ctypes.c_void_p),
            ULW_ALPHA,
        )

        # Cleanup
        win32gui.SelectObject(hdc_mem, old_bmp)
        ctypes.windll.gdi32.DeleteObject(ctypes.c_void_p(hbm))
        win32gui.DeleteDC(hdc_mem)
        win32gui.ReleaseDC(0, hdc_screen)

    # ── Public API ─────────────────────────────────────────────────────

    def update(self, data: dict) -> None:
        """Thread-safe push of new display data. Call from any thread."""
        with self._lock:
            self._current_data = data.copy()

    def start(self) -> None:
        """Launch the HUD overlay in a daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("HUD already running")
            return

        self._thread = threading.Thread(target=self._render_loop, daemon=True, name="HUD-Render")
        self._thread.start()
        logger.info("HUD overlay started")

    def stop(self) -> None:
        """Stop the HUD overlay and destroy the window."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        if self._hwnd:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception as exc:
                logger.debug("Error destroying HUD window: %s", exc)
            self._hwnd = None

        logger.info("HUD overlay stopped")

    def is_running(self) -> bool:
        return self._running and self._hwnd is not None

    # ── Render loop (background thread) ────────────────────────────────

    def _render_loop(self) -> None:
        """Background render loop. Re-renders when data changes, at ~20 FPS."""
        try:
            self._create_window()
        except Exception as exc:
            logger.error("Failed to create HUD window: %s", exc, exc_info=True)
            return

        win32gui.ShowWindow(self._hwnd, win32con.SW_SHOW)
        self._running = True

        last_hash: Optional[int] = None

        while self._running:
            with self._lock:
                data = self._current_data.copy()

            current_hash = hash(str(data))
            if current_hash != last_hash:
                try:
                    img = self._render_frame(data)
                    self._update_window(img)
                    last_hash = current_hash
                except Exception as exc:
                    logger.error("HUD render error: %s", exc)

            time.sleep(0.05)  # ~20 FPS

        # Cleanup
        if self._hwnd:
            try:
                win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = None
