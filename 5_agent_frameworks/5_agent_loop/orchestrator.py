"""
The orchestrator: A Google Agent Development Kit(ADK) agent that runs the whole bunch of agents in a loop.

The orchestrator is not a Python loop that calls the worker. It is itself an ADK agent with a goal (build a language arcade with his team) and tools for the mechanical parts:
author the shared look, kick off each framework's builder, wait for the team agents to complete there work, play each finished game in a real browser to check it, and send a builder
back once to fix the game that doesn't work. The agent owns the decisions; the tools own the mechanics.

The whole run lives on one event loop. The launch and wait tools spawn workers with plain subprocess.Popen(no asyncio transports to outlive the loop), and the browser QA closes its MCP toolset in-loop, 
so there is no "event loop is closed" teardown.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from quiet import silence

silence()

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.agents.invocation_context import LlmCallsLimitExceededError # noqa: E402
from google.adk.agents.run_config import RunConfig # noqa: E402
from google.adk.runners import InMemoryRunner # noqa: E402
from google.genai import types # noqa: E402
from rich.live import Live # noqa: E402

import board # noqa: E402
import catalog # noqa: E402
import config # noqa: E402
import css_agent # noqa: E402
import live_board # noqa: E402
import prompts # noqa: E402
import qa_agent # noqa: E402

_APP = "agent_loop"
_MAX_TURNS = 80 # bounds the outer loop so it can't thrash
GAME_FILES = ("game.html", "game.css", "game.js")
WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT_S", "300")) # a worker hung past this is stopped so the run never stalls
QA_TIMEOUT = int(os.environ.get("QA_TIMEOUT_S", "150")) # a browser QA wedged past this is given up on so the run never stalls
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

def _read_title(game_html: Path) -> str:
    """
    The title builder gave its game, read from game.html (empty if not found).
    
    Args: 
        game_html: Path to the game's game.html.
    
    Returns: 
        The text of the page's <title>, or an empty string if it has none or the file cannot be read.

    Raises:
        UnicodeDecodeError: If game.html is not valid UTF-8.
    """

    try:
        match = _TITLE_RE.search(game_html.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return match.group(1).strip() if match else ""

def is_built(folder: Path) -> bool:
    """
    True if all three game files exist in the folder and are non-empty.

    Args:
        folder: The game's folder under the site directory.

    Returns:
        True if game.html, game.css and game.js all exist and are non-empty, otherwise False.

    Raises:
        OSError: If a file's size cannot be read, for example because of a permissions error.
    """
    return all(
        (folder / file).exists() and (folder / file).stat().st_size for file in GAME_FILES
    )

def _launch(goal_id: int, worker: dict, board_path: Path) -> subprocess.Popen:
    """
    Start one worker as a subprocess against the shared board.

    Stdout and stderr go to DEVNULL: a worker's framework banner would otherwise tear the live board, 
    and the worker only ever talks to us through the board. On POSIX, start_new_session puts the worker and
    its uv/npx/MCP tree in their own session so a timeout can stop the whole tree at once; on Windows the same job is done by
    taskkill /T in _terminate, so no new group is needed at launch.

    Args:
        goal_id: ID of the board goal the worker should take.
        worker: The worker manifest record from catalog.WORKERS.
        board_path: Path to the shared board file.

    Returns:
        subprocess.Popen: The launched worker process.

    Raises:
        OSError: If the worker's interpreter or script cannot be started.
        KeyError: If the worker record has no "file" or "runner" entry.
    """

    argv = catalog.launch_argv(worker, goal_id, board_path)
    cwd = str((catalog.HERE / worker["file"]).resolve().parent)
    group = {} if sys.platform == "win32" else {"start_new_session": True}
    return subprocess.Popen(
        argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd, **group
    )

def _terminate(procedure: subprocess.Popen) -> None:
    """
    Stop a worker and its uv/npx/MCP child tree (used only when a worker overruns its timeout).
    On Windows taskkill /T kills the whole tree by pid; on POSIX a SIGTERM to the process group 
    does the same.

    Args:
        procedure: The worker process to stop.
    
    Returns: 
        None

    Raises:
        None: ProcessLookupError and OSError from a process that has already exited are caught and ignored.
    """
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(procedure.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(os.getpgid(procedure.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

class Team:
    """
    The orchestrator's working state: the discovered workers and what has been
    launched so far. The tools read and mutate this; the agent never sees it.

    Attributes:
        language: The language the arcade teaches.
        workers: The discovered worker manifest records.
        site_dir: The shared site folder every game is built into.
        board_path: The shared board file.
        by_key: Workers indexed by framework key.
        by_slug: Workers indexed by the folder their game is built in.
        objectives: The learning objective assigned to each worker, by slug.
        registry: Each launched goal's ID mapped to its worker, so the live board can colour it.
        pending: Worker processes launched but not yet waited for.
        fixed: Slugs of the workers that have already used their one fix.
    """

    def __init__(self, language: str, workers: list[dict], site_dir: Path, board_path: Path) -> None:
        """
        Set up an empty team state for one run.

        Args:
            language: The language the arcade teaches.
            workers: The worker manifest records returned by catalog.discover().
            site_dir: The shared site folder.
            board_path: The shared board file.

        Raises:
            KeyError: If a worker record has no "key" or "slug" entry.
        """
        self.language = language
        self.workers = workers
        self.site_dir = site_dir
        self.board_path = board_path
        self.by_key = {worker['key']: worker for worker in workers}
        self.by_slug = {worker["slug"]: worker for worker in workers}
        self.objectives: dict[str, str] = {} # slug -> the objective the orchestrator assigned
        self.registry: dict[int, dict] = {} # goal id -> worker (with its objective), colors the live board
        self.pending: list[subprocess.Popen] = [] # launched but not yet waited for
        self.fixed: set[str] = set() # slugs that have had their one fix
    
    def _built(self, slug: str) -> bool:
        """
        Whether a worker's game is complete on disk.

        Args:
            slug: The worker's folder name.

        Returns:
            True if all three game files exist and are non-empty.

        Raises:
            OSError: If a file's size cannot be read.
        """
        return is_built(self.site_dir / slug)
    
    def status(self) -> str:
        """
        Summarise the team: each builder, its objective once assigned, and whether its game is built.

        Returns:
            A multi-line "Team status" text the orchestrator reads after waiting.

        Raises:
            OSError: If a game file's size cannot be read.
        """
        lines = []
        for worker in self.workers:
            slug = worker["slug"]
            objective = self.objectives.get(slug)
            who = f"{worker["name"]} ({objective})" if objective else worker["name"]
            lines.append(f"  {who} [{slug}/]: {'built' if self._built(slug) else 'NOT built'}")
        return "Team status:\n" + "\n".join(lines)
        
    def finished_games(self) -> list[dict]:
        """
        The built games as [{label, slug}], each labelled by the title its builder gave it.

        Returns:
            A list of {"label", "slug"} dictionaries, one per built game: its title and the folder to link.

        Raises:
            OSError: If a game file's size cannot be read.
            UnicodeDecodeError: If a built game.html is not valid UTF-8.
        """
        games = []
        for worker in self.workers:
            slug = worker["slug"]
            if not self._built(slug):
                continue
            label = _read_title(self.site_dir / slug / "game.html") or self.objectives.get(slug) or worker["name"]
            games.append({
                "label": label, 
                "slug": slug
            })
        return games

def make_tools(team: Team) -> list:
    """
    Build the orchestrator agent's tools as closures over the team state. These would be simple async functions without any decorator for the orchestrator to get things done.

    Args:
        team: The shared Team state the tools read and update.

    Returns:
        The six tools handed to the orchestrator agent: author_style, launch_worker, wait_for_team, test_game,
        relaunch_worker and build_hub.
    """
    async def author_style() -> str:
        """
        Author the arcade's shared house style (common.css). Do this once, before the builders start.

        Returns:
            A confirmation that common.css was written.

        Raises:
            OSError: If the site folder or common.css cannot be written.
        """
        await css_agent.author_style(team.language, team.site_dir)
        return "Authored common.css, the shared house style for the arcade."

    def launch_worker(framework: str, objective:str) -> str:
        """
        Start one framework's builder, giving it a learning objective to build a game for.
        The builder invents the game itself. Returns immediately; it works in the background. 
        Start all your builders, then call wait_for_team.

        Args:
            framework: the framework key of the builder to start, one of those listed in your team.
            objective: the learning objective this builder's game teaches, e.g. "greetings" or "common verbs".
                        Give each builder a different one.

        Returns:
            A confirmation that the builder was launched, or a message saying why it was not (unknown framework,
            or already started).

        Raises:
            OSError: If the game folder cannot be created or the worker process cannot be started.
            sqlite3.Error: If the goal cannot be written to the shared board.
        """

        worker = team.by_key.get(framework)
        if worker is None: 
            return f"NObuilder named '{framework}'. Your team is: {', '.join(team.by_key)}."
        slug = worker["slug"]
        if slug in team.objectives:
            return f"{worker['name']} is already building a game on {team.objectives[slug]}."
        team.objectives[slug] = objective
        (team.site_dir / slug).mkdir(parents=True, exist_ok=True)
        task = prompts.GAME_TASK.format(language=team.language, objective=objective, slug=slug)
        goal_id = board.add_goal(task)
        team.registry[goal_id] = {**worker, "objective": objective}
        team.pending.append(_launch(goal_id, worker, team.board_path))
        return f"Launched {worker['name']} to invent a {team.language} game teaching {objective} (folder {slug}/)."

    async def wait_for_team() -> str:
        """
        Wait until every builder you have started has finished, watching the shared board fill in while they work.
        
        Returns:
            The team status: each builder and whether its game is built.

        Raises:
            sqlite3.Error: If the shared board cannot be read while the live view is drawn.
        """
        procs = team.pending
        team.pending = []
        if not procs:
            return team.status()
        started = time.monotonic()
        stopped = False
        with Live(live_board.render(team.registry), console=live_board.console, refresh_per_second=8) as live:
            while any(p.poll() is None for p in procs):
                live.update(live_board.render(team.registry))
                if not stopped and time.monotonic() - started > WORKER_TIMEOUT:
                    for p in procs:
                        if p.poll() is None:
                            _terminate(p)
                    stopped = True
                await asyncio.sleep(0.15)
            live.update(live_board.render(team.registry))
        return team.status()

    async def test_game(slug: str) -> str:
        """
        Open one finished game in a real browser and play it to judge whether it works.
        Watch the browser to see the game being played.

        Args:
            slug: the builder's folder name, which is its framework key, e.g. strands.

        Returns:
            A message saying whether the game WORKS or is BROKEN with a one-sentence note, or why it could not be checked.

        Raises:
            None: any error during the check is caught and returned as a message, so the orchestrator can carry on.
        """

        worker = team.by_slug.get(slug)
        if worker is None:
            return f"No game in folder '{slug}'. Folders: {', '.join(team.by_slug)}."
        if not team._built(slug):
            missing = [f for f in GAME_FILES if not (team.site_dir / slug / f).exists() or not (team.site_dir / slug / f).stat().st_size]
            return f"{slug} is not built yet (missing or empty: {', '.join(missing)}). Wait for team, or fix it."
        uri = (team.site_dir / slug / "game.html").resolve().as_uri()
        live_board.console.print(f"Playing {worker['name']}'s game to check it", style = worker['colour'])
        try:
            verdict = await asyncio.wait_for(
                qa_agent.judge_game(team.language, team.objectives.get(slug, ""), uri),
                timeout=QA_TIMEOUT,
            )
        except Exception as exc:
            live_board.console.print(f" could not finish checking {worker['name']} ({type(exc).__name__})", style="dim")
            return f"Could not finish checking {slug} ({type(exc).__name__}); leave it as built."
        if not verdict:
            live_board.console.print(f" could not play {worker['name']} (browser unavailable)", style = "dim")
            return f"Could not play {slug} (the browser may be unavailable); leave it as built."
        works = bool(verdict.get("works"))
        note = verdict.get("note", "")
        live_board.console.print(f" {worker['name']}: {'WORKS' if works else 'BROKEN'}. {note}", style="green" if works else "red")
        return f"{slug}: {'WORKS' if works else 'BROKEN'}. {note}"

    def relaunch_worker(framework: str, problem: str) -> str:
        """
        Send a framework's builder back to fix its game, once. Returns immediately;
        call wait_for_team afterwards. Each game gets at most one fix attempt.

        Args:
            framework: the framework key whose game is broken.
            problem: one short sentence describing what is broken.

        Returns:
            A confirmation that the builder was sent back, or a message saying why it was not (unknown framework, or its
            one fix was already used).

        Raises:
            OSError: If the worker process cannot be started.
            sqlite3.Error: If the fix task cannot be written to the shared board.
        """

        worker = team.by_key.get(framework)
        if worker is None:
            return f"No builder named '{framework}'."
        slug = worker['slug']
        if slug in team.fixed:
            return f"{worker['name']} has already had its one fix; leaving its game as is."
        team.fixed.add(slug)
        objective = team.objectives.get(slug,"")
        text = prompts.FIX_TASK.format(language=team.language, slug=slug, objective=objective, symptom=problem)
        goal_id = board.add_goal(text)
        team.registry[goal_id] = {**worker, "objective": objective}
        team.pending.append(_launch(goal_id, worker, team.board_path))
        return f"Sent {worker['name']} back to fix its game (folder {slug}/)."

    async def build_hub() -> str:
        """
        Author the themed home page (index.html) linking every finished game. Call 
        this once, after the games are built and checked.

        Returns:
            A confirmation naming the games linked from index.html, or a note that there are none to link yet.

        Raises:
            OSError: If index.html cannot be written.
        """
        games = team.finished_games()
        if not games:
            return "No finished games to link yet; build some first."
        await css_agent.build_hub(team.language, games, team.site_dir)
        return f"Authored index.html linking {len(games)} game(s): {', '.join(g['label'] for g in games)}."

    return [author_style, launch_worker, wait_for_team, test_game, relaunch_worker, build_hub]
        
def _build_agent(team: Team) -> LlmAgent:
    """
    Build the orchestrator agent from its prompt, the team roster and its tools.

    Args:
        team: The shared Team state.

    Returns:
        google.adk.agents.LlmAgent: The orchestrator agent.

    Raises:
        KeyError: If the prompt template expects a field that is not supplied.
        ImportError: If google-adk or litellm is not installed.
    """

    team_lines = "\n".join(
        f"- {w['name']} (framework key: {w['key']}, folder: {w['slug']}/)"
        for w in team.workers
    )
    instruction = prompts.ORCHESTRATOR_PROMPT.format(language=team.language, team=team_lines)
    return LlmAgent(
        name="orchestrator",
        model=config.adk_model(), 
        instruction=instruction, 
        tools=make_tools(team),
    )

async def _run(team: Team) -> None:
    """
    Run the orchestrator agent to completion, stopping cleanly on a model error or when its turn budget runs out.

    Args:
        team: The shared Team state.

    Returns:
        None

    Raises:
        None: a model or network error stops the run with a printed note instead, so the safety net can finish the site.
    """
    runner = InMemoryRunner(agent = _build_agent(team), app_name=_APP)
    try:
        session = await runner.session_service.create_session(app_name=_APP, user_id="orchestrator")
        async for event in runner.run_async(
            user_id="orchestrator",
            session_id=session.id,
            new_message=types.UserContent(
                "Design and build the arcade with your team: give each builder an objective, get the games "
                "built and working, then assemble the home page."
            ),run_config=RunConfig(max_llm_calls=_MAX_TURNS),
            ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text and part.text.strip():
                        live_board.console.print(part.text.strip(), style="dim italic")
    except LlmCallsLimitExceededError:
        # The orchestrator used its whole turn budget. Stop cleanly and let the safety net below finish the site; the games it did build are still on disk.
        print(f"\n NOTE: the orchestrator reached its {_MAX_TURNS}-step budget; wrapping up with what is built.")
    except Exception as exc:
        # A transient model or network error (a DNS blip, a 5xx from the API) on the orchestrator's own call would otherwise crash the whole run with a traceback.  
        # The game are already built on disk, so stop cleanly and let the safety net below finish the hub. The type is printed so a real fault is still visible.
        print(f"\n NOTE: the orchestrator stopped early after an error ({type(exc).__name__}: {str(exc)[:300]}); wrapping up what is built.")
    finally:
        try:
            await runner.close()
        except Exception:
            pass

def _ensure_site(team: Team) -> None:
    """
    A non-LLM safety net so the site always has a look and a front door, even if the orchestrator stopped before authoring them. Only fills in what is missing.

    Args:
        team: The shared Team state.

    Returns:
        None

    Raises:
        OSError: If the template files cannot be written.
    """
    if not (team.site_dir / "common.css").exists():
        css_agent.write_template_style(team.site_dir)
    if not (team.site_dir / "index.html").exists():
        css_agent.write_template_hub(team.language, team.finished_games(), team.site_dir)
        print(" NOTE: the orchestrator did not author index.html; wrote the plain template instead.")

def run(language: str, workers: list[dict], site_dir: Path, board_path: Path) -> Team:
    """
    Reset the shared board, then let the orchestrator agent build and check the arcade.

    Args:
        language: The language the arcade teaches.
        workers: The worker manifest records returned by catalog.discover().
        site_dir: The shared site folder every game is built into.
        board_path: The shared board file.

    Returns:
        Team: The final team state, from which the final status can be read.

    Raises:
        OSError: If the site folder cannot be created.
        sqlite3.Error: If the shared board cannot be reset.
    """
    site_dir.mkdir(parents=True, exist_ok=True)
    board.reset_board()
    team = Team(language, workers, site_dir, board_path)
    asyncio.run(_run(team))
    _ensure_site(team)
    return team



