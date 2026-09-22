"""Tools for the Sidekick: a mix of MCP servers, ready-made LangChain tools and our own."""

import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path

import requests
import wikipedia
from dotenv import load_dotenv
from langchain_community.tools import GoogleSerperRun, WikipediaQueryRun
from langchain_community.utilities import GoogleSerperAPIWrapper, WikipediaAPIWrapper
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from web_tools import ALL_TOOLS, WIKIPEDIA_TOOLS

import random
from typing import List, Optional, Annotated
from typing_extensions import TypedDict
from IPython.display import Markdown, display, Image
import gradio as gr
import urllib3
import requests
import re
import asyncio
import datetime
import win32com.client
import pythoncom
import subprocess
import time

load_dotenv(override=True)


## setting up Serpapi as websearch tool for LLM

def list_serpapi_results(response: dict, max_results: int | None = None) -> list[dict]:
    """Print and return readable search results from a SerpApi response.

    The returned list contains only the fields normally needed by an agent:
    title, link, displayed_link, snippet, and position.
    """
    if not isinstance(response, dict):
        raise TypeError("response must be the dictionary returned by search_serpapi_debug")

    if response.get("error"):
        print(f"SerpApi error: {response['error']}")
        return []

    organic_results = response.get("organic_results", [])
    if not isinstance(organic_results, list):
        print("No readable organic_results list was found in the API response.")
        return []

    results = []
    print("\n ###########-printing SERP api response-############")
    for result in organic_results[:max_results]:
        if not isinstance(result, dict):
            continue

        item = {
            "position": result.get("position"),
            "title": result.get("title", "Untitled"),
            "link": result.get("link", ""),
            "displayed_link": result.get("displayed_link", ""),
            "snippet": result.get("snippet", ""),
        }
        results.append(item)

        print(f"{item['position']}. {item['title']}")
        print(f"   URL: {item['link']}")
        if item["snippet"]:
            print(f"   {item['snippet']}")
        print()

    if not results:
        print("The API response contains no organic search results.")

    return results

# setting up a google search api tool
@tool
def search_serpapi_tool(query: str) -> list[dict]:
    """Performs a search using SerpApi and prints raw response metadata if JSON parsing fails.
    Then print and return readable search results from a SerpApi response.
    """
    print("\n******************* SERP-API-TOOL-CALLED ************************\n")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = "https://serpapi.com/search"
    SERP_API_KEY=os.getenv("SERP_API_KEY")
    params = {"engine": "google", "q": query, "api_key": SERP_API_KEY, "num": 10}

    try:
        response = requests.get(url, params=params, verify=False)

        # 1. Print status code to see what the server actually answered
        print(f"[DEBUG] HTTP Status Code: {response.status_code}")

        # 2. Check if the response header is actually JSON
        content_type = response.headers.get("Content-Type", "")
        print(f"[DEBUG] Content-Type Header: {content_type}")

        # If it's an error page or HTML block, print the snippet to read the error
        if "application/json" not in content_type:
            print("[DEBUG] Received unexpected non-JSON body:")
            print(response.text[:500])  # Prints first 500 characters
            return {}

        return list_serpapi_results(response.json(), max_results=10) # List the results returned by the previous SerpApi call.
        
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the SerpApi call: {e}")
        return {}


