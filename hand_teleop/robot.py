"""Robot back-ends behind a single interface: the real SO-101 or an in-software simulation."""

from __future__ import annotations

import abc
import logging

from .config import MOTORS, RobotConfig, home_pose

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class RobotInterface(abc.ABC):
    """Minimal control surface the app needs from any robot back-end."""

    motors: tuple[str, ...] = MOTORS

    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def read_positions(self) -> dict[str, float]:
        """Current joint positions in normalized space ([-100,100]; gripper [0,100])."""

    @abc.abstractmethod
    def send_targets(self, targets: dict[str, float]) -> dict[str, float]:
        """Command targets; return what was actually applied (possibly clipped)."""

    @abc.abstractmethod
    def disconnect(self) -> None: ...

    @property
    def is_simulation(self) -> bool:
        return False


class SimulatedRobot(RobotInterface):
    """Software stand-in: integrates targets with the same per-command cap as the real driver.

    Lets the full pipeline (camera -> detection -> mapping -> visualization) run and be tested with
    no hardware attached.
    """

    def __init__(self, max_relative_target: float = 12.0):
        self._max_rel = max_relative_target
        self._pos: dict[str, float] = home_pose()

    def connect(self) -> None:
        logger.info("SimulatedRobot connected (no hardware).")

    def read_positions(self) -> dict[str, float]:
        return dict(self._pos)

    def send_targets(self, targets: dict[str, float]) -> dict[str, float]:
        for m in MOTORS:
            if m not in targets:
                continue
            delta = _clamp(targets[m] - self._pos[m], -self._max_rel, self._max_rel)
            self._pos[m] += delta
        return dict(self._pos)

    def disconnect(self) -> None:
        logger.info("SimulatedRobot disconnected.")

    @property
    def is_simulation(self) -> bool:
        return True


class SO101RobotController(RobotInterface):
    """Adapter around LeRobot's ``SO101Follower``.

    Uses normalized joint space (``use_degrees=False``) and a ``max_relative_target`` cap, which the
    LeRobot driver enforces on every command as the final hardware safety layer.
    """

    def __init__(self, cfg: RobotConfig):
        if not cfg.port:
            raise ValueError("A serial port is required for the real SO-101 (got None).")
        # Imported lazily so simulation mode never needs the hardware stack.
        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

        self._cfg = cfg
        robot_cfg = SO101FollowerConfig(
            port=cfg.port,
            id=cfg.id,
            use_degrees=cfg.use_degrees,
            max_relative_target=cfg.max_relative_target,
            disable_torque_on_disconnect=cfg.disable_torque_on_disconnect,
        )
        self._robot = SO101Follower(robot_cfg)

    def connect(self) -> None:
        # calibrate=False: the arm is assumed already calibrated, so we avoid interactive prompts.
        self._robot.connect(calibrate=False)
        if not self._robot.is_calibrated:
            logger.warning(
                "SO-101 reports it is NOT calibrated. Run `lerobot-calibrate "
                "--robot.type=so101_follower --robot.port=%s --robot.id=%s` first.",
                self._cfg.port,
                self._cfg.id,
            )
        logger.info("SO101Follower connected on %s (id=%s).", self._cfg.port, self._cfg.id)

    def read_positions(self) -> dict[str, float]:
        obs = self._robot.get_observation()
        return {m: float(obs[f"{m}.pos"]) for m in MOTORS}

    def send_targets(self, targets: dict[str, float]) -> dict[str, float]:
        action = {f"{m}.pos": float(v) for m, v in targets.items()}
        sent = self._robot.send_action(action)
        return {m: float(sent[f"{m}.pos"]) for m in MOTORS if f"{m}.pos" in sent}

    def disconnect(self) -> None:
        try:
            self._robot.disconnect()
        except Exception as e:  # never raise during shutdown
            logger.warning("Error during disconnect: %s", e)


def make_robot(cfg: RobotConfig) -> RobotInterface:
    """Pick the back-end: real SO-101 if a port is configured, else simulation.

    In simulation there's no hardware to protect, so the sim tracks the (already smoothed) targets
    directly for a responsive preview. The real driver keeps its ``max_relative_target`` safety cap.
    """
    if cfg.port:
        return SO101RobotController(cfg)
    return SimulatedRobot(max_relative_target=1e9)
