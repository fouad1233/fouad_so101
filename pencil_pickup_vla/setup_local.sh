#!/usr/bin/env bash
# Install the LeRobot extras needed LOCALLY to record data and to run the policy.
# (Training itself happens on Kaggle — see the notebook.)
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate

# feetech = SO-101 motors, dataset = recording, smolvla = running the fine-tuned policy locally.
pip install -e "../lerobot[feetech,dataset,smolvla]"

echo
echo "Now log in to the Hugging Face Hub once (needed to push the dataset / pull the model):"
echo "    huggingface-cli login"
