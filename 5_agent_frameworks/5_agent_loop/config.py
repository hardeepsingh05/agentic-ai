"""
Everything configurable for the agent loop lives here: the Azure OpenAI settings, the deployment each
role uses, the filesystem MCP server address, and one model builder and one filesystem-tool builder
per framework (named after the framework keys in catalog.WORKERS).

The orchestrator (Google ADK) authors the shared look and the hub page; the workers build the games.
To run cheaper, point ORCHESTRATOR_MODEL / WORKER_MODEL at smaller deployments.

Framework imports happen inside the builders, so a worker process only loads the one framework it runs on.

The workers read and write files through filesystem_server.py, which you start in a separate terminal
from this folder, rooted at the shared site folder (PowerShell):

    $env:MCP_ROOT = "<path to>\\5_agent_loop\\site"
    uvicorn filesystem_server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# LiteLLM (used by ADK) otherwise tries to download its price map from GitHub at import, which hangs ~15s when blocked.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

# Azure OpenAI connection, shared by every framework's client.
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION")
# LiteLLM sends gpt-5.4+ tool calls to Azure's Responses API, which needs api-version 2025-03-01-preview or newer.
ADK_API_VERSION = os.environ.get("AZURE_OPENAI_ADK_API_VERSION", "2025-04-01-preview")

# These are Azure deployment names, not model ids. WORKER_MODEL can be overridden by an env var of the same name.
ORCHESTRATOR_MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT_56_SOL")
WORKER_MODEL = os.environ.get("WORKER_MODEL") or os.environ.get("AZURE_OPENAI_DEPLOYMENT_GPT_55")

# Streamable-HTTP endpoint of filesystem_server.py (FastMCP mounts it at /mcp).
FILESYSTEM_MCP_URL = os.environ.get("FILESYSTEM_MCP_URL", "http://127.0.0.1:8000/mcp")
FILESYSTEM_MCP_TIMEOUT = 60  # seconds allowed for the MCP handshake


def check() -> None:
    """
    Stop with a readable message if a required setting is missing from the environment.

    Returns:
        None

    Raises:
        SystemExit: If the Azure key, endpoint or api-version, or the orchestrator or worker deployment name, is not set.
    """
    required = {
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_VERSION": AZURE_OPENAI_API_VERSION,
        "AZURE_OPENAI_DEPLOYMENT_GPT_56_SOL (orchestrator)": ORCHESTRATOR_MODEL,
        "AZURE_OPENAI_DEPLOYMENT_GPT_55 or WORKER_MODEL (workers)": WORKER_MODEL,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit("Missing settings in .env: " + ", ".join(missing))


def azure_client():
    """
    Build the async Azure OpenAI client shared by Strands, Pydantic AI and Agno.

    Returns:
        openai.AsyncAzureOpenAI: A client configured with the Azure endpoint, key and api-version from the environment.

    Raises:
        ImportError: If the openai package is not installed.
        openai.OpenAIError: If no API key is set.
        ValueError: If no Azure endpoint is set.
    """
    from openai import AsyncAzureOpenAI

    return AsyncAzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


# ---- Models: one per framework -------------------------------------------------------------------------------

def adk_model(deployment: str | None = None):
    """
    Build the Google ADK model for the orchestrator, art director and QA tester.

    ADK reaches Azure through LiteLLM's "azure/<deployment>" route, using ADK_API_VERSION rather than the
    shared api-version so tool calls can be served by Azure's Responses API.

    Args:
        deployment: Azure deployment name to use. Defaults to ORCHESTRATOR_MODEL.

    Returns:
        google.adk.models.lite_llm.LiteLlm: A model object to pass to an LlmAgent.

    Raises:
        ImportError: If google-adk or litellm is not installed.
    """
    from google.adk.models.lite_llm import LiteLlm
    import litellm

    litellm.suppress_debug_info = True  # no "Provider List" banner over the live board

    return LiteLlm(
        model=f"azure/{deployment or ORCHESTRATOR_MODEL}",
        api_key=AZURE_OPENAI_API_KEY,
        api_base=AZURE_OPENAI_ENDPOINT,
        api_version=ADK_API_VERSION,
    )


def strands_model(deployment: str | None = None):
    """
    Build the AWS Strands model for the Strands worker.

    Args:
        deployment: Azure deployment name to use. Defaults to WORKER_MODEL.

    Returns:
        strands.models.openai.OpenAIModel: A model backed by the Azure client from azure_client().

    Raises:
        ImportError: If strands-agents is not installed.
        openai.OpenAIError: If no API key is set.
        ValueError: If no Azure endpoint is set.
    """
    from strands.models.openai import OpenAIModel

    return OpenAIModel(model_id=deployment or WORKER_MODEL, client=azure_client())


def pydantic_model(deployment: str | None = None):
    """
    Build the Pydantic AI model for the Pydantic AI worker.

    Args:
        deployment: Azure deployment name to use. Defaults to WORKER_MODEL.

    Returns:
        pydantic_ai.models.openai.OpenAIChatModel: A chat model backed by the Azure client from azure_client().

    Raises:
        ImportError: If pydantic-ai is not installed.
        openai.OpenAIError: If no API key is set.
        ValueError: If no Azure endpoint is set.
    """
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    return OpenAIChatModel(
        model_name=deployment or WORKER_MODEL,
        provider=OpenAIProvider(openai_client=azure_client()),
    )


def maf_client(deployment: str | None = None):
    """
    Build the Microsoft Agent Framework chat client for the MAF worker.

    Args:
        deployment: Azure deployment name to use. Defaults to WORKER_MODEL.

    Returns:
        agent_framework.openai.OpenAIChatClient: A client routed to the Azure endpoint.

    Raises:
        ImportError: If agent-framework is not installed.
        agent_framework.exceptions.SettingNotFoundError: If MAF cannot find a model, endpoint or key.
    """
    # azure_endpoint routes to Azure; no api_version because MAF's Responses client uses the /openai/v1 endpoint, which rejects dated versions.
    from agent_framework.openai import OpenAIChatClient

    return OpenAIChatClient(
        model=deployment or WORKER_MODEL,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
    )


def agno_model(deployment: str | None = None):
    """
    Build the Agno model for the Agno worker.

    Args:
        deployment: Azure deployment name to use. Defaults to WORKER_MODEL.

    Returns:
        agno.models.openai.OpenAIChat: A chat model backed by the Azure client from azure_client().

    Raises:
        ImportError: If agno is not installed.
        openai.OpenAIError: If no API key is set.
        ValueError: If no Azure endpoint is set.
    """
    from agno.models.openai import OpenAIChat

    return OpenAIChat(id=deployment or WORKER_MODEL, async_client=azure_client())


# ---- Filesystem MCP tools: one per framework, all pointing at filesystem_server.py ----------------------------

def strands_filesystem():
    """
    Build the Strands MCP client for filesystem_server.py.

    The connection is opened lazily, when the client is first used as an agent tool.

    Returns:
        strands.tools.mcp.MCPClient: A client over the server's streamable-HTTP endpoint.

    Raises:
        ImportError: If strands-agents or mcp is not installed.
    """
    from mcp.client.streamable_http import streamable_http_client
    from strands.tools.mcp import MCPClient

    return MCPClient(
        lambda: streamable_http_client(FILESYSTEM_MCP_URL),
        startup_timeout=FILESYSTEM_MCP_TIMEOUT,
    )


def pydantic_filesystem():
    """
    Build the Pydantic AI MCP toolset for filesystem_server.py.

    The connection is opened when the agent using it is entered (async with agent).

    Returns:
        pydantic_ai.mcp.MCPToolset: A toolset over the server's streamable-HTTP endpoint.

    Raises:
        ImportError: If pydantic-ai is not installed.
    """
    from pydantic_ai.mcp import MCPToolset

    return MCPToolset(FILESYSTEM_MCP_URL, init_timeout=FILESYSTEM_MCP_TIMEOUT)


async def maf_filesystem() -> list:
    """
    The filesystem server's tools as MAF function tools, found by asking the server what it offers.

    MAF's own MCP client reads mcp 1.x field names (McpError, inputSchema, ...) that mcp 2.x renamed, so
    the tools are listed and called through fastmcp instead. Each call opens a short session of its own.

    Returns:
        A list of agent_framework.FunctionTool objects, one per tool the server exposes.

    Raises:
        ImportError: If agent-framework or fastmcp is not installed.
        RuntimeError: If the server at FILESYSTEM_MCP_URL cannot be reached.
    """
    from agent_framework import FunctionTool
    from fastmcp import Client

    async with Client(FILESYSTEM_MCP_URL) as client:
        server_tools = await client.list_tools()

    def bridge(tool_name: str):
        """
        Wrap one server tool in an async function that calls it through fastmcp.

        Args:
            tool_name: Name of the tool on the filesystem server.

        Returns:
            An async function taking the tool's arguments as keyword arguments and returning its text output.
        """
        async def call(**arguments):
            """
            Call the server tool with the arguments the model chose.

            Args:
                **arguments: The tool's arguments, as keyword arguments.

            Returns:
                The tool's text output, with several text blocks joined by newlines.

            Raises:
                RuntimeError: If the server cannot be reached.
                fastmcp.exceptions.ToolError: If the tool reports an error, such as a path outside the sandbox.
            """
            async with Client(FILESYSTEM_MCP_URL) as client:
                result = await client.call_tool(tool_name, arguments)
            return "\n".join(block.text for block in result.content if hasattr(block, "text"))

        return call

    return [
        FunctionTool(
            name=tool.name,
            description=tool.description or "",
            func=bridge(tool.name),
            input_model=tool.inputSchema,
        )
        for tool in server_tools
    ]


def agno_filesystem():
    """
    Build the Agno MCP tools for filesystem_server.py.

    The connection is opened when the object is entered (async with).

    Returns:
        agno.tools.mcp.MCPTools: Tools over the server's streamable-HTTP endpoint.

    Raises:
        ImportError: If agno is not installed.
    """
    from agno.tools.mcp import MCPTools

    return MCPTools(
        transport="streamable-http",
        url=FILESYSTEM_MCP_URL,
        timeout_seconds=FILESYSTEM_MCP_TIMEOUT,
    )