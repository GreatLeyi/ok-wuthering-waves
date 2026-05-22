"""Per-startup log rotation for mobile mode.

ok-script's logger (``ok.util.logger.config_logger``) uses a
``TimedRotatingFileHandler`` that rotates **at midnight**, so multiple
startups on the same day all append to ``logs/ok-script.log``.
Annoying when you're iterating: the latest run is buried below the
previous one, and you have to eyeball timestamps to find your session.

This helper, called *before* ``OK(...)`` constructs the logger, renames
the existing ``logs/ok-script.log`` to
``logs/ok-script.previous-<finish-ts>.log`` so the new run gets a
fresh, empty file.

Naming choice: the ``previous-`` prefix is deliberate -- ok-script's
``SafeFileHandler.getFilesToDelete`` deletes files matching the pattern
``ok-script.<YYYY-MM-DD>(.\\w+)?.log``.  Inserting ``previous-`` breaks
that match, so ok-script's daily-rotation cleanup leaves our session
files alone.  We do our own cleanup (keep most-recent N) below.

Why not just timestamp the live log file directly?  Because then
ok-script's daily rotation would create a sibling file with a different
name and the user has two log files per day to chase.  Renaming the
*previous* file on startup keeps the "current session = ok-script.log"
invariant ok-script expects.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

# Defaults match ok-script's own logger naming
# (ok.util.logger.config_logger uses name='ok-script' by default,
#  writing to logs/ok-script.log).
_LOGS_DIR = Path('logs')
_LOG_NAME = 'ok-script'
_PREVIOUS_PREFIX = 'previous-'
_KEEP_COUNT = 20


def rotate_previous_log(
    logs_dir: Path = _LOGS_DIR,
    log_name: str = _LOG_NAME,
    keep_count: int = _KEEP_COUNT,
) -> Path | None:
    """Rename ``logs_dir/<log_name>.log`` to a per-startup archive.

    Returns the path of the archived file, or ``None`` if there was
    nothing to rotate (no existing log, or the existing log is empty).

    Safe to call before ok-script's logger init: only touches the
    filesystem, no logging-module side effects.
    """
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    current = logs_dir / f'{log_name}.log'
    if not current.exists() or current.stat().st_size == 0:
        return None

    # Use the file's mtime (= time the previous run last wrote to it,
    # which is effectively "when the previous run ended") rather than
    # current time -- it's more useful for finding "the session that
    # just exited".
    finish_ts = time.localtime(current.stat().st_mtime)
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S', finish_ts)

    target = logs_dir / f'{log_name}.{_PREVIOUS_PREFIX}{stamp}.log'
    # Disambiguate if two startups happen in the same second.
    suffix = 0
    while target.exists():
        suffix += 1
        target = logs_dir / f'{log_name}.{_PREVIOUS_PREFIX}{stamp}_{suffix}.log'

    try:
        current.rename(target)
    except OSError:
        # If the file is locked (rare, only if a previous run didn't
        # close cleanly), don't crash the app; just skip rotation.
        return None

    _prune_old_archives(logs_dir, log_name, keep_count)
    return target


def _prune_old_archives(logs_dir: Path, log_name: str, keep_count: int) -> None:
    """Keep at most ``keep_count`` ``previous-*`` archives, delete the rest."""
    if keep_count <= 0:
        return
    pattern_prefix = f'{log_name}.{_PREVIOUS_PREFIX}'
    archives = [
        p for p in logs_dir.iterdir()
        if p.is_file() and p.name.startswith(pattern_prefix) and p.suffix == '.log'
    ]
    if len(archives) <= keep_count:
        return
    # Oldest first -> drop the head until we're under the limit.
    archives.sort(key=lambda p: p.stat().st_mtime)
    for victim in archives[:len(archives) - keep_count]:
        try:
            victim.unlink()
        except OSError:
            pass  # Best-effort; don't crash startup over a stale handle.
