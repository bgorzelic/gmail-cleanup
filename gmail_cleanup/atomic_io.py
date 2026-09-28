"""Concurrency-safe file replacement for read-modify-write updates.

`state.py` and `lists_io.py` both update a small file in place: read, change,
write. A daily launchd autopilot and a manual command can do that to the same
file at the same time, and the old temp-file-plus-rename pattern was not safe
under it:

- Both writers derived the same fixed temp name from the target (`.json.tmp`,
  `.yaml.tmp`), so concurrent writers clobbered each other's temp file and the
  loser's rename failed with FileNotFoundError.
- Nothing serialised the read-modify-write, so a writer that read before a
  sibling's rename silently discarded that sibling's write.
- A crash between the write and the rename left the temp file as the only copy
  of the new data, and the next run overwrote it.

`file_lock` serialises the whole read-modify-write; `atomic_write` writes to a
unique temp file in the destination directory and removes it if anything fails,
so a failure leaves the original untouched and nothing behind.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:  # pragma: no cover - fcntl is absent on Windows
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

LOCK_SUFFIX = '.lock'


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock covering a read-modify-write of `path`.

    Uses a sidecar `<path>.lock` file, which must live in the same directory as
    `path` so a replacement of `path` never orphans the lock. The lock file is
    left in place on purpose: unlinking it would race with waiters.
    """
    if fcntl is None:  # pragma: no cover - no advisory locking available
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.with_name(path.name + LOCK_SUFFIX), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        # Closing the descriptor releases the lock.
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def atomic_write(path: Path, text: str) -> None:
    """Replace `path` with `text`, leaving `path` untouched if anything fails.

    The temp file is created in the target's directory so the rename stays
    within one filesystem, and is removed on failure so a crash never strands
    the only copy of a newer version.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f'{path.name}.', suffix='.tmp')
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with tmp.open('w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
