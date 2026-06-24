# Hand-Tracking Teleoperation for the SO-101 (follower)

Control your **SO-101 follower** arm by moving your **hand in front of a webcam**. A live window shows
your detected hand and a schematic of how the arm will move. No leader arm required.

> See [`plan.md`](plan.md) for the design/architecture and the task breakdown.

---

## How your hand maps to the arm

| Your hand movement                | SO-101 joint     | Feature |
|-----------------------------------|------------------|---------|
| Move left / right                 | `shoulder_pan`   | palm x  |
| Move up / down                    | `shoulder_lift`  | palm y  |
| Move toward / away from camera    | `elbow_flex`     | hand size (depth) |
| Tilt fingers up / down            | `wrist_flex`     | pitch   |
| Roll / rotate your hand           | `wrist_roll`     | roll    |
| Open / close thumb–index pinch    | `gripper`        | pinch   |

Each feature is mapped linearly into a safe sub-range of the joint and then smoothed. Each joint also
has an *active input slice* (`in_lo`/`in_hi`) so you reach its full range with comfortable hand motion
instead of pushing to the edge of the frame. Re-map or re-scale everything in [`config.py`](config.py).

---

## Prerequisites

- The SO-101 follower is **already set up and calibrated** (`lerobot-setup-motors` + `lerobot-calibrate`
  done, with a known `--robot.id`). See `../daily_progress/day1.md`.
- The project virtualenv with LeRobot installed (`../.venv`, created on Day 1).
- A working webcam.

## Install

From inside this `hand_teleop/` folder, using the project venv:

```bash
source ../.venv/bin/activate

# LeRobot ships opencv-python-headless (no GUI window). Remove it so we get a GUI-capable cv2:
pip uninstall -y opencv-python-headless

pip install -r requirements.txt
```

`mediapipe` provides the hand tracking and pulls in `opencv-contrib-python` (a GUI build of `cv2`).
LeRobot itself comes from the `../lerobot` submodule (already installed with `pip install -e
"../lerobot[feetech]"`).

---

## Run

Run from the **repository root** (the parent of this folder) so `python -m hand_teleop` resolves:

```bash
cd ..                       # repo root: fouad_so101/
source .venv/bin/activate
```

### 1) Simulation first (no hardware) — always start here

```bash
python -m hand_teleop
```

A window opens showing your hand and a simulated SO-101 reacting to it. Use this to check the camera,
the detection, and that each joint moves the way you expect **before** touching the real arm.

### 2) Real robot

```bash
python -m hand_teleop --port /dev/tty.usbmodem5B421352311 --id my_follower
```

Use your follower's port (from `lerobot-find-port`, recorded in `../myport.txxt`) and the `--robot.id`
you calibrated with.

### 3) Real 3D URDF view (accurate joint visualization)

Add `--urdf-view` to open a second window with the **official SO-101 URDF** rendered in 3D, following
the joints (far more accurate than the lightweight 2D schematic in the camera window):

```bash
python -m hand_teleop --urdf-view                 # simulation + 3D URDF window
python -m hand_teleop --urdf-view --port /dev/tty.usbmodem5B421352311 --id my_follower
```

- The URDF + meshes (TheRobotStudio/SO-ARM100) are **downloaded once** to `hand_teleop/urdf_so101/`.
- The viewer runs as a **separate process**, fed joint states over a local UDP socket, so it never
  interferes with the camera window or the control loop.
- You can also run it on its own (it just waits for joint states): `python -m hand_teleop.urdf_viewer`.
- Normalized joint values are mapped onto each URDF joint's limits, so the model spans the real range.
  Registration to the arm's exact zero is approximate; if a joint rotates the *wrong way*, run the
  viewer with e.g. `python -m hand_teleop.urdf_viewer --invert shoulder_pan,wrist_roll`.

### Controls (in the window)

| Key       | Action                                  |
|-----------|-----------------------------------------|
| `q`/`ESC` | quit (safely disconnects the arm)       |
| `space`   | pause / hold current pose               |
| `h`       | ease the arm back to a neutral home pose|

### Useful flags

```
--port PORT                 SO-101 serial port (omit => simulation)
--id ID                     calibration id (default: my_follower)
--camera N                  webcam index (default: 0)
--max-relative-target F     per-command joint cap, normalized units (default: 12) — lower = gentler
--ema-alpha F               smoothing 0..1, higher = snappier (default: 0.35)
--max-step F                max target change per tick (default: 6)
--urdf-view                 open the real 3D SO-101 URDF viewer (separate window)
--no-schematic              hide the 2D arm schematic overlay
--no-mirror                 do not mirror the camera image
-v                          verbose logging
```

---

## Safety (please read before running on hardware)

