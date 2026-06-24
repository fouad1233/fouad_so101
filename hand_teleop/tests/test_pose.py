"""Tests for the arm (pose) feature extraction. Pure math -> no camera/model needed.

Run from the repo root with either:
    python -m hand_teleop.tests.test_pose
    python -m pytest hand_teleop/tests
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from hand_teleop.config import PoseConfig
from hand_teleop.pose_tracking import compute_arm_features

CFG = PoseConfig()


def _pt(x, y):
    return np.array([x, y], dtype=np.float64)


def test_straight_arm_gives_high_elbow_extension():
    # shoulder, elbow, wrist colinear (straight arm) -> depth ~ 1
    sh, el, wr = _pt(0.5, 0.3), _pt(0.5, 0.5), _pt(0.5, 0.7)
    f = compute_arm_features(sh, el, wr, _pt(0.52, 0.72), _pt(0.5, 0.74), _pt(0.48, 0.72), CFG)
    assert f.depth > 0.9


def test_bent_arm_gives_low_elbow_extension():
    # 90-degree bend at the elbow -> low depth
    sh, el, wr = _pt(0.5, 0.5), _pt(0.7, 0.5), _pt(0.7, 0.3)
    f = compute_arm_features(sh, el, wr, _pt(0.72, 0.28), _pt(0.7, 0.26), _pt(0.68, 0.28), CFG)
    assert f.depth < 0.5


def test_wrist_right_of_shoulder_increases_x():
    sh = _pt(0.5, 0.5)
    left = compute_arm_features(sh, _pt(0.45, 0.5), _pt(0.40, 0.5), _pt(0.40, 0.5), _pt(0.40, 0.5), _pt(0.40, 0.5), CFG)
    right = compute_arm_features(sh, _pt(0.55, 0.5), _pt(0.60, 0.5), _pt(0.60, 0.5), _pt(0.60, 0.5), _pt(0.60, 0.5), CFG)
    assert right.x > left.x


def test_wrist_above_shoulder_decreases_y():
    sh = _pt(0.5, 0.5)
    up = compute_arm_features(sh, _pt(0.5, 0.4), _pt(0.5, 0.3), _pt(0.5, 0.3), _pt(0.5, 0.3), _pt(0.5, 0.3), CFG)
    down = compute_arm_features(sh, _pt(0.5, 0.6), _pt(0.5, 0.7), _pt(0.5, 0.7), _pt(0.5, 0.7), _pt(0.5, 0.7), CFG)
    assert up.y < down.y  # smaller y = higher in frame


def test_all_features_bounded():
    sh, el, wr = _pt(0.2, 0.2), _pt(0.9, 0.9), _pt(0.1, 0.95)
    f = compute_arm_features(sh, el, wr, _pt(0.0, 1.0), _pt(1.0, 0.0), _pt(0.3, 0.6), CFG)
    assert 0.0 <= f.x <= 1.0 and 0.0 <= f.y <= 1.0
    assert 0.0 <= f.depth <= 1.0 and 0.0 <= f.pinch <= 1.0
    assert -1.0 <= f.roll <= 1.0 and -1.0 <= f.pitch <= 1.0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} pose tests passed.")


if __name__ == "__main__":
    _run_all()
