import os
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from tavily import TavilyClient


class TavilySearchInput(BaseModel):
    """Input schema for the custom Tavily search tool."""
    query: str = Field(..., description="The precise search query string to look up on the web/internet.")

class CustomTavilySearchTool(BaseTool):
    name: str = "web_search_tool"
    description: str = (
        "A comprehensive web search engine. Use this tool whenever you need to look up real-time information, news, current events/affairs, or industry data on internet."
    )
    args_schema: Type[BaseModel] = TavilySearchInput

    def _run(self, query: str) -> str:
        # Initialize and run tavily search tool
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY is not set in the environment variables."
        try:
            tavily_client=TavilyClient(api_key=api_key)
            response =  tavily_client.search(query=query, max_results=5)
            return str(response)
        except Exception as e:
            return f"Error executing search: {str(e)}"
