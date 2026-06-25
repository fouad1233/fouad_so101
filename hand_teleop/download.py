"""Small HTTPS download helper with a certifi CA bundle.

The python.org interpreter ships without root certificates, so plain urllib HTTPS fails; using
``certifi`` fixes it. Shared by the model/asset downloaders.
"""

from __future__ import annotations

import shutil
import ssl
import urllib.request
from pathlib import Path


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # pragma: no cover
        return ssl.create_default_context()


def fetch(url: str, dest: Path) -> Path:
    """Download ``url`` to ``dest`` (atomically) if needed; return ``dest``."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, context=_ssl_context(), timeout=60) as resp, open(tmp, "wb") as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(dest)
    return dest
