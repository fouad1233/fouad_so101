"""Whole-arm detection: webcam frame -> normalized features from your shoulder/elbow/wrist.

Implements the same :class:`HandDetector` contract as the hand tracker, so the mapper, smoother,
safety and URDF viewer are all reused unchanged. The arm drives the joints like this:

* wrist position relative to your shoulder  -> base pan + shoulder lift,
* your actual elbow bend                    -> robot elbow,
* forearm up/down                           -> wrist flex,
* hand knuckle line / thumb-index (coarse)  -> wrist roll + gripper.
"""

from __future__ import annotations

import abc
import logging
import math
import time
from pathlib import Path

import numpy as np

from .config import PoseConfig
from .download import fetch
from .features import ARM_CONNECTIONS, HandDetection, HandFeatures
from .hand_tracking import HandDetector  # reuse the ABC

logger = logging.getLogger(__name__)

# MediaPipe Pose landmark indices (per the person's own left/right).
_SIDES = {
    "left": dict(shoulder=11, elbow=13, wrist=15, pinky=17, index=19, thumb=21),
    "right": dict(shoulder=12, elbow=14, wrist=16, pinky=18, index=20, thumb=22),
}
_VARIANTS = {0: "lite", 1: "full", 2: "heavy"}
_MODEL_DIR = Path(__file__).parent / "models"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ensure_pose_model(complexity: int = 1) -> Path:
    variant = _VARIANTS.get(complexity, "full")
    path = _MODEL_DIR / f"pose_landmarker_{variant}.task"
    if path.exists() and path.stat().st_size > 0:
        return path
    url = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        f"pose_landmarker_{variant}/float16/1/pose_landmarker_{variant}.task"
    )
    logger.info("Downloading MediaPipe pose model (%s) ...", variant)
    fetch(url, path)
    logger.info("Pose model downloaded (%.1f MB).", path.stat().st_size / 1e6)
    return path


def compute_arm_features(
    shoulder: np.ndarray,
    elbow: np.ndarray,
    wrist: np.ndarray,
    thumb: np.ndarray,
    index: np.ndarray,
    pinky: np.ndarray,
    cfg: PoseConfig,
) -> HandFeatures:
    """Derive the six normalized features from 2D arm landmarks. Pure -> unit-testable."""
    # pan / lift: wrist position relative to the shoulder (recentred to ~0.5).
    x = _clamp(0.5 + (wrist[0] - shoulder[0]) * cfg.pan_gain, 0.0, 1.0)
    y = _clamp(0.5 + (wrist[1] - shoulder[1]) * cfg.lift_gain, 0.0, 1.0)

    # elbow extension from the interior angle at the elbow.
    v1 = shoulder - elbow
    v2 = wrist - elbow
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2)) or 1e-6
    angle = math.acos(_clamp(float(np.dot(v1, v2)) / denom, -1.0, 1.0))
    depth = _clamp((angle - cfg.elbow_bent_rad) / (cfg.elbow_straight_rad - cfg.elbow_bent_rad), 0.0, 1.0)

    # forearm pitch (up = positive).
    fore = wrist - elbow
    fore_len = float(np.linalg.norm(fore)) or 1e-6
    pitch = _clamp(-(fore[1]) / fore_len * cfg.pitch_gain, -1.0, 1.0)

    # roll from the (noisy) knuckle line index -> pinky.
    vr = pinky - index
    roll = _clamp(math.atan2(-vr[1], vr[0]) / (math.pi / 2.0), -1.0, 1.0)

    # gripper proxy from thumb-index distance normalized by forearm length.
    grip_ratio = float(np.linalg.norm(thumb - index)) / fore_len
    pinch = _clamp((grip_ratio - cfg.pinch_closed) / (cfg.pinch_open - cfg.pinch_closed), 0.0, 1.0)

    return HandFeatures(x=x, y=y, depth=depth, roll=roll, pitch=pitch, pinch=pinch)


class PoseArmDetector(HandDetector):
    """Arm landmark detection backed by the MediaPipe Tasks ``PoseLandmarker`` (VIDEO mode)."""

    def __init__(self, cfg: PoseConfig, model_path: Path | None = None):
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "mediapipe is required for arm tracking. Install it with:\n"
                "  pip install -r hand_teleop/requirements.txt"
            ) from e

        self._mp = mp
        self._cfg = cfg
        model = model_path or ensure_pose_model(cfg.complexity)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=cfg.min_detection_confidence,
            min_pose_presence_confidence=cfg.min_detection_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        self._t0 = time.perf_counter()
        self._last_ts = -1

    def _pick_side(self, lm: np.ndarray, vis: np.ndarray) -> str:
        if self._cfg.side in _SIDES:
            return self._cfg.side
        # auto: choose the arm whose shoulder/elbow/wrist are most visible
        def score(side: str) -> float:
            idx = _SIDES[side]
            return float(vis[[idx["shoulder"], idx["elbow"], idx["wrist"]]].sum())

        return "right" if score("right") >= score("left") else "left"

    def detect(self, frame_bgr: np.ndarray) -> HandDetection | None:
        h, w = frame_bgr.shape[:2]
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

        ts = int((time.perf_counter() - self._t0) * 1000)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts

        result = self._landmarker.detect_for_video(mp_image, ts)
        if not result.pose_landmarks:
            return None

        pl = result.pose_landmarks[0]
        lm = np.array([[p.x, p.y] for p in pl], dtype=np.float64)
        vis = np.array([getattr(p, "visibility", 1.0) for p in pl], dtype=np.float64)

        side = self._pick_side(lm, vis)
        idx = _SIDES[side]
        pts = {role: lm[i] for role, i in idx.items()}

        features = compute_arm_features(
            pts["shoulder"], pts["elbow"], pts["wrist"],
            pts["thumb"], pts["index"], pts["pinky"], self._cfg,
        )

        # 6-point skeleton for drawing: [shoulder, elbow, wrist, thumb, index, pinky]
        order = ["shoulder", "elbow", "wrist", "thumb", "index", "pinky"]
        skel = np.array([[pts[r][0] * w, pts[r][1] * h] for r in order], dtype=np.int32)
        return HandDetection(
            features=features,
            landmarks_px=skel,
            handedness=side.capitalize(),
            connections=ARM_CONNECTIONS,
        )

    def close(self) -> None:
        self._landmarker.close()


__all__ = ["PoseArmDetector", "compute_arm_features", "ensure_pose_model"]
