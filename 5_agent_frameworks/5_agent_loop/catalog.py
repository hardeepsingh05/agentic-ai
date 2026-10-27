"""The worker manifest: which framework builds which game, how to launch it, and
the colour it flies on the live board.

"""

from __future__ import annotations
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# One record per framework, in the order. Key is also the slug, the folder its game is built into;
# file is relative to this folder; colour is a rich colour for the live board; runner picks the launcher.
WORKERS = [
    {
        "key": "strands", "name": "AWS Strands", "colour": "cyan", "file": "../2_strands_pydantic/strands_worker.py", "runner": "python"
    },
    {
        "key": "pydantic", "name": "Pydantic AI", "colour": "green", "file": "../2_strands_pydantic/pydantic_worker.py", "runner": "python"
    },
    {
        "key": "maf", "name": "Microsoft Agent Framework", "colour": "magenta", "file": "../3_maf_agno/maf_worker.py", "runner": "python"
    },
    {
        "key": "agno", "name": "Agno", "colour": "yellow", "file": "../3_maf_agno/agno_worker.py", "runner": "python"
    },
]

def discover(skip: tuple[str, ...] = ()) -> list[dict]:
    """
    The worker whose files exist on disk, minus any skipped by key. Each result is its manifest record with slug set to its key (the folder its game builds into);
    the game itself is invented at runtime, so nothing about it is fixed here.
    
    Args:
        skip: A tuple of worker keys to leave out.

    Returns:
        A list of the discovered worker manifest records, each with its slug set to the worker's key.
    """
    found = []
    for worker in WORKERS:
        if worker['key'] in skip:
            continue
        if (HERE / worker["file"]).exists():
            found.append({**worker, "slug": worker["key"]})
    return found

def launch_argv(worker: dict, task_id: int, board_path: Path) -> list[str]:
    """
    The subprocess argv that runs a worker in Day 5 mode against the shared board.

    The "python" runner uses the interpreter running the orchestrator (sys.executable), so workers see the same
    installed packages. Any other runner launches the worker through npx tsx; npx is resolved to its full path
    with shutil.which because on Windows it is a .cmd shim that subprocess.Popen cannot find by its bare name.
    
    Args:
        worker: The worker manifest record, with its "file" path and "runner".
        task_id: The ID of the board goal the worker should take.
        board_path: The path to the shared board file.

    Returns:
        A list of command-line arguments to launch the worker.

    Raises:
        KeyError: If the worker record has no "file" or "runner" entry.
    """

    path = str((HERE / worker["file"]).resolve())
    if worker["runner"]=="python":
        # sys.executable keeps workers on the same environment (and packages) as the orchestrator.
        return [sys.executable, path, str(task_id), str(board_path)]
    return [shutil.which("npx") or "npx", "tsx", path, str(task_id), str(board_path)]
   

