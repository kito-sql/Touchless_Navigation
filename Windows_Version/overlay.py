"""
overlay.py
Transparent fullscreen overlay for Windows kiosk/desktop applications.
Renders the 21 MediaPipe hand landmarks as an auto-scaling, high-contrast skeleton.
Supports direct shared state binding or standalone WebSocket execution.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import math
import time
from typing import List, Optional, Tuple

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QPointF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QRadialGradient
from PyQt5.QtWidgets import QApplication, QWidget

import websockets

WS_URI = "ws://127.0.0.1:8765"
RECONNECT_SEC = 1.5
REFRESH_MS = 16
FADE_SPEED = 0.12

HAND_CONNECTIONS: List[Tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]

_DWELL_GREEN_LOAD = QColor(57, 255, 20)
_DWELL_TRACK_BG = QColor(15, 60, 35, 140)
_FINGERTIPS = {4, 8, 12, 16, 20}

class OverlayWindow(QWidget):
    """Transparent, frameless, stay-on-top window for hand skeleton rendering on Windows."""

    def __init__(self, shared_state=None, geometry_callback=None) -> None:
        super().__init__()
        self._shared_state = shared_state
        self._geometry_callback = geometry_callback

        self._pending_geo = None
        self._landmarks: List[List[float]] = []
        self._world_landmarks: List[List[float]] = []
        self._hand_detected: bool = False
        self._gesture: str = "NONE"
        self._cursor_state: str = "MOVE"
        self._cursor_x: int = 0
        self._cursor_y: int = 0
        self._skel_anchor_x: float = 0.0
        self._skel_anchor_y: float = 0.0
        self._connected: bool = True
        self._dwell_progress: float = 0.0
        self._depth_z: float = 1.0

        self._fade_alpha: float = 0.0
        self._click_pulse: float = 0.0
        self._ghost_protect: int = 0
        self._new_data: bool = False

        flags = (
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._screen = QApplication.primaryScreen()
        screen_geo = self._screen.geometry()
        self.setGeometry(screen_geo)

        self._engine_scale_x: float = float(self.width())
        self._engine_scale_y: float = float(self.height())
        self._engine_w: int = self.width()
        self._engine_h: int = self.height()

        self._screen.geometryChanged.connect(self._on_screen_geometry_changed)
        self._geo_debounce = QTimer(self)
        self._geo_debounce.setSingleShot(True)
        self._geo_debounce.timeout.connect(self._flush_geometry_update)

        if self._geometry_callback:
            geo = self._screen.geometry()
            self._geometry_callback(geo.width(), geo.height())

        if self._shared_state is None:
            self._start_ws_client()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(REFRESH_MS)

        self.showFullScreen()
        self.raise_()

    def _start_ws_client(self) -> None:
        def run():
            async def client():
                while True:
                    try:
                        async with websockets.connect(WS_URI) as ws:
                            self._on_connect(True)
                            async for message in ws:
                                try:
                                    data = json.loads(message)
                                    self._on_data(data)
                                except Exception:
                                    pass
                    except Exception:
                        self._on_connect(False)
                        await asyncio.sleep(RECONNECT_SEC)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(client())
        threading.Thread(target=run, daemon=True, name="OverlayWSClient").start()

    def _on_connect(self, connected: bool) -> None:
        self._connected = connected
        if connected and self._geometry_callback:
            geo = self._screen.geometry()
            self._geometry_callback(geo.width(), geo.height())

    def _on_screen_geometry_changed(self, geo) -> None:
        self._pending_geo = (geo.width(), geo.height())
        self._geo_debounce.start(250)

    def _flush_geometry_update(self) -> None:
        if self._pending_geo is None:
            return
        w, h = self._pending_geo
        self._pending_geo = None
        geo = self._screen.geometry()
        self.setGeometry(geo)
        if self._geometry_callback:
            self._geometry_callback(geo.width(), geo.height())

    def _on_data(self, data: dict) -> None:
        prev_state = self._cursor_state
        new_hand_detected = data.get("hand_detected", False)
        new_state = data.get("state", "MOVE")
        new_x = data.get("x", 0)
        new_y = data.get("y", 0)
        new_skel_x = data.get("skel_anchor_x", 0)
        new_skel_y = data.get("skel_anchor_y", 0)
        new_progress = data.get("dwell_progress", 0.0)

        if (new_hand_detected != self._hand_detected or
            new_state != self._cursor_state or
            new_x != self._cursor_x or new_y != self._cursor_y or
            new_skel_x != self._skel_anchor_x or new_skel_y != self._skel_anchor_y or
            abs(new_progress - self._dwell_progress) > 0.001):
            self._new_data = True

        self._hand_detected = new_hand_detected
        self._landmarks = data.get("landmarks", [])
        self._world_landmarks = data.get("world_landmarks", [])
        self._gesture = data.get("gesture", "NONE")
        self._cursor_state = new_state
        self._cursor_x = new_x
        self._cursor_y = new_y
        self._skel_anchor_x = new_skel_x
        self._skel_anchor_y = new_skel_y
        self._dwell_progress = new_progress
        self._depth_z = data.get("depth_z", 1.0)

        self._engine_w = self.width()
        self._engine_h = self.height()

        if self._cursor_state == "CLICK" and prev_state != "CLICK":
            self._click_pulse = 1.0
            self._ghost_protect = 20

    def _tick(self) -> None:
        if self._shared_state:
            snap = self._shared_state.snapshot()
            self._on_data(snap)
            self._connected = True

        if self._ghost_protect > 0:
            self._ghost_protect -= 1
            effective_detected = True
        else:
            effective_detected = self._hand_detected

        target = 1.0 if effective_detected else 0.0
        animating = False

        if abs(self._fade_alpha - target) > 0.001:
            self._fade_alpha += (target - self._fade_alpha) * FADE_SPEED
            animating = True
        else:
            self._fade_alpha = target

        if self._click_pulse > 0.0:
            self._click_pulse = max(0.0, self._click_pulse - 0.08)
            animating = True

        if animating or self._new_data:
            self.update()
            self._new_data = False

    def paintEvent(self, _event) -> None:
        if getattr(self, '_fade_alpha', 0.0) < 0.01:
            return

        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._fade_alpha > 0.01 and len(self._landmarks) == 21:
            self._draw_skeleton(painter, w, h)

        painter.end()

    def _draw_skeleton(self, painter: QPainter, w: int, h: int) -> None:
        alpha = self._fade_alpha
        lms = self._landmarks

        if len(lms) < 21 or not all(isinstance(lm, (list, tuple)) and len(lm) >= 2 for lm in lms):
            return

        anchor_norm_x, anchor_norm_y = lms[8][0], lms[8][1]
        anchor_norm_z = lms[8][2] if len(lms[8]) > 2 else 0.0
        anchor_screen_x = float(getattr(self, '_skel_anchor_x', self._cursor_x))
        anchor_screen_y = float(getattr(self, '_skel_anchor_y', self._cursor_y))

        def clamp(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, v))

        depth_val = max(0.65, min(1.6, float(getattr(self, '_depth_z', 1.0))))
        SKELETON_SCALE = clamp(depth_val ** 0.5, 0.80, 1.30)

        base_size = min(self._engine_w, self._engine_h)
        skel_scale_x = base_size * 0.85
        skel_scale_y = base_size * 0.85
        MAX_BONE_PX = base_size * 0.45

        # 3D Perspective Projection & Per-Landmark Z-Depth
        px_lms: List[QPointF] = []
        z_depths: List[float] = []
        z_scale_factors: List[float] = []

        for lm in lms:
            nx, ny = lm[0], lm[1]
            nz = lm[2] if len(lm) > 2 else 0.0

            dx_norm = nx - anchor_norm_x
            dy_norm = ny - anchor_norm_y
            dz_norm = nz - anchor_norm_z

            persp_factor = clamp(1.0 / (1.0 + dz_norm * 1.8), 0.5, 1.8)
            per_lm_scale = SKELETON_SCALE * persp_factor

            dx_px = clamp(dx_norm * skel_scale_x * per_lm_scale, -MAX_BONE_PX, MAX_BONE_PX)
            dy_px = clamp(dy_norm * skel_scale_y * per_lm_scale, -MAX_BONE_PX, MAX_BONE_PX)

            sx = anchor_screen_x - dx_px
            sy = anchor_screen_y + dy_px
            px_lms.append(QPointF(sx, sy))
            z_depths.append(dz_norm)
            z_scale_factors.append(persp_factor)

        active_connections = list(HAND_CONNECTIONS)

        # Painter's Algorithm: Sort connections by average Z-depth (furthest first)
        connection_depths = []
        for a, b in active_connections:
            if a < len(z_depths) and b < len(z_depths):
                avg_z = (z_depths[a] + z_depths[b]) / 2.0
                connection_depths.append((avg_z, a, b))

        connection_depths.sort(key=lambda item: item[0], reverse=True)

        # Draw bones with 3D Depth-aware stroke width & shading
        for avg_z, a, b in connection_depths:
            if a < len(px_lms) and b < len(px_lms):
                dx = px_lms[a].x() - px_lms[b].x()
                dy = px_lms[a].y() - px_lms[b].y()
                if (dx * dx + dy * dy) >= 4.0:
                    depth_shade = clamp(1.0 - avg_z * 1.8, 0.4, 1.4)
                    black_alpha = int(clamp(210 * alpha * depth_shade, 60, 240))
                    white_alpha = int(clamp(235 * alpha * depth_shade, 80, 255))

                    BLACK_OUT = QColor(0, 0, 0, black_alpha)
                    WHITE_CORE = QColor(240, 245, 255, white_alpha)

                    line_width_blk = max(3.0, 8.0 * SKELETON_SCALE * depth_shade)
                    line_width_wht = max(1.2, 2.5 * SKELETON_SCALE * depth_shade)

                    painter.setPen(QPen(BLACK_OUT, line_width_blk, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawLine(px_lms[a], px_lms[b])
                    painter.setPen(QPen(WHITE_CORE, line_width_wht, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawLine(px_lms[a], px_lms[b])

        # Painter's Algorithm: Sort Joint Nodes by Z-depth (furthest first)
        joint_indices = list(range(len(px_lms)))
        joint_indices.sort(key=lambda idx: z_depths[idx], reverse=True)

        painter.setPen(Qt.NoPen)
        rendered_points: List[QPointF] = []
        dedup_dist_sq = 16.0 * SKELETON_SCALE * SKELETON_SCALE

        for idx in joint_indices:
            if idx >= len(px_lms):
                continue
            pos = px_lms[idx]

            too_close = False
            for r_pos in rendered_points:
                dx = pos.x() - r_pos.x()
                dy = pos.y() - r_pos.y()
                if (dx * dx + dy * dy) < dedup_dist_sq:
                    too_close = True
                    break

            if too_close:
                continue

            rendered_points.append(pos)
            node_z = z_depths[idx]
            depth_shade = clamp(1.0 - node_z * 1.8, 0.4, 1.4)
            persp_scale = z_scale_factors[idx]

            radius = int(max(4, (9 if idx in _FINGERTIPS else 6) * SKELETON_SCALE * persp_scale * (0.8 + 0.2 * depth_shade)))

            glow_alpha = int(clamp(55 * alpha * depth_shade, 15, 120))
            black_alpha = int(clamp(210 * alpha * depth_shade, 60, 240))
            white_alpha = int(clamp(235 * alpha * depth_shade, 80, 255))

            WHITE_GLOW = QColor(200, 215, 255, glow_alpha)
            BLACK_OUT = QColor(0, 0, 0, black_alpha)
            WHITE_CORE = QColor(240, 245, 255, white_alpha)

            grad = QRadialGradient(pos, radius * 2)
            grad.setColorAt(0.0, WHITE_GLOW)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(pos, radius * 2, radius * 2)

            painter.setBrush(QBrush(BLACK_OUT))
            painter.drawEllipse(pos, radius + 3, radius + 3)

            painter.setBrush(QBrush(WHITE_CORE))
            painter.drawEllipse(pos, radius, radius)

        if len(lms) >= 9:
            tip_pos = QPointF(anchor_screen_x, anchor_screen_y)
            arc_r = int(max(14, 20 * SKELETON_SCALE))
            rect_x = int(tip_pos.x() - arc_r)
            rect_y = int(tip_pos.y() - arc_r)
            rect_d = arc_r * 2

            track_alpha = int(160 * alpha)
            if track_alpha > 0:
                painter.setPen(QPen(QColor(0, 0, 0, int(200 * alpha)), 4.5, Qt.SolidLine, Qt.RoundCap))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(rect_x, rect_y, rect_d, rect_d)

                track_col = QColor(_DWELL_TRACK_BG)
                track_col.setAlpha(track_alpha)
                painter.setPen(QPen(track_col, 3.0, Qt.SolidLine, Qt.RoundCap))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(rect_x, rect_y, rect_d, rect_d)

            if self._dwell_progress > 0.01:
                pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0)
                glow_alpha = int((90 + 50 * pulse) * alpha)
                glow_col = QColor(57, 255, 20, glow_alpha)
                glow_pen = QPen(glow_col, 5.0, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(rect_x, rect_y, rect_d, rect_d)

            if self._dwell_progress > 0.001:
                span_deg = self._dwell_progress * 360.0
                arc_alpha = int((0.85 + 0.15 * self._dwell_progress) * 255 * alpha)
                arc_col = QColor(_DWELL_GREEN_LOAD)
                arc_col.setAlpha(arc_alpha)
                pen_w = 3.5 + self._dwell_progress * 1.0

                start_angle = 90 * 16
                span_angle = -int(span_deg * 16)

                border_pen_w = pen_w + 2.0
                border_col = QColor(0, 0, 0, int(220 * alpha))
                painter.setPen(QPen(border_col, border_pen_w, Qt.SolidLine, Qt.RoundCap))
                painter.setBrush(Qt.NoBrush)
                painter.drawArc(rect_x, rect_y, rect_d, rect_d, start_angle, span_angle)

                painter.setPen(QPen(arc_col, pen_w, Qt.SolidLine, Qt.RoundCap))
                painter.setBrush(Qt.NoBrush)
                painter.drawArc(rect_x, rect_y, rect_d, rect_d, start_angle, span_angle)

        if self._click_pulse > 0.01 and len(lms) >= 9:
            tip_pos = QPointF(anchor_screen_x, anchor_screen_y)
            pulse_r = int((20 + (1.0 - self._click_pulse) * 35) * SKELETON_SCALE)
            ring_alpha = int(self._click_pulse * 230 * alpha)
            ring_color = QColor(57, 255, 20, ring_alpha)
            painter.setPen(QPen(ring_color, 4.5 * SKELETON_SCALE))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(tip_pos, pulse_r, pulse_r)

    def closeEvent(self, event) -> None:
        super().closeEvent(event)

def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("GestureOverlay")
    window = OverlayWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()