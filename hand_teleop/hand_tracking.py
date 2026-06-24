"""Hand detection: webcam frame -> normalized :class:`HandFeatures`.

The :class:`HandDetector` ABC isolates the rest of the pipeline from MediaPipe so the detector can be
mocked in tests or replaced with another backend.

Uses the modern MediaPipe **Tasks** API (``HandLandmarker``), which needs a small model bundle. The
model is downloaded once and cached under ``hand_teleop/models/``.
"""

from __future__ import annotations

import abc
import logging
import math
import shutil
import ssl
import time
import urllib.request
from pathlib import Path

import numpy as np

from .config import TrackingConfig
from .features import HandDetection, HandFeatures

logger = logging.getLogger(__name__)

# MediaPipe landmark indices we care about.
WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_TIP = 12
RING_MCP = 13
PINKY_MCP = 17

PALM_POINTS = (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
_MODEL_PATH = Path(__file__).parent / "models" / "hand_landmarker.task"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ensure_model(path: Path = _MODEL_PATH, url: str = _MODEL_URL) -> Path:
    """Download and cache the HandLandmarker model bundle on first use (needs internet)."""
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading MediaPipe hand model to %s ...", path)
    # Use certifi's CA bundle if available (python.org builds otherwise lack root certs).
    try:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover
        ctx = ssl.create_default_context()

    tmp = path.with_suffix(".task.part")
    with urllib.request.urlopen(url, context=ctx, timeout=60) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(path)
    logger.info("Model downloaded (%.1f MB).", path.stat().st_size / 1e6)
    return path


class HandDetector(abc.ABC):
    """Detect a single hand and return normalized features (or ``None`` if no hand)."""

    @abc.abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> HandDetection | None: ...

    def close(self) -> None:  # optional resource cleanup
        pass

    def __enter__(self) -> "HandDetector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class MediaPipeHandDetector(HandDetector):
    """Hand landmark detection backed by the MediaPipe Tasks ``HandLandmarker`` (VIDEO mode)."""

    def __init__(self, cfg: TrackingConfig, model_path: Path | None = None):
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:  # pragma: no cover - environment dependent
            raise ImportError(
                "mediapipe is required for hand tracking. Install it with:\n"
                "  pip install -r hand_teleop/requirements.txt"
            ) from e

        self._mp = mp
        self._cfg = cfg
        model = ensure_model(model_path or _MODEL_PATH)

        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=cfg.max_num_hands,
            min_hand_detection_confidence=cfg.min_detection_confidence,
            min_hand_presence_confidence=cfg.min_detection_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        self._t0 = time.perf_counter()
        self._last_ts = -1

    def detect(self, frame_bgr: np.ndarray) -> HandDetection | None:
        h, w = frame_bgr.shape[:2]
        rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])  # BGR -> RGB, contiguous for mp.Image
        mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)

        ts = int((time.perf_counter() - self._t0) * 1000)
        if ts <= self._last_ts:  # VIDEO mode needs strictly increasing timestamps
            ts = self._last_ts + 1
        self._last_ts = ts

        result = self._landmarker.detect_for_video(mp_image, ts)
        if not result.hand_landmarks:
            return None

        hand = result.hand_landmarks[0]
        lm = np.array([[p.x, p.y, p.z] for p in hand], dtype=np.float64)  # (21, 3)

        handedness = None
        if result.handedness:
            handedness = result.handedness[0][0].category_name

        features = self._extract_features(lm)
        landmarks_px = np.column_stack([lm[:, 0] * w, lm[:, 1] * h]).astype(np.int32)
        return HandDetection(features=features, landmarks_px=landmarks_px, handedness=handedness)

    def _extract_features(self, lm: np.ndarray) -> HandFeatures:
        """Derive interpretable, bounded features from the 21 normalized landmarks."""
        xy = lm[:, :2]
        palm = xy[list(PALM_POINTS)].mean(axis=0)

        # Hand size proxy: wrist -> middle-finger knuckle distance (scale-invariant depth cue).
        spread = float(np.linalg.norm(xy[MIDDLE_MCP] - xy[WRIST]))
        spread = max(spread, 1e-6)

        d = self._cfg.depth
        depth = _clamp((spread - d.far) / (d.near - d.far), 0.0, 1.0)

        # Roll: angle of the knuckle line (index_mcp -> pinky_mcp) vs horizontal.
        v_roll = xy[PINKY_MCP] - xy[INDEX_MCP]
        roll_angle = math.atan2(-v_roll[1], v_roll[0])  # image y grows downward, so negate
        roll = _clamp(roll_angle / (math.pi / 2.0), -1.0, 1.0)

        # Pitch: vertical component of wrist -> middle_mcp, normalized by hand size.
        v_pitch = xy[MIDDLE_MCP] - xy[WRIST]
        pitch = _clamp(-v_pitch[1] / spread, -1.0, 1.0)  # hand pointing up => positive

        # Pinch: thumb tip <-> index tip distance, normalized by hand size.
        pinch_ratio = float(np.linalg.norm(xy[THUMB_TIP] - xy[INDEX_TIP])) / spread
        p = self._cfg.pinch
        pinch = _clamp((pinch_ratio - p.closed) / (p.open - p.closed), 0.0, 1.0)

        return HandFeatures(
            x=float(palm[0]),
            y=float(palm[1]),
            depth=float(depth),
            roll=float(roll),
            pitch=float(pitch),
            pinch=float(pinch),
        )

    def close(self) -> None:
        self._landmarker.close()