Defense in depth — the arm should never jump or exceed its calibrated range:

1. **Normalized space** — joints are commanded in `[-100, 100]` (gripper `[0, 100]`), which maps to the
   **calibrated** range of motion, so staying inside is inherently safe.
2. **Conservative sub-ranges** — defaults clamp well inside that (e.g. ±60 for most joints).
3. **Smoothing + per-tick rate limit** — no jitter, no sudden jumps.
4. **`--max-relative-target`** — the LeRobot driver caps every command's motion as a final hardware net.
5. **No startup jump** — targets are seeded from the arm's live position.
6. **Hold on hand-loss** — if your hand leaves the frame, the last safe pose is held.

Keep a hand near the power switch the first time, start with a **low `--max-relative-target`** (e.g. 6),
and make sure the workspace around the arm is clear. On quit the arm's torque is disabled (it goes
limp), so don't leave it holding a heavy/extended pose.

If a joint moves the **wrong direction** for your arm, flip its `invert` (or swap `out_min`/`out_max`)
in `config.py` → `MappingConfig`.

---

## Test

From the repo root:

```bash
python -m hand_teleop.tests.test_mapping
python -m hand_teleop.tests.test_kinematics
python -m hand_teleop.tests.test_pipeline
# or, if pytest is installed:  python -m pytest hand_teleop/tests -q
```

These cover the mapping/clamping, the smoother's rate limit, the schematic kinematics, and a full
headless pipeline run (mock hand → mapper → smoother → simulated robot) — no camera or arm needed.

---

## Troubleshooting

- **No window appears / `cv2.imshow` error** — the headless OpenCV is still installed. Run
  `pip uninstall -y opencv-python-headless` then `pip install -r requirements.txt`.
- **Camera won't open** — try `--camera 1`, and grant camera permission to your terminal app
  (macOS: System Settings → Privacy & Security → Camera).
- **Arm too jumpy** — lower `--max-relative-target` and `--max-step`, or lower `--ema-alpha`.
- **Arm too sluggish** — raise `--ema-alpha` (toward 1) and `--max-step`.
- **Depth/pinch feel off** — tune `DepthCalibration` / `PinchCalibration` in `config.py` to your
  camera distance and hand size.
- **Can't reach a joint's full range** — each joint maps from an *active* slice of its hand feature
  (`in_lo`/`in_hi` in `config.py` → `MappingConfig`). Widen the output range (`out_min`/`out_max`) or
  the active input slice for that joint.
- **A joint rotates the wrong way in the 3D view** — `python -m hand_teleop.urdf_viewer --invert <joint>`
  (or set `UrdfViewConfig.invert_joints`). To flip the *commanded* direction on the real arm instead,
  toggle that joint's `invert` in `MappingConfig`.
- **3D window doesn't open** — ensure `yourdfpy` is installed (`pip install -r requirements.txt`); the
  first run also needs internet to download the URDF/meshes.

---

## Project layout

```
hand_teleop/
├── plan.md            # design + task plan
├── README.md          # this file
├── requirements.txt
├── config.py          # all tunables (mapping, smoothing, safety, robot, app)
├── features.py        # HandFeatures dataclass + hand topology
├── hand_tracking.py   # HandDetector ABC + MediaPipeHandDetector
├── mapping.py         # HandToJointMapper + TargetSmoother
├── robot.py           # RobotInterface + SO101RobotController + SimulatedRobot
├── kinematics.py      # ArmSchematic (2D forward kinematics for the overlay)
├── visualizer.py      # OpenCV overlay (hand, joint bars, schematic)
├── urdf_assets.py     # downloads/caches the SO-101 URDF + meshes
├── urdf_viewer.py     # 3D URDF viewer process (yourdfpy), UDP-driven
├── net.py             # UDP JointStatePublisher / receiver
├── app.py             # HandTeleopApp control loop
├── cli.py / __main__  # command-line entry point
└── tests/             # headless unit + pipeline tests
```

## Visualization: 2D schematic vs 3D URDF

- The **camera window** always draws a lightweight **2D schematic** (no extra deps) for at-a-glance
  feedback.
- Adding **`--urdf-view`** opens the accurate **3D URDF** model (the official
  [SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) SO-101 URDF via `yourdfpy`), driven by the
  same joint targets over UDP.

## Future: whole-arm (body) tracking

Hand-only tracking has a limited, fiddly range (you noticed you can't always reach a joint's max). A
natural next step is **whole-arm tracking** with MediaPipe **Pose** (shoulder→elbow→wrist landmarks),
mapping your physical arm onto the robot arm for a larger, more intuitive workspace. The
`HandDetector` interface is designed so a `PoseArmDetector` can drop in as an alternative back-end.
