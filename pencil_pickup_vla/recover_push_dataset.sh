#!/usr/bin/env bash
# Recover a locally-recorded LeRobot dataset and push it to the Hugging Face Hub.
#
# Use this if `1_record_dataset.sh` finished recording but the final Hub push failed (e.g. wrong
# HF_USER, network blip). Your episodes are always saved locally first under
#   ~/.cache/huggingface/lerobot/<repo_id>/
# so they are NOT lost — this just uploads that local folder.
#
# Usage:
#   ./recover_push_dataset.sh                         # auto-find the newest local dataset, push to $DATASET_REPO
#   ./recover_push_dataset.sh /path/to/local/dataset  # push a specific local folder to $DATASET_REPO
#   ./recover_push_dataset.sh /path/to/local/dataset  fouad1233/my_dataset   # explicit target repo
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env
source ../.venv/bin/activate

SRC="${1:-}"
TARGET="${2:-$DATASET_REPO}"

# Auto-find the most recently modified local LeRobot dataset (one with meta/info.json) if not given.
if [ -z "$SRC" ]; then
  SRC=$(find ~/.cache/huggingface/lerobot -type f -name info.json -path "*/meta/*" -print0 2>/dev/null \
        | xargs -0 ls -td 2>/dev/null | head -1 | xargs -n1 dirname | xargs -n1 dirname)
  echo "Auto-detected local dataset: $SRC"
fi

[ -f "$SRC/meta/info.json" ] || { echo "ERROR: '$SRC' is not a LeRobot dataset (no meta/info.json)." >&2; exit 1; }

echo "Pushing '$SRC' -> https://huggingface.co/datasets/$TARGET"
python - "$SRC" "$TARGET" <<'PY'
import sys
from huggingface_hub import HfApi
src, repo = sys.argv[1], sys.argv[2]
api = HfApi()
print("logged in as:", api.whoami()["name"])
api.create_repo(repo, repo_type="dataset", exist_ok=True)
api.upload_folder(folder_path=src, repo_id=repo, repo_type="dataset",
                  commit_message="Push recovered LeRobot dataset")
print("DONE -> https://huggingface.co/datasets/" + repo)
PY
