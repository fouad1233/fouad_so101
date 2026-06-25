"""3D URDF viewer for the SO-101, served in the browser via ``viser``.

Loads the official SO-101 URDF (TheRobotStudio/SO-ARM100) and updates its joints from the teleop app.
It is **browser-based** (WebGL) rather than a native OpenGL window, which is far more reliable on
macOS than the trimesh/pyglet viewer. ``viser`` serves on a background thread, so the viewer runs
**in-process** with the OpenCV camera window without any event-loop conflict.

The teleop app drives it directly. You can also run it standalone (it just shows the model, and will
follow joint states if something streams them over UDP):

    python -m hand_teleop.urdf_viewer

Joint mapping: the app speaks LeRobot's normalized space (body joints in [-100, 100], gripper in
[0, 100]); those are mapped linearly onto each URDF joint's [lower, upper] limit so the model follows
the real joints. Registration to the arm's exact zero is approximate; flip a joint with ``--invert``
if it rotates the wrong way.
"""

from __future__ import annotations

import argparse
import logging
import time

import numpy as np

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
    """Owns the URDF model + a viser web server; translates joint states into the rendered pose."""

    def __init__(self, web_host: str = "127.0.0.1", web_port: int = 8080, invert: set[str] | None = None):
        import viser
        import yourdfpy
        from viser.extras import ViserUrdf

        self._urdf = yourdfpy.URDF.load(str(ensure_urdf()))
        self._order = [j.name for j in self._urdf.actuated_joints]
        self._limits: dict[str, tuple[float, float]] = {
            j.name: (float(j.limit.lower), float(j.limit.upper))
            for j in self._urdf.actuated_joints
            if j.limit is not None
        }
        self._invert = invert or set()
        self._server = viser.ViserServer(host=web_host, port=web_port)
        self._viser_urdf = ViserUrdf(self._server, self._urdf)
        self.apply({m: (50.0 if m == "gripper" else 0.0) for m in MOTORS})

    @property
    def url(self) -> str:
        return f"http://localhost:{self._server.get_port()}"

    def apply(self, positions: dict[str, float]) -> None:
        rad = normalized_to_radians(positions, self._limits, self._invert)
        cfg = np.array([rad.get(name, 0.0) for name in self._order], dtype=float)
        self._viser_urdf.update_cfg(cfg)

    def stop(self) -> None:
        try:
            self._server.stop()
        except Exception:  # pragma: no cover - best effort
            pass


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="hand_teleop.urdf_viewer", description="3D SO-101 URDF viewer (browser).")
    p.add_argument("--web-host", default="127.0.0.1")
    p.add_argument("--web-port", type=int, default=8080)
    p.add_argument("--udp-host", default="127.0.0.1", help="address to receive joint states on")
    p.add_argument("--udp-port", type=int, default=50607)
    p.add_argument("--invert", default="",
                   help="comma-separated joint names to flip if they rotate the wrong way.")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    invert = {s.strip() for s in args.invert.split(",") if s.strip()}
    viewer = UrdfViewer(args.web_host, args.web_port, invert)
    print(f"\n>>> Open {viewer.url} in your browser to see the SO-101.\n")

    sock = make_receiver(args.udp_host, args.udp_port)
    logger.info("Listening for joint states on udp://%s:%d (Ctrl-C to quit).", args.udp_host, args.udp_port)
    try:
        while True:
            latest = drain_latest(sock)
            if latest:
                viewer.apply(latest)
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        viewer.stop()


if __name__ == "__main__":
    main()
