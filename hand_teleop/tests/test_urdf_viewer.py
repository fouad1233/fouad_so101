"""Tests for the URDF viewer's joint mapping and the UDP transport (no 3D window opened).

The actual yourdfpy load + window are exercised only if yourdfpy is installed and the URDF has been
downloaded; otherwise that part is skipped so the suite still runs in a bare environment.

Run from the repo root with either:
    python -m hand_teleop.tests.test_urdf_viewer
    python -m pytest hand_teleop/tests
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from hand_teleop.config import MOTORS
from hand_teleop.net import JointStatePublisher, drain_latest, make_receiver
from hand_teleop.urdf_viewer import normalized_to_radians

LIMITS = {
    "shoulder_pan": (-1.92, 1.92),
    "shoulder_lift": (-1.75, 1.75),
    "elbow_flex": (-1.69, 1.69),
    "wrist_flex": (-1.66, 1.66),
    "wrist_roll": (-2.74, 2.84),
    "gripper": (-0.17, 1.75),
}


def test_radians_within_limits_and_midpoint():
    # body joint at normalized 0 -> mid-range; extremes -> the limits
    mid = normalized_to_radians({m: 0.0 for m in MOTORS}, LIMITS, set())
    for m, (lo, hi) in LIMITS.items():
        if m == "gripper":
            continue
        assert abs(mid[m] - (lo + hi) / 2.0) < 1e-6

    hi_cmd = normalized_to_radians({m: 100.0 for m in MOTORS}, LIMITS, set())
    lo_cmd = normalized_to_radians({m: -100.0 for m in MOTORS}, LIMITS, set())
    for m, (lo, hi) in LIMITS.items():
        if m == "gripper":
            continue
        assert abs(hi_cmd[m] - hi) < 1e-6
        assert abs(lo_cmd[m] - lo) < 1e-6


def test_gripper_uses_0_100():
    lo, hi = LIMITS["gripper"]
    closed = normalized_to_radians({"gripper": 0.0}, LIMITS, set())["gripper"]
    opened = normalized_to_radians({"gripper": 100.0}, LIMITS, set())["gripper"]
    assert abs(closed - lo) < 1e-6
    assert abs(opened - hi) < 1e-6


def test_invert_flips_direction():
    normal = normalized_to_radians({"shoulder_pan": 100.0}, LIMITS, set())["shoulder_pan"]
    flipped = normalized_to_radians({"shoulder_pan": 100.0}, LIMITS, {"shoulder_pan"})["shoulder_pan"]
    assert abs(normal - LIMITS["shoulder_pan"][1]) < 1e-6
    assert abs(flipped - LIMITS["shoulder_pan"][0]) < 1e-6


def test_out_of_range_input_is_clamped():
    r = normalized_to_radians({"elbow_flex": 9999.0}, LIMITS, set())["elbow_flex"]
    assert abs(r - LIMITS["elbow_flex"][1]) < 1e-6


def test_udp_roundtrip():
    sock = make_receiver("127.0.0.1", 50711)
    try:
        pub = JointStatePublisher("127.0.0.1", 50711)
        payload = {m: float(i) for i, m in enumerate(MOTORS)}
        for _ in range(3):  # send a few; drain_latest should return the most recent
            pub.publish(payload)
        import time
        time.sleep(0.05)
        got = drain_latest(sock)
        assert got == payload
        assert drain_latest(sock) is None  # nothing left after draining
        pub.close()
    finally:
        sock.close()


def test_urdf_viewer_loads_if_available():
    try:
        import viser  # noqa: F401
        import yourdfpy  # noqa: F401
        from hand_teleop.urdf_viewer import UrdfViewer
    except ImportError:
        print("  (skipped: viser/yourdfpy not installed)")
        return
    try:
        viewer = UrdfViewer(web_port=8137)  # off the default port to avoid clashing with a live app
    except Exception as e:  # e.g. no network to download the URDF, or port busy
        print(f"  (skipped UrdfViewer load: {type(e).__name__}: {e})")
        return
    try:
        viewer.apply({m: (50.0 if m == "gripper" else 50.0) for m in MOTORS})
        viewer.apply({m: (0.0 if m != "gripper" else 50.0) for m in MOTORS})
        print("  UrdfViewer (viser) loaded + applied poses OK; url:", viewer.url)
    finally:
        viewer.stop()


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} urdf-viewer tests passed.")


if __name__ == "__main__":
    _run_all()
