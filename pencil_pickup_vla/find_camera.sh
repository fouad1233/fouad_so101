#!/usr/bin/env bash
# List connected cameras and save a preview frame from each, so you can pick CAMERA_INDEX.
# Look in the printed output dir for the saved images, then set CAMERA_INDEX in config.env.
set -euo pipefail
cd "$(dirname "$0")"
source ../.venv/bin/activate

lerobot-find-cameras opencv
