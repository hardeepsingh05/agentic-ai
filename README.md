# Agentic Frameworks

Learning labs and working examples for building AI agents with Azure OpenAI, Azure AI Foundry, OpenAI tooling, LangChain/LangGraph, Google ADK, A2A, and MCP.

## Contents

| Directory | Focus |
| --- | --- |
| `1_foundations/` | Introductory notebooks and a Gradio-based digital twin that can use Azure OpenAI, Azure-hosted Anthropic models, and local tools. |
| `2_openai/` | OpenAI SDK notebooks, a message recorder, and an Outlook desktop email tool for Windows. |
| `4_langchain_langgraph/` | LangChain and LangGraph labs, browser/search tools, a slide kit, and the Sidekick agent with guardrails and human approval for sensitive actions. |
| `5_agent_frameworks/1_google_adk_a2a/` | Google ADK and A2A experiments, including a shared SQLite task board and a sandboxed FastMCP filesystem server. |
| `5_agent_frameworks/2_strands_pydantic/` | AWS Strands and Pydantic AI labs on Azure OpenAI with a shared task board and an MCP filesystem server, plus their workers for the agent loop. |
| `5_agent_frameworks/3_maf_agno/` | Microsoft Agent Framework and Agno labs on Azure OpenAI, plus their workers for the agent loop. |
| `5_agent_frameworks/5_agent_loop/` | The capstone: a Google ADK orchestrator leads four framework workers to build a browser-game arcade, checks each game in a real browser, and writes a home page. See its [README](5_agent_frameworks/5_agent_loop/README.md) for the architecture and how to run it. |
| `.env.example` | Template listing every setting; copy it to `.env`, which is git-ignored. |
| `requirements.txt` | Python packages used across the exercises. |

## Setup

1. Use Python 3.11 or later (the agent loop was tested on Python 3.12).
2. Install the dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Copy the environment template and fill in the values needed for the lab you want to run:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Open a lab notebook in VS Code or Jupyter, select the Python kernel where the dependencies were installed, and run its cells in order.

## Configuration

The examples load `.env` with `python-dotenv`. Keep secrets only in `.env`; do not commit that file.

`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, and the relevant deployment name are required for the Azure OpenAI examples. The digital twin can additionally use the Azure AI Foundry Anthropic settings. Search-enabled agent examples may need Tavily or Serper credentials. The Outlook email tool requires the Windows Outlook desktop app and `EMAIL_ADDRESS_TO`.

`BOARD_PATH` and `MCP_ROOT` are optional overrides for the Google ADK/A2A SQLite task board and MCP filesystem-server sandbox respectively.

The agent loop (`5_agent_frameworks/5_agent_loop/`) additionally needs `AZURE_OPENAI_DEPLOYMENT_GPT_56_SOL` for the orchestrator and either `AZURE_OPENAI_DEPLOYMENT_GPT_55` or `WORKER_MODEL` for the workers. Its optional settings (`AZURE_OPENAI_ADK_API_VERSION`, `FILESYSTEM_MCP_URL`, `QA_HEADLESS`, `WORKER_TIMEOUT_S`, `QA_TIMEOUT_S`) are described in its README and listed in `.env.example`. All of its model and tool configuration lives in `5_agent_frameworks/5_agent_loop/config.py`.

## Running Selected Examples

- Launch the digital twin from its directory:

  ```powershell
  Set-Location 1_foundations/digital_twin
  python app.py
  ```

- Run the Sidekick from `4_langchain_langgraph/` through its associated notebook or Python entry point after providing the appropriate Azure OpenAI and search settings.
- Run the Google ADK/A2A labs from `5_agent_frameworks/1_google_adk_a2a/lab.ipynb`. The filesystem server is intended to operate within `MCP_ROOT`.
- Build the language arcade with the agent loop. Start the file server in one terminal and the loop in another, both from `5_agent_frameworks/5_agent_loop/`:

  ```powershell
  # terminal 1: the file server the workers use, rooted at the folder the games are built in
  Set-Location 5_agent_frameworks/5_agent_loop
  $env:MCP_ROOT = "$PWD\site"
  python -m uvicorn filesystem_server:app --host 127.0.0.1 --port 8000

  # terminal 2: the orchestrator and its four workers
  Set-Location 5_agent_frameworks/5_agent_loop
  python agent_loop.py
  ```

  Add `--language French`, `--skip agno`, `--dry-run` or `--no-open` as needed. The finished arcade is written to `5_agent_frameworks/5_agent_loop/site/index.html`.

## Notes

- Some labs call paid external model and search services; review provider pricing and deployment availability first.
- Browser examples may require Playwright browsers to be installed separately:

  ```powershell
  python -m playwright install
  ```
- The Outlook integration uses Windows COM automation and is Windows-specific.
- The agent loop's QA step drives your installed Google Chrome through Playwright, so Chrome must be installed; Playwright's own browsers are not needed for it.

## Dependency notes

- Agno 3 requires `mcp` 2.x and `fastmcp` 4.x, so `requirements.txt` pins `mcp>=2.1.0,<3.0.0` and `fastmcp>=4.0.0,<5.0.0`.
- Some other packages (CrewAI, `langchain-mcp-adapters` and Strands) still declare `mcp` 1.x constraints, so `pip check` reports conflicts. The Strands worker was tested against MCP 2 and works; the others were not retested.
- MCP 2 renamed `FastMCP` to `MCPServer`. The `filesystem_server.py` copies in `1_google_adk_a2a/`, `2_strands_pydantic/` and `3_maf_agno/` still import `FastMCP` and will not start on MCP 2; `5_agent_frameworks/5_agent_loop/filesystem_server.py` shows the updated import (`from mcp.server.mcpserver import MCPServer`).
- Microsoft Agent Framework's own MCP client does not yet work with MCP 2, which is why the agent loop gives its MAF worker the file tools through `fastmcp` instead.

## Repository hygiene

`.gitignore` keeps these out of the repository: `.env` and other `.env.*` files (but not `.env.example`), virtual environments, `__pycache__`, SQLite files, logs, Jupyter checkpoints, IDE settings, personal digital-twin files (`email.txt`, `Profile.pdf`, `summary.txt`, `user_message.txt`), screenshots, `node_modules`, tool caches, OS files, private keys, and the agent loop's generated `5_agent_frameworks/5_agent_loop/site/` folder.