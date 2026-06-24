# Plan — Hand-Tracking Teleoperation for SO-101 (follower)

**Goal:** Use a webcam to track my hand and make the **SO-101 follower** arm mirror my hand's
movements in real time (a markerless, hardware-leader-free teleoperation), with a live on-screen
view that overlays the detected hand and a schematic of how the arm will move.

**Hard requirement:** never command the arm outside safe joint limits, and never let it jump suddenly
— the arm is assumed already **calibrated**.

**Design principles:** object-oriented, small single-responsibility classes, dependency-injected so each
part is testable in isolation, and a **simulation mode** so the whole pipeline runs and is testable
without the physical arm.

---

## Architecture (data flow)

```
Webcam ─▶ HandDetector ─▶ HandFeatures ─▶ HandToJointMapper ─▶ TargetSmoother ─▶ RobotInterface
 (cv2)   (MediaPipe)      (x,y,depth,      (per-joint linear     (EMA + rate     (SO101 / Sim)
                          roll,pitch,       map + clamp to         limit, safety)
                          pinch)            safe sub-range)
                                                    │
                                                    └─▶ Visualizer (overlay hand + 2D arm schematic)
```

Joint outputs use LeRobot's **normalized** space (`use_degrees=False`): the 5 body joints are
`[-100, 100]` (mapped from the calibrated range of motion, so staying inside is inherently safe) and
the gripper is `[0, 100]`.

---

## Tasks

### Task 1 — Project scaffolding ✅
- [x] 1.1 Create `hand_teleop/` package folder.
- [x] 1.2 Write this `plan.md`.
- [x] 1.3 Define config dataclasses (`config.py`): mapping, smoothing, safety, tracking, robot, app.

### Task 2 — Hand tracking ✅
- [x] 2.1 `features.py`: `HandFeatures` dataclass + hand connection topology for drawing.
- [x] 2.2 `hand_tracking.py`: `HandDetector` ABC + `MediaPipeHandDetector` producing normalized
  features (palm x/y, depth proxy, roll, pitch, pinch) + pixel landmarks for drawing.

### Task 3 — Mapping & safety ✅
- [x] 3.1 `mapping.py`: `HandToJointMapper` — per-joint linear map of a feature to a safe sub-range,
  with hard clamping (Safety layer 1).
- [x] 3.2 `mapping.py`: `TargetSmoother` — exponential smoothing + max-step rate limit (Safety layer 2).
- [x] 3.3 Initialize targets from the arm's current position so there is **no jump** at startup.

### Task 4 — Robot interface ✅
- [x] 4.1 `robot.py`: `RobotInterface` ABC.
- [x] 4.2 `SO101RobotController` wrapping LeRobot `SO101Follower` with `max_relative_target`
  (Safety layer 3, enforced by the hardware driver).
- [x] 4.3 `SimulatedRobot` — same interface, integrates targets in software (no hardware needed).

### Task 5 — Visualization ✅
- [x] 5.1 `kinematics.py`: `ArmSchematic` — simple planar forward kinematics for a side-view stick
  drawing of the arm from joint values.
- [x] 5.2 `visualizer.py`: overlay hand landmarks, per-joint target bars, the arm schematic
  (side view + base-pan dial + gripper indicator), and status text.

### Task 6 — Application & CLI ✅
- [x] 6.1 `app.py`: `HandTeleopApp` main loop (capture → detect → map → smooth → send → draw),
  with keyboard controls (quit / pause-hold / home) and guaranteed safe shutdown.
- [x] 6.2 `cli.py` + `__main__.py`: argument parsing; **sim by default**, real robot when `--port` given.

### Task 7 — Testing ✅
- [x] 7.1 `tests/test_mapping.py`: mapping monotonicity, clamping to safe range, smoother rate-limit.
- [x] 7.2 `tests/test_kinematics.py`: schematic FK is finite/bounded across the full joint range.
- [x] 7.3 Import smoke test + headless simulation run (no camera/GUI).

### Task 9 — 3D URDF viewer ✅ (added after Day-2 feedback)
- [x] 9.1 `urdf_assets.py`: download + cache the official SO-101 URDF + meshes (SO-ARM100).
- [x] 9.2 `urdf_viewer.py`: browser-based 3D viewer using **viser** (WebGL) — robust on macOS, unlike
  native pyglet/trimesh windows. Maps normalized values onto URDF joint limits.
- [x] 9.3 App runs the viser viewer **in-process** (background thread) and updates it each frame when
  `--urdf-view` is set; user opens http://localhost:8080.
- [x] 9.4 `net.py`: UDP transport kept for driving the standalone viewer from another process/machine.
- [x] 9.5 Widen mapping ranges + add per-joint active input slice (`in_lo`/`in_hi`) so joints reach
  their full range (fixes "can't go down / can't reach max").
- [x] 9.6 `tests/test_urdf_viewer.py`: radian mapping, invert, clamping, UDP round-trip, viser load.

### Task 10 — Whole-arm tracking (future)
- [ ] 10.1 Add a `PoseArmDetector` (MediaPipe Pose: shoulder→elbow→wrist) behind the `HandDetector`
  interface, mapping the physical arm to the robot for a larger, more natural range.

### Task 8 — Docs ✅
- [x] 8.1 `requirements.txt` (Python dependencies).
- [x] 8.2 `README.md` run guide (install, calibration assumption, how to run sim & real, controls,
  tuning, safety notes, URDF/3D notes).

---

## Safety model (defense in depth)

1. **Calibrated normalized space** — `[-100,100]` already corresponds to the recorded range of motion.
2. **Configured safe sub-range** — defaults clamp well inside that (e.g. ±60 for most joints).
3. **EMA smoothing + max-step per tick** — no jitter, no sudden jumps.
4. **`max_relative_target`** in the LeRobot driver — final hardware cap on per-command motion.
5. **Startup from current pose** — targets seeded from the live reading; the arm does not snap.
6. **Hold-on-loss** — if the hand leaves the frame, the last safe target is held (no flailing).
7. **Pause / Home keys** and a `finally` block that always disconnects (disabling torque) on exit.

## Out of scope / future
- Full **URDF + mesh 3D** rendering of the arm. We ship a lightweight 2D schematic instead (no extra
  heavy deps, disk-friendly). The URDF route (e.g. `rerun`/`pybullet` + the SO-ARM100 URDF) is noted
  in the README as a future enhancement.
- Inverse kinematics (mapping hand 3D position to a Cartesian end-effector target). We use a direct,
  interpretable feature→joint mapping, which is robust and easy to reason about for safety.
