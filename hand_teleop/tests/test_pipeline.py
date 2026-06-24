"""Headless end-to-end smoke test: mock hand -> mapper -> smoother -> simulated robot.

Verifies the whole control data flow (minus camera/MediaPipe/OpenCV) produces safe, tracking motion.

Run from the repo root with either:
    python -m hand_teleop.tests.test_pipeline
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


def test_pipeline_tracks_and_stays_safe():
    robot = SimulatedRobot(max_relative_target=CFG.robot.max_relative_target)
    robot.connect()
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    smoother = TargetSmoother(CFG.smoothing, robot.read_positions())
    s = CFG.safety

    # Simulate the hand sweeping left -> right and opening the fingers over 120 frames.
    positions_history = []
    for i in range(120):
        frac = i / 119.0
        feats = HandFeatures(x=frac, y=0.3, depth=0.6, roll=0.0, pitch=0.2, pinch=frac)
        targets = smoother.update(mapper.map(feats))
        positions = robot.send_targets(targets)
        positions_history.append(positions)

        # safety invariant must hold on every single command
        for m in MOTORS:
            lo, hi = (0.0, 100.0) if m == "gripper" else (s.clamp_min, s.clamp_max)
            assert lo - 1e-6 <= positions[m] <= hi + 1e-6, (m, positions[m])

    first, last = positions_history[0], positions_history[-1]
    # base pan should have followed the hand to the right; gripper should have opened
    assert last["shoulder_pan"] > first["shoulder_pan"] + 10
    assert last["gripper"] > first["gripper"] + 10
    robot.disconnect()


def test_no_jump_at_startup():
    # If the arm starts at a non-zero pose, the first command must not jump more than the cap.
    robot = SimulatedRobot(max_relative_target=CFG.robot.max_relative_target)
    robot._pos = {m: (20.0 if m != "gripper" else 50.0) for m in MOTORS}  # pretend current pose
    robot.connect()
    mapper = HandToJointMapper(CFG.mapping, CFG.safety)
    smoother = TargetSmoother(CFG.smoothing, robot.read_positions())

    start = robot.read_positions()
    feats = HandFeatures(x=1.0, y=0.0, depth=1.0, roll=1.0, pitch=1.0, pinch=1.0)  # extreme target
    positions = robot.send_targets(smoother.update(mapper.map(feats)))
    for m in MOTORS:
        assert abs(positions[m] - start[m]) <= CFG.robot.max_relative_target + 1e-6
    robot.disconnect()


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} pipeline tests passed.")


if __name__ == "__main__":
    _run_all()
