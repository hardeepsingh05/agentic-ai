# AI Research Agent Workflow Notebook

This project contains the notebook `4_lab4.ipynb`, which demonstrates a research automation workflow built with the OpenAI Agents SDK.

The notebook creates a multi-agent pipeline that:

- plans web searches
- performs live web research
- summarizes findings into a structured report
- sends the final report by email

## What the notebook does

The workflow is composed of four agents:

1. Search Agent
   - searches the web for a query
   - returns a concise summary of the results

2. Planner Agent
   - generates a list of targeted search queries
   - uses structured output with Pydantic models

3. Writer Agent
   - turns research into a detailed markdown report
   - writes a longer-form report with sections and follow-up questions

4. Email Agent
   - sends the final report via SMTP to a configured recipient

## Prerequisites

- Python 3.10+
- Access to the workspace dependencies in the root `requirements.txt`
- API keys for OpenRouter and Tavily
- SMTP email credentials if you want the notebook to send email

## Installation

From the workspace root:

```bash
pip install -r requirements.txt
```

If the environment is not already configured, create a `.env` file in the project root with values like:

```env
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
SENDER_EMAIL=your_sender_email@example.com
RECEIVER_EMAIL=recipient@example.com
GMAIL_PASSWORD=your_gmail_app_password
SMTP_SERVER=smtp.gmail.com
```

## Run the notebook

Open the notebook in VS Code and run the cells in order:

- `4_lab4.ipynb`

The final cell executes the research workflow for the query:

```python
query = "Most of the popular AI Agent frameworks in 2026"
```

This triggers:

- planning the search set
- running multiple web searches
- writing a markdown report
- emailing the report

## Important notes

- The notebook uses `AsyncOpenAI` with the OpenRouter base URL.
- The web search tool uses Tavily for live results.
- The email tool uses SMTP over SSL with the Gmail configuration in the environment variables.
- To avoid accidental emails during testing, review the configuration before running the final email step.

## Project structure

```text
2_openai/
├── 4_lab4.ipynb
├── README.md
```

## Suggested next improvements

- add a reusable `.env.example` file
- split the notebook into a clean Python script and a notebook demo
- add error handling and retries for API calls
- store generated reports in an `output/` folder
- add logging for search and email actions
