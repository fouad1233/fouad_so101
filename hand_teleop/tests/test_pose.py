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
    sh, el, wr = _pt(0.5, 0.3), _pt(0.5, 0.5), _pt(0.5, 0.7)  # colinear -> straight
    f = compute_arm_features(sh, el, wr, CFG)
    assert f.depth > 0.9


def test_bent_arm_gives_low_elbow_extension():
    sh, el, wr = _pt(0.5, 0.5), _pt(0.7, 0.5), _pt(0.7, 0.3)  # 90-degree bend
    f = compute_arm_features(sh, el, wr, CFG)
    assert f.depth < 0.5


def test_pan_follows_upper_arm_left_right():
    sh = _pt(0.5, 0.5)
    left = compute_arm_features(sh, _pt(0.3, 0.5), _pt(0.2, 0.5), CFG)   # upper arm to the left
    right = compute_arm_features(sh, _pt(0.7, 0.5), _pt(0.8, 0.5), CFG)  # upper arm to the right
    assert right.x > left.x


def test_lift_follows_upper_arm_up_down():
    sh = _pt(0.5, 0.5)
    up = compute_arm_features(sh, _pt(0.5, 0.3), _pt(0.5, 0.1), CFG)    # elbow above shoulder
    down = compute_arm_features(sh, _pt(0.5, 0.7), _pt(0.5, 0.9), CFG)  # elbow below shoulder
    assert up.y < down.y  # smaller y = higher in frame (mapper inverts -> higher lift)


def test_pan_lift_decoupled_from_elbow_bend():
    """The whole point: bending the elbow must NOT move pan/lift (true serial DOF)."""
    sh, el = _pt(0.5, 0.5), _pt(0.75, 0.45)  # fixed upper arm
    straight = compute_arm_features(sh, el, _pt(1.0, 0.40), CFG)   # forearm extended
    bent = compute_arm_features(sh, el, _pt(0.75, 0.20), CFG)      # forearm bent up
    assert abs(straight.x - bent.x) < 1e-9
    assert abs(straight.y - bent.y) < 1e-9
    assert straight.depth != bent.depth  # elbow flex DID change


def test_elbow_uses_3d_world_when_provided():
    # In 2D the arm looks straight (colinear), but in 3D it is bent toward the camera (z).
    sh2, el2, wr2 = _pt(0.5, 0.3), _pt(0.5, 0.5), _pt(0.5, 0.7)
    flat = compute_arm_features(sh2, el2, wr2, CFG)
    world = (
        np.array([0.0, -0.2, 0.0]),   # shoulder
        np.array([0.0, 0.0, 0.0]),    # elbow
        np.array([0.0, -0.2, 0.2]),   # wrist bent forward (out of the image plane)
    )
    bent3d = compute_arm_features(sh2, el2, wr2, CFG, world=world)
    assert flat.depth > 0.9          # looked straight in 2D
    assert bent3d.depth < flat.depth  # 3D reveals the bend


def test_all_features_bounded():
    sh, el, wr = _pt(0.2, 0.2), _pt(0.9, 0.9), _pt(0.1, 0.95)
    f = compute_arm_features(sh, el, wr, CFG)
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
