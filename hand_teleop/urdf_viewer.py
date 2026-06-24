"""Standalone 3D URDF viewer for the SO-101.

Loads the official SO-101 URDF (TheRobotStudio/SO-ARM100) with ``yourdfpy`` and animates it from
normalized joint states received over UDP from the teleop app. Run on its own:

    python -m hand_teleop.urdf_viewer

or let ``python -m hand_teleop --urdf-view`` launch it for you.

Joint mapping: the teleop app speaks LeRobot's normalized space (body joints in [-100, 100], gripper
in [0, 100]); here those are mapped linearly onto each URDF joint's [lower, upper] limit so the model
follows the real joints. (Registration to the arm's exact zero is approximate; flip a joint with
``--invert`` if it rotates the wrong way.)
"""

from __future__ import annotations

import argparse
import logging

from .config import MOTORS
from .net import drain_latest, make_receiver
from .urdf_assets import ensure_urdf

logger = logging.getLogger(__name__)


def normalized_to_radians(
    positions: dict[str, float],
    limits: dict[str, tuple[float, float]],
    invert: set[str],
) -> dict[str, float]:
    """Map normalized joint values to URDF joint angles (radians)."""
    out: dict[str, float] = {}
    for motor, (lo, hi) in limits.items():
        v = positions.get(motor)
        if v is None:
            continue
        if motor == "gripper":
            t = v / 100.0                  # gripper is [0, 100]
        else:
            t = (v + 100.0) / 200.0        # body joints are [-100, 100], 0 -> mid-range
        t = max(0.0, min(1.0, t))
        if motor in invert:
            t = 1.0 - t
        out[motor] = lo + t * (hi - lo)
    return out


class UrdfViewer:
    """Owns the URDF model and translates incoming joint states into the rendered pose."""

    def __init__(self, invert: set[str] | None = None):
        import yourdfpy

        self._robot = yourdfpy.URDF.load(str(ensure_urdf()))
        self._invert = invert or set()
        self._limits: dict[str, tuple[float, float]] = {}
        for j in self._robot.actuated_joints:
            if j.name in MOTORS and j.limit is not None:
                self._limits[j.name] = (float(j.limit.lower), float(j.limit.upper))
        # start at a neutral pose
        self.apply({m: (50.0 if m == "gripper" else 0.0) for m in MOTORS})

    def apply(self, positions: dict[str, float]) -> None:
        self._robot.update_cfg(normalized_to_radians(positions, self._limits, self._invert))

    def run(self, host: str, port: int) -> None:
        sock = make_receiver(host, port)
        logger.info("URDF viewer listening on %s:%d. Close the window to quit.", host, port)

        def _callback(scene):  # called by the trimesh/pyglet viewer each frame
            latest = drain_latest(sock)
            if latest:
                self.apply(latest)

        try:
            self._robot.show(callback=_callback)
        finally:
            sock.close()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="hand_teleop.urdf_viewer", description="3D SO-101 URDF viewer.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=50607)
    p.add_argument("--invert", default="",
                   help="comma-separated joint names to flip if they rotate the wrong way.")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    invert = {s.strip() for s in args.invert.split(",") if s.strip()}
    UrdfViewer(invert=invert).run(args.host, args.port)


if __name__ == "__main__":
    main()
