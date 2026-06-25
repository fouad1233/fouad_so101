# hand_teleop — context & memory (for Claude / future me)

Webcam teleoperation of the **SO-101 follower** arm: track the user's **hand** (MediaPipe Hands) or
**whole arm** (MediaPipe Pose) and drive the 6 joints. OOP, dependency-injected, with a **simulation
mode** so the whole pipeline runs and is tested without hardware. See [plan.md](plan.md) for the task
list and [README.md](README.md) for the user-facing run guide.

## Pipeline / architecture

```
Webcam ─▶ Detector ─▶ HandFeatures ─▶ HandToJointMapper ─▶ TargetSmoother ─▶ RobotInterface
 (cv2)   (hand|arm)   (x,y,depth,        (per-joint linear     (EMA + rate     (SO101 | Sim)
                       roll,pitch,pinch)   map + safety clamp)   limit)              │
                                                                                     └▶ URDF viewer
```

- `config.py` — all tunables (dataclasses): `MappingConfig` (per-joint `JointMap`: feature, out range,
  invert, active input slice `in_lo/in_hi`), `SmoothingConfig`, `SafetyConfig`, `TrackingConfig`,
  `PoseConfig`, `RobotConfig`, `UrdfViewConfig`, `AppConfig`. `MOTORS` = the 6 joint names in bus order.
- `features.py` — `HandFeatures` (the shared, normalized contract) + `HandDetection` (landmarks_px,
  `connections`, `overlays`). `HAND_CONNECTIONS` (21-pt) and `ARM_CONNECTIONS` (shoulder→elbow→wrist).
- `hand_tracking.py` — `HandDetector` ABC + `MediaPipeHandDetector` (Tasks **HandLandmarker**, VIDEO).
- `pose_tracking.py` — `PoseArmDetector` (Tasks **PoseLandmarker**) + `CombinedArmHandDetector`
  (Pose for arm joints **and** Hands for gripper/roll) + pure `compute_arm_features`.
- `mapping.py` — `HandToJointMapper` (+ safety clamp) and `TargetSmoother` (EMA + max-step).
- `robot.py` — `RobotInterface`, `SO101RobotController` (LeRobot `SO101Follower`, normalized space),
  `SimulatedRobot`, `make_robot` (sim has a huge rate cap so it tracks directly).
- `urdf_viewer.py` / `urdf_assets.py` / `net.py` — 3D URDF viewer (viser, separate process, UDP-fed).
- `visualizer.py` — OpenCV overlay (skeleton(s), joint bars, 2D schematic). `kinematics.py` — 2D FK.
- `app.py` — `HandTeleopApp` loop. `cli.py` / `__main__.py` — entry point. `download.py` — HTTPS helper.

Joint space: LeRobot **normalized** (`use_degrees=False`): body joints `[-100,100]` (= calibrated
range, so staying inside is inherently safe), gripper `[0,100]`. Action keys are `f"{motor}.pos"`.

## Environment gotchas (this machine: macOS arm64, python.org Python 3.12 venv at ../.venv)

- **LeRobot needs Python ≥3.12**; it's a git submodule at `../lerobot`, installed `-e ".[feetech]"`.
- **OpenCV window**: LeRobot pins `opencv-python-headless` (no GUI). Must `pip uninstall -y
  opencv-python-headless`; `mediapipe` pulls `opencv-contrib-python` (GUI-capable).
- **MediaPipe**: this build (0.10.35) has **only the Tasks API** (`mediapipe.tasks`), NOT the legacy
  `mp.solutions`. Models (`hand_landmarker.task`, `pose_landmarker_*.task`) auto-download to `models/`.
- **SSL**: the python.org interpreter has no root certs → urllib downloads must use a `certifi`
  context (see `download.py`). Same fix applies to MediaPipe model URLs and the SO-101 URDF.
- **Camera permission (TCC)**: a process *I* spawn can't get camera access; the **user must run it from
  their own Terminal** so macOS shows the permission prompt. I cannot grant TCC programmatically.
- **3D viewer**: trimesh/pyglet native viewer needs `pyglet<2` and is unreliable on macOS → use
  **viser** (browser/WebGL) instead. It must run in a **separate process** (the busy camera loop
  starves an in-process web server and the page won't load). URDF/meshes from TheRobotStudio/SO-ARM100
  cached in `urdf_so101/` (gitignored, like `models/`).
- I can't see the live camera/GUI/browser from here — verify everything testable headlessly (servers,
  UDP, model loads, the 27 tests) and rely on the user for the final visual confirmation.

## Problems hit during development & the fixes (most recent first)

1. **Arm tracking never matched exactly** → pan/lift were driven by the **wrist**, coupling the elbow
   into them. Fix: drive pan+lift from the **upper-arm** direction (shoulder→elbow) and elbow_flex from
   the **true 3D angle** (`pose_world_landmarks`). DOFs now decoupled like the real serial arm.
2. **"no target" for valid in-frame poses** → the `min_visibility>=0.6` gate was too strict (visibility
   scores are flaky for self-occluding poses). Fix: reject phantom arms by checking elbow/wrist are
   **inside the frame** (`bounds_margin`); visibility gate now off by default.
3. **3 confusing points on the hand** → those were Pose's coarse thumb/index/pinky guesses (unused in
   combined mode). Fix: arm skeleton is now just shoulder→elbow→wrist; the real 21-pt hand is drawn in
   a distinct color (magenta/yellow).
4. **Gripper didn't work in arm mode** → pure Pose hand points are useless. Fix: `--track arm` uses
   `CombinedArmHandDetector` = Pose (arm) + Hands (gripper/roll).
5. **pan/lift pinned at limits** → fixed gain on raw pixel offset saturated. Fix: normalize by arm
   length, then (see #1) by upper-arm direction cosine; gain ~1.3.
6. **Felt laggy / "not following"** → low FPS + conservative smoothing. Fix: `ema_alpha` 0.35→0.5,
   `max_step` 6→15, **sim robot tracks targets directly**, pose model default `lite` (complexity 0).
7. **URDF page wouldn't load** → viser ran in-process and the camera loop starved it. Fix: run viser in
   a **separate process**, stream joint states over UDP (`net.py`).
8. **`elbow_flex` (joint 3) backwards** → inverted by default; `--invert-joints` flips any joint(s).

## Run / test

```bash
# from repo root, with ../.venv active and opencv-python-headless removed:
python -m hand_teleop                              # hand mode, simulation
python -m hand_teleop --track arm --urdf-view      # whole-arm + 3D URDF (open http://localhost:8080)
python -m hand_teleop --track arm --port /dev/tty.usbmodem5B421352311 --id my_follower --max-relative-target 6
# tuning: --invert-joints, --pose-complexity {0,1,2}, --min-visibility, --arm-side, --ema-alpha, --max-step
python -m hand_teleop.tests.test_mapping   # + test_kinematics test_pipeline test_urdf_viewer test_pose (27 total)
```

## Known limits / good next steps

- **Monocular depth** limits true accuracy: forward/back reach and **wrist roll** are estimated and
  noisy. A second camera or depth cam would be needed for full 3D.
- `wrist_flex` is forearm pitch (not hand-relative); could derive it from the Hands model for fidelity.
- Real-robot **sign/zero registration**: normalized space depends on the user's calibration; the URDF
  view zero is approximate. Verify directions on the real arm and flip with `--invert-joints` if needed.
- Safety on hardware: start with low `--max-relative-target`; the LeRobot driver caps every command;
  torque is disabled on disconnect (arm goes limp — don't leave it holding an extended/heavy pose).
