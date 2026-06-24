"""Hand-tracking teleoperation for the SO-101 follower arm.

The light-weight building blocks (config, features, mapping, robot) are importable directly from the
package. The full app (``HandTeleopApp``) and ``Visualizer`` pull in OpenCV, so import them from their
own modules (``from hand_teleop.app import HandTeleopApp``) to keep ``import hand_teleop`` free of any
GUI dependency.
"""

from __future__ import annotations

from .config import AppConfig, MOTORS, home_pose
from .features import HandFeatures
from .mapping import HandToJointMapper, TargetSmoother
from .robot import RobotInterface, SimulatedRobot, make_robot

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "MOTORS",
    "home_pose",
    "HandFeatures",
    "HandToJointMapper",
    "TargetSmoother",
    "RobotInterface",
    "SimulatedRobot",
    "make_robot",
]
