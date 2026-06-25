"""Tests for the schematic forward kinematics (pure math, no GUI).

Run from the repo root with either:
    python -m hand_teleop.tests.test_kinematics
    python -m pytest hand_teleop/tests
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from hand_teleop.config import MOTORS
from hand_teleop.kinematics import ArmSchematic


def _targets(**kw):
    base = {m: 0.0 for m in MOTORS}
    base["gripper"] = 50.0
    base.update(kw)
    return base


def test_points_are_finite_and_bounded_over_full_range():
    arm = ArmSchematic()
    reach = sum(arm.lengths)
    for lift in (-100, 0, 100):
        for elbow in (-100, 0, 100):
            for wflex in (-100, 0, 100):
                pts = arm.side_view_points(
                    _targets(shoulder_lift=lift, elbow_flex=elbow, wrist_flex=wflex)
                )
                assert len(pts) == 4
                for x, y in pts:
                    assert math.isfinite(x) and math.isfinite(y)
                    assert abs(x) <= reach + 1e-6 and abs(y) <= reach + 1e-6


def test_base_is_origin():
    arm = ArmSchematic()
    pts = arm.side_view_points(_targets())
    assert pts[0] == (0.0, 0.0)


def test_neutral_arm_points_up():
    arm = ArmSchematic()
    pts = arm.side_view_points(_targets())
    # with all-zero joints the arm should extend straight up (+y), x ~ 0
    tip_x, tip_y = pts[-1]
    assert abs(tip_x) < 1e-6
    assert tip_y > 0


def test_gripper_opening_clamped():
    arm = ArmSchematic()
    assert arm.gripper_opening(_targets(gripper=0)) == 0.0
    assert arm.gripper_opening(_targets(gripper=100)) == 1.0
    assert 0.0 <= arm.gripper_opening(_targets(gripper=50)) <= 1.0


def test_pan_dial_sign():
    arm = ArmSchematic()
    assert arm.pan_angle_deg(_targets(shoulder_pan=100)) > 0
    assert arm.pan_angle_deg(_targets(shoulder_pan=-100)) < 0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} kinematics tests passed.")


if __name__ == "__main__":
    _run_all()
