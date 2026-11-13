"""Utility helpers shared across the engine."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def atomic_write_json(
    path: str,
    data: Any,
    indent: int = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
) -> None:
    """Atomically write data as JSON to `path`.

    Writes to a temporary file in the destination directory first, syncs to disk,
    and then renames over `path` via `os.replace()`. This ensures no partial/truncated
    files on crash or SIGTERM on both Windows and POSIX.
    """
    abs_path = os.path.abspath(path)
    parent_dir = os.path.dirname(abs_path)
    os.makedirs(parent_dir, exist_ok=True)

    tf = tempfile.NamedTemporaryFile(
        mode="w",
        dir=parent_dir,
        delete=False,
        encoding="utf-8",
        prefix=".tmp_",
        suffix=".json",
    )
    temp_path = tf.name
    try:
        json.dump(data, tf, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii)
        tf.write("\n")
        tf.flush()
        os.fsync(tf.fileno())
        tf.close()
        os.replace(temp_path, abs_path)
    except Exception:
        tf.close()
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise
