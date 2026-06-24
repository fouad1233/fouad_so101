"""Tests for the mapping + smoothing + simulated-robot logic (no camera/GUI required).

Run from the repo root with either:
    python -m hand_teleop.tests.test_mapping
    python -m pytest hand_teleop/tests
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from hand_teleop.config import MOTORS, AppConfig
from hand_teleop.features import HandFeatures
from hand_teleop.mapping import HandToJointMapper, TargetSmoother
from hand_teleop.robot import SimulatedRobot

CFG = AppConfig()


def _features(**kw) -> HandFeatures:
    base = dict(x=0.5, y=0.5, depth=0.5, roll=0.0, pitch=0.0, pinch=0.5)
    base.update(kw)
    return HandFeatures(**base)


def test_outputs_within_safe_range():
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    s = CFG.safety
    # sweep every feature across its extremes
    extremes = [
        _features(x=v, y=v, depth=v, pinch=v, roll=r, pitch=r)
        for v in (0.0, 0.5, 1.0)
        for r in (-1.0, 0.0, 1.0)
    ]
    for f in extremes:
        t = mapper.map(f)
        assert set(t) == set(MOTORS)
        for m in MOTORS:
            if m == "gripper":
                assert s.gripper_min <= t[m] <= s.gripper_max, (m, t[m])
            else:
                assert s.clamp_min <= t[m] <= s.clamp_max, (m, t[m])


def test_pan_is_monotonic_in_x():
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    left = mapper.map(_features(x=0.0))["shoulder_pan"]
    mid = mapper.map(_features(x=0.5))["shoulder_pan"]
    right = mapper.map(_features(x=1.0))["shoulder_pan"]
    assert left < mid < right


def test_lift_inverted_hand_up_is_positive():
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    # y is 0 at top of frame; hand up should raise the arm (positive lift)
    up = mapper.map(_features(y=0.0))["shoulder_lift"]
    down = mapper.map(_features(y=1.0))["shoulder_lift"]
    assert up > down


def test_gripper_opens_with_pinch():
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    closed = mapper.map(_features(pinch=0.0))["gripper"]
    opened = mapper.map(_features(pinch=1.0))["gripper"]
    assert opened > closed


def test_smoother_respects_max_step():
    init = {m: 0.0 for m in MOTORS}
    smoother = TargetSmoother(CFG.smoothing, init)
    target = {m: 100.0 for m in MOTORS}
    prev = dict(init)
    for _ in range(5):
        state = smoother.update(target)
        for m in MOTORS:
            assert abs(state[m] - prev[m]) <= CFG.smoothing.max_step + 1e-6
        prev = state


def test_smoother_converges_toward_target():
    init = {m: 0.0 for m in MOTORS}
    smoother = TargetSmoother(CFG.smoothing, init)
    target = {m: 40.0 for m in MOTORS}
    for _ in range(200):
        state = smoother.update(target)
    for m in MOTORS:
        assert abs(state[m] - 40.0) < 1.0


def test_simulated_robot_caps_relative_motion():
    robot = SimulatedRobot(max_relative_target=10.0)
    robot.connect()
    start = robot.read_positions()
    sent = robot.send_targets({m: 100.0 for m in MOTORS})
    for m in MOTORS:
        assert abs(sent[m] - start[m]) <= 10.0 + 1e-6
    robot.disconnect()


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} mapping tests passed.")


if __name__ == "__main__":
    _run_all()
