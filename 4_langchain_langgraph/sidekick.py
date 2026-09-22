"""
The Sidekick: a create_agent (Layer 3). Around it we run our own loop that checks
the worker's answer against the user's success criteria, and either accepts it, sends it
back for another attempt, or returns to the user with a question. Middleware gives the 
worker a plan it shares with the UI, guardrails for PII and runaway costs, and a pause
for human approval before sensitive actions.
"""

import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    PIIMiddleware,
    TodoListMiddleware
)
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from sidekick_tools import get_all_tools

load_dotenv(override=True)
# loading environment variables
# From OpenAI
AZURE_OPENAI_API_KEY= os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_MODEL_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_GPT_41 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_41")
AZURE_OPENAI_DEPLOYMENT_GPT_54_mini = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_54_mini")
AZURE_OPENAI_DEPLOYMENT_GPT_55 = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_55")
AZURE_OPENAI_DEPLOYMENT_GPT_4O_mini = os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT_4O_mini")
# From Anthropic
AZURE_CLAUDE_DEPLOYMENT_OPUS_48=os.getenv("AZURE_CLAUDE_DEPLOYMENT_OPUS_48")
AZURE_CLAUDE_ENDPOINT=os.getenv("AZURE_CLAUDE_ENDPOINT")
AZURE_CLAUDE_API_KEY=os.getenv("AZURE_CLAUDE_API_KEY")
# setting up tavily api key
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")
SERP_API_KEY=os.getenv("SERP_API_KEY")
# loading email address
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS_TO")

# setting up local variables related to folder paths
HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.abspath("sandbox")
MAX_ATTEMPTS = 3

# setting up LLM variable
## Setting up the llm from Azure Foundry
model = AzureChatOpenAI(
    api_key = AZURE_OPENAI_API_KEY,
    azure_endpoint = AZURE_OPENAI_ENDPOINT,
    azure_deployment = AZURE_OPENAI_DEPLOYMENT_GPT_54_mini,
    api_version = AZURE_OPENAI_API_VERSION
)

## create a pydantic subclass for validating the LLm results
class EvaluatorOutput(BaseModel):
    feedback: str = Field(
        description="Feedback on the assistant's response"
    )
    success_criteria_met: bool = Field(
        description="Whether the success criteria have been met"
    )
    user_input_needed: bool = Field(
        description="True if assistant has a question, needs clarification, or is stuck and needs the user to answer something."
    )

WORKER_PROMPT = """You are Sidekick, a capable personal assistant who completes tasks for the user.
You have a real web browser, a sandbox filesystem, web search, Wikipedia, and the ability to send push notifications.
When you use the browser, navigate to a page and read it with a snapshot rather than clicking around unnecessarily.
Dismiss cookie banners and popups yourself by clicking in the browser. If you reach something only a human can do,
like logging in, a captcha, or two-factor authentication, use the request_human_help tool to tell the user exactly
what to do in your browser window, then carry on once they have done it.
For flight searches, use Google Flights in your browser: go straight to https://www.google.com/travel/flights?q=...
with a natural language query like "flights from Bangalore to Chandigarh leaving 14 October returning 21 October".
Keep working on the task until the success criteria are met, or until you genuinely need to ask the user a question.
If you have a question, ask it plainly. When you are finished, give your final answer clearly,
saying what you did, what you produced, and what you found."""

## let's create a custom middleware
class TolerateToolError(AgentMiddleware):
    """Hand tool failure back to the model as a message so it can recover, rather than
    crashing the run. Tools that touch the outside world, like a browser, fail now and then.
    """
    async def awrap_tool_call(self, request, handler):
        try: 
            return await handler(request)
        except Exception as error:
            return ToolMessage(
                content = f"That tool call failed: {error}. Try another approach.",
                tool_call_id = request.tool_call['id']
            )

