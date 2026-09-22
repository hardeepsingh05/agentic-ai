# Agentic Frameworks

Learning labs and working examples for building AI agents with Azure OpenAI, Azure AI Foundry, OpenAI tooling, LangChain/LangGraph, Google ADK, A2A, and MCP.

## Contents

| Directory | Focus |
| --- | --- |
| `1_foundations/` | Introductory notebooks and a Gradio-based digital twin that can use Azure OpenAI, Azure-hosted Anthropic models, and local tools. |
| `2_openai/` | OpenAI SDK notebooks, a message recorder, and an Outlook desktop email tool for Windows. |
| `4_langchain_langgraph/` | LangChain and LangGraph labs, browser/search tools, a slide kit, and the Sidekick agent with guardrails and human approval for sensitive actions. |
| `5_agent_frameworks/1_google_adk_a2a/` | Google ADK and A2A experiments, including a shared SQLite task board and a sandboxed FastMCP filesystem server. |
| `requirements.txt` | Python packages used across the exercises. |

## Setup

1. Use Python 3.11 or later.
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

## Running Selected Examples

- Launch the digital twin from its directory:

  ```powershell
  Set-Location 1_foundations/digital_twin
  python app.py
  ```

- Run the Sidekick from `4_langchain_langgraph/` through its associated notebook or Python entry point after providing the appropriate Azure OpenAI and search settings.
- Run the Google ADK/A2A labs from `5_agent_frameworks/1_google_adk_a2a/lab.ipynb`. The filesystem server is intended to operate within `MCP_ROOT`.

## Notes

- Some labs call paid external model and search services; review provider pricing and deployment availability first.
- Browser examples may require Playwright browsers to be installed separately:

  ```powershell
  python -m playwright install
  ```
- The Outlook integration uses Windows COM automation and is Windows-specific.