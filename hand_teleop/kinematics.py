"""Lightweight planar forward kinematics for the on-screen arm schematic.

This is a *schematic* (approximate link lengths, single plane) purely for visual feedback of how the
SO-101 will move. It is not a physically exact model and is not used for control. A full URDF/mesh 3D
view is noted as a future enhancement in the README.
"""

from __future__ import annotations

import math


class ArmSchematic:
    """Maps normalized joint values to 2D points for a side-view stick drawing."""

    def __init__(
        self,
        lengths: tuple[float, float, float] = (70.0, 60.0, 45.0),  # upper arm, forearm, wrist (px)
        spans: tuple[float, float, float] = (90.0, 110.0, 80.0),   # degrees of swing per joint
    ):
        self.lengths = lengths
        self.spans = spans

    def side_view_points(self, targets: dict[str, float]) -> list[tuple[float, float]]:
        """Return [base, elbow, wrist, tip] in a local frame where +x is right and +y is up."""
        lift = targets["shoulder_lift"] / 100.0 * self.spans[0]
        elbow = targets["elbow_flex"] / 100.0 * self.spans[1]
        wflex = targets["wrist_flex"] / 100.0 * self.spans[2]

        # Angles measured from the +x axis; the upper arm starts pointing up (90 deg).
        a1 = 90.0 - lift
        a2 = a1 - elbow
        a3 = a2 - wflex

        points = [(0.0, 0.0)]
        x = y = 0.0
        for length, angle in zip(self.lengths, (a1, a2, a3)):
            x += length * math.cos(math.radians(angle))
            y += length * math.sin(math.radians(angle))
            points.append((x, y))
        return points

    @staticmethod
    def pan_angle_deg(targets: dict[str, float]) -> float:
        """Base rotation in degrees for the top-down dial (just for display)."""
        return targets["shoulder_pan"] / 100.0 * 90.0

    @staticmethod
    def gripper_opening(targets: dict[str, float]) -> float:
        """Gripper opening as a fraction in [0, 1]."""
        return max(0.0, min(1.0, targets["gripper"] / 100.0))