## Setting up email sending method/tool 
# define a method/function to send email via Outlook COM
@tool
def send_email_tool( 
    subject: str,
    body: str
    ) -> bool:
    """Send an email using the local Outlook desktop client."""
    # Normalize recipient to a semicolon-separated string (Outlook format)
    recipient = os.getenv("EMAIL_ADDRESS_TO")
    recipients = []
    if isinstance(recipient, list):
        recipients = [r.strip() for r in recipient if r.strip()]
    elif isinstance(recipient, str):
        if "," in recipient:
            recipients = [r.strip() for r in recipient.split(",") if r.strip()]
        else:
            recipients = [recipient.strip()]
    
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email.strip()) is not None

    # Validate all recipients
    invalid_recipients = [r for r in recipients if not validate_email(r)]
    if invalid_recipients:
        print(f"Error: Invalid email format(s): {invalid_recipients}")
        return False
    
    recipient_str = "; ".join(recipients)
    
    if not recipient_str:
        print("Error: No recipients specified. Email not sent.")
        return False

    if body is None:
        body = "Hello there!! "

    print(f"\nSending email to {recipient_str} with subject '{subject}'...")

    # Ensure COM is initialized for the current thread (agent tool calls may run in worker threads).
    pythoncom.CoInitialize()
    try:
        # Connect to Outlook, launch it if not running
        outlook = None
        for attempt in range(5):
            try:
                outlook = win32com.client.Dispatch("Outlook.Application")
                outlook.GetNamespace("MAPI")
                print("Outlook is up & running...")
                break
            except Exception as e:
                if attempt == 0:
                    print("Outlook not running — launching...")
                    for p in [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
                              r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE"]:
                        if os.path.exists(p):
                            subprocess.Popen([p])
                            time.sleep(45)
                            break
                    else:
                        print("Error: Outlook executable not found.")
                        return False
                elif attempt < 4:
                    print(f"Outlook connect attempt {attempt + 1}/5 — waiting...")
                    time.sleep(15)
                else:
                    print(f"Error: Outlook connect failed after 5 attempts: {e}")
                    return False

        try:
            mail = outlook.CreateItem(0)
            mail.To = recipient_str
            mail.Subject = subject
            mail.Body = body

            mail.Send()
            print(f"\nEmail sent successfully to '{recipient_str}' with subject '{subject}'.")
            return True

        except Exception as e:
            print(f"Failed to send email: {e}")
            # Print recipient info for debugging
            print(f"Debug - Recipients used: {repr(recipient_str)}")
            print(f"Debug - Recipient type: {type(recipient_str)}")
            return False
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

## binding the tools with llm
tools = [search_serpapi_tool, send_email_tool]
tools

@tool
def request_human_help(instructions: str) -> str:
    """Ask the user to do something in the browser window that you cannot do yourself,
    such as logging in to a site, passing a captcha, or approving two-factor authentication.
    Explain exactly what you need them to do. The run pauses until they have done it."""
    return "The user says it is done. Continue with the task."


def get_sandbox_tools(sandbox: str) -> list:
    """Create filesystem tools restricted to the Sidekick sandbox directory."""
    sandbox_root = Path(sandbox).resolve()

    def resolve_path(path: str) -> Path:
        candidate = (sandbox_root / path).resolve()
        try:
            candidate.relative_to(sandbox_root)
        except ValueError as error:
            raise ValueError("Paths must stay within the sandbox directory.") from error
        return candidate

    @tool
    def list_sandbox_files(path: str = ".") -> list[str]:
        """List files and folders inside the sandbox directory."""
        target = resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Sandbox path does not exist: {path}")
        if target.is_file():
            return [str(target.relative_to(sandbox_root))]
        return sorted(str(item.relative_to(sandbox_root)) for item in target.rglob("*"))

    @tool
    def read_sandbox_file(path: str) -> str:
        """Read a UTF-8 text file from the sandbox directory."""
        target = resolve_path(path)
        if not target.is_file():
            raise FileNotFoundError(f"Sandbox file does not exist: {path}")
        return target.read_text(encoding="utf-8")

    @tool
    def write_sandbox_file(path: str, content: str) -> str:
        """Write UTF-8 text to a file in the sandbox directory."""
        target = resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target.relative_to(sandbox_root)}"

    return [list_sandbox_files, read_sandbox_file, write_sandbox_file]


def mcp_connections(sandbox: str) -> dict:
    """The MCP servers the Sidekick uses."""
    return {
        "playwright": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest", "--isolated"],
        },
    }


class McpSessions:
    """Holds persistent MCP sessions open so the browser keeps its state between tool calls.

    The stdio transport must be opened and closed from the same asyncio task, so one
    background task owns the sessions: it opens them, waits, and unwinds them when stop()
    is called. Stopping shuts down the servers, and you will see the browser close.
    """

    def __init__(self, connections: dict):
        self.connections = connections
        self.tools = []
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._task = None

    async def _run(self):
        client = MultiServerMCPClient(self.connections)
        async with AsyncExitStack() as stack:
            for name in self.connections:
                session = await stack.enter_async_context(client.session(name))
                self.tools += await load_mcp_tools(session, server_name=name)
            self._ready.set()
            await self._stop.wait()

    async def start(self) -> list:
        self._task = asyncio.create_task(self._run())
        ready = asyncio.create_task(self._ready.wait())
        await asyncio.wait([ready, self._task], return_when=asyncio.FIRST_COMPLETED)
        ready.cancel()
        if self._task.done():
            self._task.result()  # the servers failed to start; raise the real error
        return self.tools

    def stop(self):
        self._stop.set()


async def get_all_tools(sandbox: str):
    """Return the full tool list (our tools plus the MCP server tools) and the session holder."""
    sessions = McpSessions(mcp_connections(sandbox))
    mcp_tools = await sessions.start()
    our_tools = [request_human_help, search_serpapi_tool, send_email_tool]
    our_tools += get_sandbox_tools(sandbox) + WIKIPEDIA_TOOLS
    return our_tools + mcp_tools, sessions