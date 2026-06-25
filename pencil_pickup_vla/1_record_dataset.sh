#!/usr/bin/env bash
# Stage 1 — record teleoperated demonstrations of the pick-and-place task.
# You move the LEADER arm; the FOLLOWER mirrors it and everything (joints + camera) is recorded.
#
# Controls during recording (keyboard):
#   Right Arrow  -> end the current episode early and move to the next
#   Left Arrow   -> cancel & re-record the current episode
#   Escape       -> stop recording and save the dataset
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env
source ../.venv/bin/activate

# Fail fast (BEFORE recording) if the HF username is still the placeholder, otherwise the Hub push
# at the very end fails and it looks like the data was lost (it isn't — it's saved locally first).
if [ "$HF_USER" = "your-hf-username" ]; then
  echo "ERROR: set HF_USER in config.env to your real Hugging Face username first." >&2
  exit 1
fi
# Confirm you're logged in so the end-of-recording push succeeds.
hf auth whoami >/dev/null 2>&1 || { echo "ERROR: run 'hf auth login' first." >&2; exit 1; }

lerobot-record \
  --robot.type=so101_follower \
  --robot.port="$FOLLOWER_PORT" \
  --robot.id="$FOLLOWER_ID" \
  --robot.cameras="{ front: {type: opencv, index_or_path: $CAMERA_INDEX, width: $CAMERA_W, height: $CAMERA_H, fps: $CAMERA_FPS}}" \
  --teleop.type=so101_leader \
  --teleop.port="$LEADER_PORT" \
  --teleop.id="$LEADER_ID" \
  --display_data=true \
  --dataset.repo_id="$DATASET_REPO" \
  --dataset.single_task="$TASK" \
  --dataset.num_episodes="$NUM_EPISODES" \
  --dataset.fps="$CAMERA_FPS" \
  --dataset.episode_time_s="$EPISODE_TIME_S" \
  --dataset.reset_time_s="$RESET_TIME_S" \
  --dataset.push_to_hub=true

echo
echo "Done. Dataset pushed to: https://huggingface.co/datasets/$DATASET_REPO"
echo "Preview it with: lerobot-dataset-viz --repo-id=$DATASET_REPO"
