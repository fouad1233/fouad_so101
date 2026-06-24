"""Download and cache the official SO-101 URDF + meshes (from TheRobotStudio/SO-ARM100).

Files are cached under ``hand_teleop/urdf_so101/`` (gitignored). Only needs internet on first use.
"""

from __future__ import annotations

import logging
import re
import shutil
import ssl
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

_RAW_BASE = (
    "https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/Simulation/SO101/"
)
_URDF_NAME = "so101_new_calib.urdf"
_CACHE_DIR = Path(__file__).parent / "urdf_so101"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover
        return ssl.create_default_context()


def _download(url: str, dest: Path, ctx: ssl.SSLContext) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, context=ctx, timeout=60) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)


def ensure_urdf(cache_dir: Path = _CACHE_DIR) -> Path:
    """Ensure the URDF and all meshes it references are present locally; return the URDF path."""
    urdf_path = cache_dir / _URDF_NAME
    ctx = _ssl_context()

    if not (urdf_path.exists() and urdf_path.stat().st_size > 0):
        logger.info("Downloading SO-101 URDF to %s ...", urdf_path)
        _download(_RAW_BASE + _URDF_NAME, urdf_path, ctx)

    # Parse relative mesh filenames (e.g. assets/foo.stl) and fetch any that are missing.
    text = urdf_path.read_text()
    meshes = sorted(set(re.findall(r'filename="([^"]+)"', text)))
    missing = [m for m in meshes if not (cache_dir / m).exists()]
    if missing:
        logger.info("Downloading %d SO-101 mesh(es) ...", len(missing))
        for rel in missing:
            _download(_RAW_BASE + rel, cache_dir / rel, ctx)
    logger.info("SO-101 URDF ready (%d meshes).", len(meshes))
    return urdf_path
