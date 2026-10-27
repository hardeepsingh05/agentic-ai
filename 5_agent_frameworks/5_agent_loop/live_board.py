"""The live board: a rich.Live view of the shared board while the team works.

Each game is drawn in its owner's colour, with the steps that worker writes for
itself indented beneath in the same colour. Done items are dimmed and struck
through, the one in progress is bold, pending is plain. A small legend maps colour
to framework. The colour comes from the orchestrator's registry (goal id -> worker),
so the board schema and the workers stay untouched: a worker never needs to know
its own colour.
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.text import Text

import board

console = Console()


def _line(todo: dict, colour: str, label: str, indent: str = "") -> Text:
    """
    Style one todo for the live view: dimmed and struck through when done, bold when in progress, plain when pending.

    Args:
        todo: The todo as a dictionary from board.list_todos().
        colour: The rich colour of the worker that owns it.
        label: The text to show.
        indent: Leading whitespace, used to nest steps under their goal.

    Returns:
        rich.text.Text: The styled line, with the todo's result appended when it is done.

    Raises:
        KeyError: If the todo lacks a status or result entry.
    """
    text = Text(indent)
    if todo["status"] == "done":
        text.append(label, style=f"{colour} dim strike")
        if todo["result"]:
            text.append(f"   {todo['result']}", style="dim")
    elif todo["status"] == "in_progress":
        text.append(label, style=f"bold {colour}")
    else:
        text.append(label, style=colour)
    return text


def render(registry: dict[int, dict]) -> Group:
    """
    Build the whole board as one renderable from the current board state.

    Args:
        registry: Each launched goal's id mapped to its worker record, which supplies the name, colour and objective.

    Returns:
        rich.console.Group: The goals and their steps in their owners' colours, followed by a legend.

    Raises:
        sqlite3.OperationalError: If the shared board has not been created or stays locked.
        KeyError: If a registered worker record has no "name" or "colour".
    """
    todos = board.list_todos()
    children: dict[int | None, list[dict]] = {}
    for todo in todos:
        children.setdefault(todo["parent_id"], []).append(todo)

    lines: list[Text] = []
    for goal in children.get(None, []):
        worker = registry.get(goal["id"])
        colour = worker["colour"] if worker else "white"
        if worker:
            objective = worker.get("objective")
            label = f"{worker['name']}: {objective}" if objective else worker["name"]
        else:
            label = goal["task"][:48]
        lines.append(_line(goal, colour, label))
        for step in children.get(goal["id"], []):
            lines.append(_line(step, colour, step["task"], indent="    "))

    legend = Text("\n")
    seen = set()
    for worker in registry.values():
        if worker["name"] in seen:  # a fixed worker is registered twice; show it once
            continue
        seen.add(worker["name"])
        legend.append(f"{worker['name']}  ", style=worker["colour"])
    lines.append(legend)
    return Group(*lines)