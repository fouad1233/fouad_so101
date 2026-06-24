"""The control loop wiring everything together."""

from __future__ import annotations

import logging
import time

from .config import AppConfig, home_pose
from .hand_tracking import HandDetector
from .mapping import HandToJointMapper, TargetSmoother
from .robot import RobotInterface
from .visualizer import Visualizer

logger = logging.getLogger(__name__)


class HandTeleopApp:
    """Capture -> detect -> map -> smooth -> send, with live visualization and safe shutdown.

    Collaborators are injected so the loop has no hidden dependencies and stays testable.
    """

    def __init__(
        self,
        cfg: AppConfig,
        robot: RobotInterface,
        detector: HandDetector,
        mapper: HandToJointMapper,
        visualizer: Visualizer | None = None,
    ):
        self._cfg = cfg
        self._robot = robot
        self._detector = detector
        self._mapper = mapper
        self._viz = visualizer
        self._paused = False

    def run(self) -> None:
        import cv2

        cap = self._open_camera(cv2)
        self._robot.connect()
        # Seed targets from the live arm position so the first commands cause no jump.
        smoother = TargetSmoother(self._cfg.smoothing, self._robot.read_positions())
        window = "SO-101 hand teleop"
        min_dt = 1.0 / self._cfg.control_hz if self._cfg.control_hz > 0 else 0.0
        fps = 0.0
        last = time.perf_counter()

        try:
            while True:
                tick = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Camera frame grab failed; stopping.")
                    break
                if self._cfg.mirror:
                    frame = cv2.flip(frame, 1)

                detection = self._detector.detect(frame)

                if self._paused:
                    targets = smoother.hold()
                elif detection is not None:
                    targets = smoother.update(self._mapper.map(detection.features))
                else:
                    targets = smoother.hold()  # hand lost -> hold last safe target

                positions = self._robot.send_targets(targets)

                # smooth fps estimate
                now = time.perf_counter()
                inst = 1.0 / max(now - last, 1e-6)
                fps = 0.9 * fps + 0.1 * inst if fps else inst
                last = now

                if self._cfg.show_window and self._viz is not None:
                    info = {
                        "mode": "SIM" if self._robot.is_simulation else "ROBOT",
                        "fps": fps,
                        "paused": self._paused,
                    }
                    frame = self._viz.draw(frame, detection, targets, positions, info)
                    cv2.imshow(window, frame)
                    if self._handle_keys(cv2, smoother):
                        break

                # cap the control rate
                sleep = min_dt - (time.perf_counter() - tick)
                if sleep > 0:
                    time.sleep(sleep)
        finally:
            self._shutdown(cap, cv2)

    def _open_camera(self, cv2):
        cap = cv2.VideoCapture(self._cfg.camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open camera index {self._cfg.camera_index}. "
                "Try a different --camera index, and grant camera permission to your terminal."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cfg.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cfg.frame_height)
        return cap

    def _handle_keys(self, cv2, smoother: TargetSmoother) -> bool:
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):  # q or ESC
            return True
        if key == ord(" "):
            self._paused = not self._paused
            logger.info("Paused" if self._paused else "Resumed")
        if key == ord("h"):
            # ease toward the neutral home pose (rate limiting still applies on send)
            for m, v in home_pose().items():
                smoother._state[m] = v  # noqa: SLF001 - intentional internal nudge
            logger.info("Set target to home pose.")
        return False

    def _shutdown(self, cap, cv2) -> None:
        try:
            self._robot.disconnect()
        finally:
            self._detector.close()
            cap.release()
            if self._cfg.show_window:
                cv2.destroyAllWindows()
