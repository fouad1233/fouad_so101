"""OpenCV overlay: hand skeleton, per-joint bars, and a 2D arm schematic."""

from __future__ import annotations

import math

import cv2
import numpy as np

from .config import MOTORS, SafetyConfig
from .features import HandDetection
from .kinematics import ArmSchematic

# BGR colors
WHITE = (245, 245, 245)
GREY = (130, 130, 130)
GREEN = (80, 220, 120)
CYAN = (220, 200, 60)
ORANGE = (60, 170, 245)
RED = (60, 60, 235)
PANEL = (35, 35, 35)


def _font(img, text, org, scale=0.5, color=WHITE, thick=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


class Visualizer:
    """Draws all feedback onto the (already mirrored) camera frame."""

    def __init__(self, safety: SafetyConfig, show_schematic: bool = True):
        self._safety = safety
        self._show_schematic = show_schematic
        self._arm = ArmSchematic()

    def draw(
        self,
        frame: np.ndarray,
        detection: HandDetection | None,
        targets: dict[str, float],
        positions: dict[str, float],
        info: dict | None = None,
    ) -> np.ndarray:
        info = info or {}
        if detection is not None:
            self._draw_hand(frame, detection)
        self._draw_joint_panel(frame, targets, positions)
        if self._show_schematic:
            self._draw_schematic(frame, positions)
        self._draw_status(frame, detection, info)
        return frame

    # --- hand / arm skeleton --------------------------------------------
    def _draw_hand(self, frame: np.ndarray, det: HandDetection) -> None:
        pts = det.landmarks_px
        n = len(pts)
        for a, b in det.connections:
            if a < n and b < n:
                cv2.line(frame, tuple(pts[a]), tuple(pts[b]), CYAN, 2, cv2.LINE_AA)
        for x, y in pts:
            cv2.circle(frame, (int(x), int(y)), 4, GREEN, -1, cv2.LINE_AA)

    # --- joint bars ------------------------------------------------------
    def _draw_joint_panel(self, frame, targets, positions) -> None:
        x0, y0, w = 12, 18, 230
        row_h = 26
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0 - 6, y0 - 14),
                      (x0 + w + 70, y0 + row_h * len(MOTORS) + 6), PANEL, -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

        for i, m in enumerate(MOTORS):
            y = y0 + i * row_h
            lo, hi = (0.0, 100.0) if m == "gripper" else (self._safety.clamp_min, self._safety.clamp_max)
            _font(frame, m, (x0, y - 2), 0.42, WHITE)
            bx, by, bw, bh = x0, y + 4, w, 8
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), GREY, 1)

            def to_px(val):
                t = (val - lo) / (hi - lo) if hi > lo else 0.0
                return int(bx + max(0.0, min(1.0, t)) * bw)

            # actual position = filled bar
            cv2.rectangle(frame, (bx, by), (to_px(positions[m]), by + bh), GREEN, -1)
            # target = orange marker
            tx = to_px(targets[m])
            cv2.line(frame, (tx, by - 3), (tx, by + bh + 3), ORANGE, 2)
            _font(frame, f"{positions[m]:6.1f}", (bx + bw + 6, by + bh), 0.4, WHITE)

    # --- arm schematic ---------------------------------------------------
    def _draw_schematic(self, frame, positions) -> None:
        h, w = frame.shape[:2]
        base = (w - 150, h - 70)

        overlay = frame.copy()
        cv2.rectangle(overlay, (w - 300, h - 230), (w - 10, h - 10), PANEL, -1)
        cv2.addWeighted(overlay, 0.40, frame, 0.60, 0, frame)
        _font(frame, "SO-101 (schematic)", (w - 292, h - 210), 0.45, WHITE)

        # side view (lift / elbow / wrist_flex)
        pts = self._arm.side_view_points(positions)
        screen = [(int(base[0] + px), int(base[1] - py)) for px, py in pts]
        cv2.circle(frame, screen[0], 7, WHITE, -1, cv2.LINE_AA)  # base
        for a, b in zip(screen[:-1], screen[1:]):
            cv2.line(frame, a, b, ORANGE, 4, cv2.LINE_AA)
        for p in screen[1:]:
            cv2.circle(frame, p, 4, GREEN, -1, cv2.LINE_AA)

        # gripper indicator at the tip
        opening = self._arm.gripper_opening(positions)
        gap = int(4 + opening * 16)
        tip = screen[-1]
        cv2.line(frame, (tip[0] - gap, tip[1] - 8), (tip[0] - gap, tip[1] + 8), GREEN, 2)
        cv2.line(frame, (tip[0] + gap, tip[1] - 8), (tip[0] + gap, tip[1] + 8), GREEN, 2)

        # base-pan dial (top-down)
        dial = (w - 250, h - 170)
        r = 26
        cv2.circle(frame, dial, r, GREY, 1, cv2.LINE_AA)
        ang = math.radians(self._arm.pan_angle_deg(positions))
        end = (int(dial[0] + r * math.sin(ang)), int(dial[1] - r * math.cos(ang)))
        cv2.line(frame, dial, end, CYAN, 2, cv2.LINE_AA)
        _font(frame, "pan", (dial[0] - 14, dial[1] + r + 14), 0.4, GREY)

    # --- status text -----------------------------------------------------
    def _draw_status(self, frame, detection, info) -> None:
        h, w = frame.shape[:2]
        mode = info.get("mode", "SIM")
        fps = info.get("fps", 0.0)
        paused = info.get("paused", False)

        mode_color = ORANGE if mode == "ROBOT" else GREEN
        _font(frame, f"{mode}", (w - 110, 28), 0.7, mode_color, 2)
        _font(frame, f"{fps:4.1f} fps", (w - 110, 50), 0.5, WHITE)

        if paused:
            _font(frame, "PAUSED (hold)", (w // 2 - 90, 34), 0.7, ORANGE, 2)
        elif detection is None:
            _font(frame, "no target - holding", (w // 2 - 120, 34), 0.7, RED, 2)

        _font(frame, "[q] quit   [space] pause/hold   [h] home", (12, h - 14), 0.5, WHITE)
