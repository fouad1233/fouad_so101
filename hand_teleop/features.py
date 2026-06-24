"""Hand feature representation shared between the detector and the mapper.

Keeping this as a plain dataclass (independent of MediaPipe) lets the mapper be unit-tested with
synthetic inputs and keeps the detector swappable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Canonical MediaPipe hand topology (21 landmarks) used for drawing the skeleton.
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (5, 9), (9, 10), (10, 11), (11, 12),       # middle
    (9, 13), (13, 14), (14, 15), (15, 16),     # ring
    (13, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (0, 17),                                   # palm base
)

# Topology for the arm skeleton drawn in "arm" mode, over a 6-point array:
# [shoulder, elbow, wrist, thumb, index, pinky].
ARM_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),  # upper arm: shoulder -> elbow
    (1, 2),  # forearm: elbow -> wrist
    (2, 3),  # wrist -> thumb
    (2, 4),  # wrist -> index
    (4, 5),  # index -> pinky (knuckle line)
)


@dataclass
class HandFeatures:
    """Normalized, interpretable hand features that drive the joints.

    All fields are bounded; see ``config.FEATURE_DOMAINS`` for the exact domains.
    """

    x: float       # palm horizontal position in frame, [0, 1]
    y: float       # palm vertical position in frame, [0, 1]
    depth: float   # near/far proxy, [0, 1] (1 = close to camera)
    roll: float    # wrist roll, [-1, 1]
    pitch: float   # pointing up/down, [-1, 1]
    pinch: float   # fingers open amount, [0, 1] (1 = open)


@dataclass
class HandDetection:
    """Result of running a detector on one frame (hand or arm)."""

    features: HandFeatures
    landmarks_px: np.ndarray              # (N, 2) pixel coordinates for drawing
    handedness: str | None = None        # "Left" / "Right" / None
    connections: tuple[tuple[int, int], ...] = HAND_CONNECTIONS  # topology for drawing
