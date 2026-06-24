"""Map hand features to joint targets, then smooth/limit them for safe motion."""

from __future__ import annotations

from .config import FEATURE_DOMAINS, MOTORS, MappingConfig, SafetyConfig, SmoothingConfig
from .features import HandFeatures


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class HandToJointMapper:
    """Linear, per-joint mapping from a single hand feature to a safe output sub-range.

    Each joint reads one feature, normalizes it to ``[0, 1]`` over its known domain, optionally
    inverts it, then scales to the joint's configured ``[out_min, out_max]``. A final hard clamp
    (the :class:`SafetyConfig` range) guarantees the command never leaves the safe envelope.
    """

    def __init__(self, mapping: MappingConfig, safety: SafetyConfig):
        self._mapping = mapping
        self._safety = safety

    def map(self, features: HandFeatures) -> dict[str, float]:
        out: dict[str, float] = {}
        for motor, jm in self._mapping.joint_maps.items():
            value = getattr(features, jm.feature)
            domain_lo, domain_hi = FEATURE_DOMAINS[jm.feature]
            lo = jm.in_lo if jm.in_lo is not None else domain_lo
            hi = jm.in_hi if jm.in_hi is not None else domain_hi
            t = (value - lo) / (hi - lo) if hi > lo else 0.0
            t = _clamp(t, 0.0, 1.0)
            if jm.invert:
                t = 1.0 - t
            out[motor] = jm.out_min + t * (jm.out_max - jm.out_min)
        return self._apply_safety(out)

    def _apply_safety(self, targets: dict[str, float]) -> dict[str, float]:
        s = self._safety
        safe: dict[str, float] = {}
        for motor, value in targets.items():
            if motor == "gripper":
                safe[motor] = _clamp(value, s.gripper_min, s.gripper_max)
            else:
                safe[motor] = _clamp(value, s.clamp_min, s.clamp_max)
        return safe


class TargetSmoother:
    """Exponential smoothing + per-tick rate limit.

    Initialize from the arm's current position so the first commands cause no jump. Smoothing removes
    jitter; the rate limit caps how far a target can move in a single control tick.
    """

    def __init__(self, cfg: SmoothingConfig, initial: dict[str, float]):
        self._cfg = cfg
        self._state: dict[str, float] = {m: float(initial.get(m, 0.0)) for m in MOTORS}

    @property
    def state(self) -> dict[str, float]:
        return dict(self._state)

    def reset(self, position: dict[str, float]) -> None:
        for m in MOTORS:
            if m in position:
                self._state[m] = float(position[m])

    def hold(self) -> dict[str, float]:
        """Return the current target unchanged (used when no hand is visible)."""
        return dict(self._state)

    def update(self, target: dict[str, float]) -> dict[str, float]:
        a = self._cfg.ema_alpha
        max_step = self._cfg.max_step
        for m in MOTORS:
            if m not in target:
                continue
            desired = (1.0 - a) * self._state[m] + a * target[m]
            delta = _clamp(desired - self._state[m], -max_step, max_step)
            self._state[m] += delta
        return dict(self._state)
