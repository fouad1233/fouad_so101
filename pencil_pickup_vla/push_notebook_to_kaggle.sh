#!/usr/bin/env bash
# Upload 2_kaggle_finetune_smolvla.ipynb to Kaggle directly (no copy-paste), with GPU + Internet
# already enabled (see kernel-metadata.json).
#
# One-time setup:
#   1) kaggle.com -> Settings -> API -> "Create New Token"  (downloads kaggle.json)
#   2) mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate
pip show kaggle >/dev/null 2>&1 || pip install -q kaggle

kaggle kernels push -p .

echo
echo "Pushed to https://www.kaggle.com/code/fouad1233/smolvla-pencil-pickup"
echo "Now on Kaggle: Add-ons -> Secrets -> add HF_TOKEN, then Run All."
echo "(GPU + Internet are already enabled via kernel-metadata.json.)"
