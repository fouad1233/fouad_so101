#!/usr/bin/env bash
# Upload 2_kaggle_finetune_smolvla.ipynb to Kaggle directly (no copy-paste), with GPU + Internet
# already enabled (see kernel-metadata.json). Re-running pushes a new version of the same notebook.
#
# Authenticate ONCE first (Kaggle CLI 2.x), pick one:
#   - Browser, no secrets to paste (recommended):   kaggle auth login
#   - Or export your API token (KGAT_...) for this shell:
#       export KAGGLE_API_TOKEN="KGAT_xxxxxxxx"
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate
pip show kaggle >/dev/null 2>&1 || pip install -q kaggle

# Quick auth check (works with cached `kaggle auth login` creds or a KAGGLE_API_TOKEN export).
if ! kaggle kernels list --mine >/dev/null 2>&1; then
  echo "Not authenticated. Run 'kaggle auth login' (browser) or export KAGGLE_API_TOKEN first." >&2
  exit 1
fi

kaggle kernels push -p .

echo
echo "Pushed -> https://www.kaggle.com/code/fouad1233/smolvla-pencil-pickup"
echo "Now on Kaggle: Add-ons -> Secrets -> add HF_TOKEN, then Run All."
echo "(GPU + Internet are already enabled via kernel-metadata.json.)"
