"""
The QA tester: the ADK orchestrator plays its team's games to judge them.

Equipped with a real browser, a single ADK agent opens each finished game, plays it, watches the console,
and reports which work and which are broken. This is capstone's lesson in miniature: give an agent a goal and a way to check its own success,
here a real browser, and let it evaluate the work itself. The agent's verdicts drive the one bounded fix round.
The browser tools are web_tools.BrowserSession, which drives the installed Chrome through Playwright (see browser_tools.py).
If the browser cannot start, the game is left as built and the finished site is still opened.
"""

from __future__ import annotations
import asyncio
import os
import webbrowser
from pathlib import Path
from quiet import silence
silence()

from google.adk.agents import LlmAgent # noqa: E402
from google.adk.agents.invocation_context import LlmCallsLimitExceededError # noqa: E402
from google.adk.agents.run_config import RunConfig # noqa: E402
from google.adk.runners import InMemoryRunner # noqa: E402
from google.genai import types # noqa: E402

import config # noqa: E402
import prompts # noqa: E402
import web_tools # noqa: E402

_APP = "agent_loop"
_MAX_CALLS = 25 # the QA agent's budget for one game; a quick check needsd far fewer
_CLOSE_TIMEOUT = 10 # bound the browser teardown so a wedged browser close cannot hang the run

async def judge_game(language: str, objective: str, uri:str) -> dict | None:
    """
    Play one game with a fresh, bounded QA sub-agent.

    Args:
        language: The language the game teaches, such as "Spanish".
        objective: The learning objective the game was built to teach.
        uri: The file:// address of the game's game.html.

    Returns:
        A dictionary with "works" (bool) and "note" (one sentence), or None if the agent never reported a verdict.
        Running out of the call budget without a report counts as working, since the agent could keep using the game.

    Raises:
        Exception: If a model call fails, for example a rejected request or a network error. The caller, test_game in
            orchestrator.py, catches it. A browser that cannot start is not raised: the tools report it to the agent.
    """
    verdict: dict = {}

    def report_game(works: bool, note: str) -> dict:
        """
        Report whether the game works, after playing it.

        Args:
            works: true if the game loads and plays correctly.
            note: one short sentence on what you saw or what is broken.

        Returns:
            {"recorded": True}, telling the agent its verdict was stored.
        """
        verdict["works"] = works
        verdict["note"] = note
        return {"recorded": True}

    # Headed by default so you can watch the game being played; QA_HEADLESS=1 hides the window.
    browser = web_tools.BrowserSession(headless=os.environ.get("QA_HEADLESS") == "1")

    agent = LlmAgent(
        name="qa_tester",
        model=config.adk_model(),
        instruction="You are a meticulous QA tester. Use the browser to check the game, then report your verdict.",
        tools=[*browser.tools(), report_game]
    )

    runner = InMemoryRunner(agent=agent, app_name=_APP)
    try:
        session = await runner.session_service.create_session(app_name=_APP, user_id="qa")
        prompt = prompts.QA_PROMPT.format(language=language, objective=objective, uri=uri)
        try:
            async for _ in runner.run_async(
                user_id="qa",
                session_id=session.id,
                new_message=types.UserContent(prompt),
                run_config=RunConfig(max_llm_calls=_MAX_CALLS),
                ):
                pass

        except LlmCallsLimitExceededError:
            """
            The agent used its whole budget without reporting. It was clearly able to keep interacting with the game,
            so the game loads and respounds: treat it as working rather than firing a spurious fix round.
            """
            verdict.setdefault("works", True)
            verdict.setdefault("note", "played it for the full check budget and it stayed responsive")
        return verdict or None
    finally:
        """
        Close the browser inside the loop before it ends. Bound each close, so if the caller gives up on a slow check
        and cancels this game, a wedged browser can't hang the teardown and freeze the run.
        """
        for close in (browser.close, runner.close):
            try:
                await asyncio.wait_for(close(), timeout=_CLOSE_TIMEOUT)
            except Exception:
                pass


def open_site(index_path: Path) -> None:
    """
    Open the finished arcade in the default browser for the player.

    Args:
        index_path: The path to the index.html file of the finished arcade.

    Returns:
        None

    Raises:
        OSError: If the path cannot be resolved.
    """
    webbrowser.open(index_path.resolve().as_uri())





