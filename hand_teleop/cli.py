"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging

from .app import HandTeleopApp
from .config import AppConfig
from .mapping import HandToJointMapper
from .robot import make_robot
from .visualizer import Visualizer


def build_config(args: argparse.Namespace) -> AppConfig:
    cfg = AppConfig()
    cfg.camera_index = args.camera
    cfg.show_window = not args.no_window
    cfg.show_schematic = not args.no_schematic
    cfg.mirror = not args.no_mirror
    cfg.robot.port = args.port
    cfg.robot.id = args.id
    cfg.robot.max_relative_target = args.max_relative_target
    cfg.urdf_view.enabled = args.urdf_view
    cfg.track = args.track
    cfg.pose.side = args.arm_side
    # Flip the command direction of any listed joints (e.g. elbow_flex by default).
    for name in (j.strip() for j in args.invert_joints.split(",")):
        if name in cfg.mapping.joint_maps:
            jm = cfg.mapping.joint_maps[name]
            jm.invert = not jm.invert
    if args.ema_alpha is not None:
        cfg.smoothing.ema_alpha = args.ema_alpha
    if args.max_step is not None:
        cfg.smoothing.max_step = args.max_step
    return cfg


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="hand_teleop",
        description="Control an SO-101 follower arm by tracking your hand with a webcam.",
    )
    p.add_argument("--port", default=None,
                   help="Serial port of the SO-101 follower (e.g. /dev/tty.usbmodem...). "
                        "If omitted, runs in SIMULATION mode (no hardware).")
    p.add_argument("--id", default="my_follower",
                   help="Calibration id used with `lerobot-calibrate` (default: my_follower).")
    p.add_argument("--track", choices=["hand", "arm"], default="hand",
                   help="Track your hand (MediaPipe Hands) or your whole arm (MediaPipe Pose).")
    p.add_argument("--arm-side", choices=["auto", "left", "right"], default="auto",
                   help="Which arm to follow in --track arm mode (default: auto).")
    p.add_argument("--invert-joints", default="elbow_flex",
                   help="Comma-separated joints whose direction to flip (default: elbow_flex). "
                        "Pass '' for none, or e.g. 'elbow_flex,shoulder_pan'.")
    p.add_argument("--camera", type=int, default=0, help="Webcam index (default: 0).")
    p.add_argument("--max-relative-target", type=float, default=12.0,
                   help="Max per-command joint change, normalized units (safety cap; default: 12).")
    p.add_argument("--ema-alpha", type=float, default=None,
                   help="Smoothing responsiveness 0..1 (higher = snappier; default: 0.35).")
    p.add_argument("--max-step", type=float, default=None,
                   help="Max target change per control tick (default: 6).")
    p.add_argument("--urdf-view", action="store_true",
                   help="Open a real 3D SO-101 URDF viewer (separate window) that follows the joints.")
    p.add_argument("--no-window", action="store_true", help="Run without the OpenCV window.")
    p.add_argument("--no-schematic", action="store_true", help="Hide the arm schematic overlay.")
    p.add_argument("--no-mirror", action="store_true", help="Do not mirror the camera image.")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cfg = build_config(args)
    robot = make_robot(cfg.robot)
    if cfg.track == "arm":
        # Arm joints from Pose + reliable gripper/roll from Hands.
        from .pose_tracking import CombinedArmHandDetector

        detector = CombinedArmHandDetector(cfg.pose, cfg.tracking)
    else:
        from .hand_tracking import MediaPipeHandDetector

        detector = MediaPipeHandDetector(cfg.tracking)
    mapper = HandToJointMapper(cfg.mapping, cfg.safety)
    visualizer = Visualizer(cfg.safety, show_schematic=cfg.show_schematic) if cfg.show_window else None

    mode = "SIMULATION" if cfg.robot.port is None else f"ROBOT on {cfg.robot.port}"
    logging.info("Starting teleop (%s tracking) in %s mode.", cfg.track, mode)
    HandTeleopApp(cfg, robot, detector, mapper, visualizer).run()


if __name__ == "__main__":
    main()
