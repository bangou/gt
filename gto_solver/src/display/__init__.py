"""
Strategy display and HUD overlay.

Provides a transparent click-through HUD (WS_EX_LAYERED) that floats
above the WePoker game window, showing real-time GTO strategy recommendations.

Usage:
    from display.hud import HudOverlay
    hud = HudOverlay(target_window_title="WePoker")
    hud.start()
    hud.update({"hero": ["Ah", "Kh"], "action": "RAISE", ...})
    # ... when done ...
    hud.stop()
"""

from display.hud import HudOverlay

__all__ = ["HudOverlay"]
