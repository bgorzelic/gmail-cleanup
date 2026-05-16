"""Progress UI wrapper around rich.progress, honoring --quiet/--verbose."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional, Tuple

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

_MODE = 'normal'
console = Console()


def set_mode(mode: str) -> None:
    global _MODE
    assert mode in ('quiet', 'normal', 'verbose')
    _MODE = mode


def is_quiet() -> bool:
    return _MODE == 'quiet'


def is_verbose() -> bool:
    return _MODE == 'verbose'


def vprint(*args, **kwargs) -> None:
    if _MODE == 'verbose':
        console.print(*args, **kwargs)


@contextmanager
def progress_for(description: str, total: int) -> Iterator[Optional[Tuple[Progress, TaskID]]]:
    if _MODE == 'quiet' or total == 0:
        yield None
        return
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task_id = progress.add_task(description, total=total)
        yield progress, task_id


def advance(handle, by: int = 1) -> None:
    if handle is None:
        return
    progress, task_id = handle
    progress.advance(task_id, advance=by)