## create a class for running our sidekick
class Sidekick:
    def __init__(self): # define a constructor
        self.sidekick_id = str(uuid.uuid4())
        self.memory = InMemorySaver()
        self.tools = None
        self.sessions = None
        self.worker = None
        self.evaluator = None
        self.task = ""
        self.success_criteria = ""
        self.attempts = 0
        self.paused = False
        self.pending_actions = 0
        self.todos = []

    async def setup(self): # function to setup variables & models
        os.makedirs(SANDBOX, exist_ok=True)
        self.tools, self.sessions = await get_all_tools(SANDBOX)
        self.worker = create_agent(
            model = model,
            tools = self.tools,
            system_prompt=f"{WORKER_PROMPT}\n Today's date is {datetime.now(): %A %d %B %Y}.",
            middleware=[
                TolerateToolError(),
                TodoListMiddleware(),
                PIIMiddleware("email"),
                PIIMiddleware("credit_card", apply_to_tool_results=True),
                ModelCallLimitMiddleware(run_limit=30),
                HumanInTheLoopMiddleware(
                    interrupt_on = {
                        "send_email_tool": True, 
                        "request_human_help": True
                    }
                )
            ],
            checkpointer = self.memory
        )
        self.evaluator = model.with_structured_output(EvaluatorOutput)

    ## function to evaluate the LLM model results
    async def evaluate(
        self, 
        message: str, 
        success_criteria: str, 
        last_reply: str,
        tools_used: list[str]) -> EvaluatorOutput:
        prompt = f"""You decide whether an assistant has met the success criteria for a task.
        The user's request was:
        {message}

        The success criteria are:
        {success_criteria}

        The tools the assistant called while working, in order:
        {", ".join(tools_used) or "none"}

        The assistant's most recent reply was:
        {last_reply}

        Decide whether the success criteria are met, using the tool calls as evidence of what was acutally done.
        Also decide whether the assistant needs more input from the user, either because it asked a question, 
        needs clarification, or seems stuck. Give brief, concrete feedback.
        """

        return await self.evaluator.ainvoke(prompt)

    ## let's make a function to run the agent
    async def run_turn(self, message: str, success_criteria: str, history: list) -> list:
        """One turn of conversation: the worker attempts the task and the evaluator checks it, 
        retrying with feedback up to MAX_ATTEMPTS. If the worker pauses for approval, this returns
        straight away with paused set, and resume() continues the same turn."""
        self.task = message,
        self.success_criteria = success_criteria or "The answer should be clear, correct and complete"
        self.attempts = 0
        self.todos = []
        payload = {
            "messages":[
                {
                    "role": "user",
                    "content": f"{message} \n\nThe success criteria for this task are: {self.success_criteria}"
                }
            ]
        }
        return await self._advance(payload, history + [{"role": "user", "content": message}])

    # function to resume the agent 
    async def resume(self, history: str) -> list:
        """Approve the actions the worker paused on, and continue the turn."""
        payload = Command(
            resume = {
                "decisions":[
                    {
                        "type": "approve"
                    }
                ] * self.pending_actions
            }
        )
        return await self._advance(payload, history)

    # function to make first callto agent, and interrupt/resume
    async def _advance(self, payload, history: list) -> list:
        config = {
            "configurable":{
                "thread_id": self.sidekick_id
            }
        }
        while True:
            result=None
            async for result in self.worker.astream(payload, config=config, stream_mode="values"):
                self.todos = result.get("todos", self.todos)

            if "__interrupt__" in result:
                actions = result["__interrupt__"][0].value['action_requests']
                self.paused = True
                self.pending_actions = len(actions)
                described = "\n".join(action["description"] for action in actions)
                return history + [{
                    "role": "assistant",
                    "content": f"Waiting for your approval: \n{described}"
                }]

            self.paused = False
            reply = result['messages'][-1].content
            tools_used = [
                call['name'] for m in result['messages'] for call in (getattr(m,"tool_calls", None) or [])
            ]
            self.attempts += 1
            verdict = await self.evaluate(self.task, self.success_criteria, reply, tools_used)
            if verdict.success_criteria_met or verdict.user_input_needed or self.attempts >= MAX_ATTEMPTS:
                return history + [
                    {
                        "role": "assistant", 
                        "content": reply
                    },
                    {
                        "role": "assistant",
                        "content": f"Evaluator: {verdict.feedback}"
                    }
                ]
            payload = {
                "messages":[
                    {
                        "role": "user",
                        "content": f"Your last response did not meet the success criteria."
                        f"Here is the feedback: {verdict.feedback}. Please keep working and address it."
                    }
                ]
            }

    def cleanup(self):
        """Shutdown the MCP servers; the browser window closes."""
        if self.sessions:
            self.sessions.stop()
