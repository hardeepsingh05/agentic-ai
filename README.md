# Agentic AI Learning Workspace

This repository contains hands-on projects and exercises from an Agentic AI learning path, covering both foundational OpenAI workflows and multi-agent orchestration with CrewAI.

## Project structure

```text
Agentic AI/
├── .env.example
├── .env
├── requirements.txt
├── README.md
├── 2_openai/
│   ├── 4_lab4.ipynb
│   └── README.md
├── 3_crewai/
│   ├── coder/
│   ├── debate/
│   ├── engineering_team/
│   ├── financial_researcher/
│   ├── researcher/
│   └── stock_picker/
└── .venv/
```

## Overview

### 2_openai
This folder includes a notebook-based lab focused on using the OpenAI Agents SDK for:

- planning research queries
- using web search tools
- summarizing results
- writing a markdown report
- sending the output by email

### 3_crewai
This folder contains multiple CrewAI-based mini projects demonstrating agent collaboration for:

- coding tasks
- debate simulations
- engineering workflows
- financial research
- general research
- stock-picking use cases

## Requirements

- Python 3.10+
- A virtual environment recommended
- OpenAI-compatible API access via environment variables
- Tavily API key for web search tools
- SMTP email settings if using email features

## Setup

Create a local environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Then configure your environment variables in a `.env` file. A sample file is available at `.env.example`.

Example:

```env
OPENAI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_openrouter_key
TAVILY_API_KEY=your_tavily_key
SENDER_EMAIL=your_sender@example.com
RECEIVER_EMAIL=recipient@example.com
GMAIL_PASSWORD=your_gmail_app_password
SMTP_SERVER=smtp.gmail.com
```

## Running projects

### OpenAI notebook
Open the notebook in VS Code and run the cells in order:

```text
2_openai/4_lab4.ipynb
```

### CrewAI projects
Each project under `3_crewai/` has its own `README.md` and can be run from its own folder using the project-specific setup.

Typical pattern:

```bash
cd 3_crewai/researcher
crewai run
```

## Learning goals

This workspace is designed to help you learn:

- agentic workflow design
- tool calling with LLMs
- autonomous search and planning
- multi-agent coordination
- structured output generation
- production-oriented prompting and orchestration patterns

## Notes

- Some notebooks and projects rely on external API keys and live services.
- Review all environment variables before running tasks that trigger web searches or email delivery.
- Use the project-specific READMEs for more details on each example.

## Recommended next steps

1. Start with the notebook in `2_openai/` to understand the agent workflow basics.
2. Explore the CrewAI examples under `3_crewai/`.
3. Modify prompts, agents, and tools to match your own project ideas.
4. Add logging, validation, and output storage for production-style use cases.
