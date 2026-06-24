"""Configuration dataclasses for the hand-teleop pipeline.

Everything tunable lives here so the rest of the code stays free of magic numbers.
Joint targets are expressed in LeRobot's *normalized* space (``use_degrees=False``):

* the five body joints are in ``[-100, 100]`` (mapped from the calibrated range of motion), and
* the gripper is in ``[0, 100]``.

Because ``[-100, 100]`` already corresponds to the arm's recorded range of motion, keeping targets
inside a conservative sub-range (the defaults below) is inherently safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Joint order matches the SO-101 motor bus (ids 1..6).
MOTORS: tuple[str, ...] = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)

# Domain of each hand feature produced by the detector. Used by the mapper to normalize to [0, 1].
FEATURE_DOMAINS: dict[str, tuple[float, float]] = {
    "x": (0.0, 1.0),       # palm horizontal position in the frame (0 = left, 1 = right)
    "y": (0.0, 1.0),       # palm vertical position (0 = top, 1 = bottom)
    "depth": (0.0, 1.0),   # size proxy (0 = far/small, 1 = near/large)
    "roll": (-1.0, 1.0),   # hand roll about the forearm axis
    "pitch": (-1.0, 1.0),  # hand pointing up/down
    "pinch": (0.0, 1.0),   # thumb-index separation (0 = closed, 1 = open)
}


@dataclass
class JointMap:
    """Linear map from one hand feature to one joint's safe output sub-range.

    ``in_lo``/``in_hi`` define the *active* part of the feature's domain that spans the full output
    range. Narrowing it (e.g. y over [0.2, 0.85] instead of [0, 1]) means you reach the joint's limits
    with comfortable hand motion, without having to push to the very edge of the frame. If left as
    ``None`` the full feature domain (``FEATURE_DOMAINS``) is used.
    """

    feature: str
    out_min: float
    out_max: float
    invert: bool = False
    in_lo: float | None = None
    in_hi: float | None = None


@dataclass
class MappingConfig:
    """Which feature drives which joint, and the safe output range per joint.

    Defaults are intentionally conservative (well inside ``[-100, 100]``). Flip ``invert`` or swap
    ``out_min``/``out_max`` if a joint moves the "wrong" way for your arm's calibration direction.
    """

    joint_maps: dict[str, JointMap] = field(
        default_factory=lambda: {
            # hand moves left/right  -> base pan
            "shoulder_pan": JointMap("x", -90.0, 90.0, invert=False, in_lo=0.15, in_hi=0.85),
            # hand moves up/down     -> shoulder lift (invert: hand up => arm up)
            "shoulder_lift": JointMap("y", -60.0, 60.0, invert=True, in_lo=0.20, in_hi=0.85),
            # hand near/far          -> elbow reach
            "elbow_flex": JointMap("depth", -75.0, 75.0, invert=False, in_lo=0.10, in_hi=0.90),
            # hand points up/down    -> wrist flex
            "wrist_flex": JointMap("pitch", -75.0, 75.0, invert=False, in_lo=-0.80, in_hi=0.80),
            # hand roll              -> wrist roll
            "wrist_roll": JointMap("roll", -90.0, 90.0, invert=False, in_lo=-0.90, in_hi=0.90),
            # fingers open/close     -> gripper
            "gripper": JointMap("pinch", 3.0, 97.0, invert=False, in_lo=0.05, in_hi=0.95),
        }
    )


@dataclass
class SmoothingConfig:
    """Exponential smoothing + per-tick rate limit applied to joint targets."""

    ema_alpha: float = 0.35   # 0..1; higher = more responsive, lower = smoother
    max_step: float = 6.0     # max change per control tick, in normalized units


@dataclass
class SafetyConfig:
    """Hard clamps applied after mapping (defense layer 1)."""

    clamp_min: float = -95.0  # body joints never exceed this normalized magnitude
    clamp_max: float = 95.0
    gripper_min: float = 3.0
    gripper_max: float = 97.0


@dataclass
class DepthCalibration:
    """Maps the raw hand-size proxy to a [0, 1] depth feature.

    ``near`` is the spread (wrist-to-knuckles distance, in normalized image units) when the hand is
    close to the camera; ``far`` is the spread when it is far. Tune to your camera/distance.
    """

    near: float = 0.45
    far: float = 0.12


@dataclass
class PinchCalibration:
    """Maps the raw thumb-index distance (normalized by hand size) to a [0, 1] open feature."""

    closed: float = 0.18  # ratio at which the gripper is considered fully closed
    open: float = 1.05    # ratio at which it is considered fully open


@dataclass
class TrackingConfig:
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.6
    max_num_hands: int = 1
    depth: DepthCalibration = field(default_factory=DepthCalibration)
    pinch: PinchCalibration = field(default_factory=PinchCalibration)


@dataclass
class RobotConfig:
    """Settings for the real SO-101 follower (ignored in simulation mode)."""

    port: str | None = None              # e.g. /dev/tty.usbmodem5B421352311; None => simulation
    id: str = "my_follower"              # calibration id used during `lerobot-calibrate`
    use_degrees: bool = False            # False => normalized [-100,100] space (recommended here)
    max_relative_target: float = 12.0    # hardware per-command cap (defense layer 3)
    disable_torque_on_disconnect: bool = True


@dataclass
class UrdfViewConfig:
    """Optional 3D URDF viewer (separate process, fed joint states over local UDP)."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 50607
    # If a joint appears to move the opposite way in the 3D view, add its name here.
    invert_joints: tuple[str, ...] = ()


@dataclass
class AppConfig:
    camera_index: int = 0
    frame_width: int = 1280
    frame_height: int = 720
    mirror: bool = True          # selfie view (feels natural)
    show_window: bool = True
    show_schematic: bool = True
    control_hz: float = 30.0     # upper bound on control loop rate

    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    smoothing: SmoothingConfig = field(default_factory=SmoothingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    robot: RobotConfig = field(default_factory=RobotConfig)
    urdf_view: UrdfViewConfig = field(default_factory=UrdfViewConfig)


def home_pose() -> dict[str, float]:
    """A neutral, safe target: all body joints centered, gripper half-open."""
    return {m: (50.0 if m == "gripper" else 0.0) for m in MOTORS}
