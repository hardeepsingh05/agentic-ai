"""
Tavily MCP server: a Python stand-in for the `tavily-mcp` npm package, for machines where `npx` cannot
reach the npm registry. It exposes the same capabilities (search, extract, crawl, map, research) by
calling the Tavily REST API directly. Needs TAVILY_API_KEY in the environment or in a .env file.
"""
import asyncio
import os
import ssl
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x

load_dotenv(override=True)

mcp = FastMCP("tavily_server")

try:
    import truststore
    # Corporate proxies re-sign TLS traffic; the OS store trusts that CA while certifi's bundle does not.
    SSL_VERIFY: ssl.SSLContext | bool = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:
    SSL_VERIFY = True

TAVILY_BASE_URL = "https://api.tavily.com"
RESEARCH_POLL_SECONDS = 5
RESEARCH_MAX_WAIT_SECONDS = 240


def _headers() -> dict[str, str]:
    """
    Build the authorisation headers for a Tavily request.

    Args:
        None

    Returns:
        Headers carrying the bearer token.
    Raises:
        RuntimeError: If TAVILY_API_KEY is not set.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return {"Authorization": f"Bearer {api_key}"}


def _raise_for_error(response: httpx.Response) -> None:
    """
    Turn a failed Tavily response into an exception that carries Tavily's own error message.

    Args:
        response: The HTTP response to check.

    Returns:
        None
    Raises:
        RuntimeError: If the response status is 400 or above.
    """
    if response.status_code >= 400:
        raise RuntimeError(f"Tavily API error {response.status_code}: {response.text}")


async def _post(endpoint: str, payload: dict[str, Any], timeout: float = 180) -> httpx.Response:
    """
    POST a JSON payload to a Tavily endpoint, leaving out any parameter that is None.

    Args:
        endpoint: Endpoint path such as "/search".
        payload: Request body; None values are dropped so Tavily applies its own defaults.
        timeout: Seconds to wait for the HTTP response.

    Returns:
        The successful HTTP response.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing or Tavily returns an error status.
        httpx.HTTPError: If the request fails at the network level or times out.
    """
    body = {k: v for k, v in payload.items() if v is not None}
    async with httpx.AsyncClient(timeout=timeout, verify=SSL_VERIFY) as client:
        response = await client.post(f"{TAVILY_BASE_URL}{endpoint}", json=body, headers=_headers())
    _raise_for_error(response)
    return response


@mcp.tool()
async def tavily_search(
    query: str,
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "basic",
    topic: Literal["general", "news", "finance"] = "general",
    max_results: int = 10,
    time_range: Literal["day", "week", "month", "year"] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_images: bool = False,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Search the web in real time and return ranked, LLM-ready results.

    Args:
        query: The search query.
        search_depth: "basic" is balanced, "advanced" is most relevant but slower (2 credits), "fast" and "ultra-fast" favour latency.
        topic: "news" for current events, "finance" for financial topics, otherwise "general".
        max_results: Maximum number of results, from 0 to 20.
        time_range: Only return results published or updated within this window back from today.
        start_date: Only return results after this date, formatted YYYY-MM-DD.
        end_date: Only return results before this date, formatted YYYY-MM-DD.
        include_domains: Restrict results to these domains.
        exclude_domains: Leave out results from these domains.
        include_answer: Add a short LLM-generated answer to the response.
        include_raw_content: Add the cleaned full page content to each result.
        include_images: Add query-related images to the response.
        country: Boost results from this country, e.g. "united kingdom". Only used when topic is "general".

    Returns:
        Tavily's response, including `results` (title, url, content, score) and optionally `answer` and `images`.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing or Tavily returns an error status.
        httpx.HTTPError: If the request fails at the network level or times out.
    """
    response = await _post("/search", {
        "query": query,
        "search_depth": search_depth,
        "topic": topic,
        "max_results": max_results,
        "time_range": time_range,
        "start_date": start_date,
        "end_date": end_date,
        "include_domains": include_domains,
        "exclude_domains": exclude_domains,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "include_images": include_images,
        "country": country,
    })
    return response.json()


@mcp.tool()
async def tavily_extract(
    urls: list[str],
    extract_depth: Literal["basic", "advanced"] = "basic",
    format: Literal["markdown", "text"] = "markdown",
    include_images: bool = False,
    query: str | None = None,
) -> dict[str, Any]:
    """
    Extract the content of one or more web pages (up to 20 URLs per call).

    Args:
        urls: The URLs to extract from.
        extract_depth: "advanced" also retrieves tables and embedded content, with higher success but more latency.
        format: Output format of the page content.
        include_images: Add the images found on each page.
        query: When given, only the chunks most relevant to this query are returned for each page.

    Returns:
        Tavily's response with `results` (url, raw_content) and `failed_results` (url, error); check both.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing or Tavily returns an error status.
        httpx.HTTPError: If the request fails at the network level or times out.
    """
    response = await _post("/extract", {
        "urls": urls,
        "extract_depth": extract_depth,
        "format": format,
        "include_images": include_images,
        "query": query,
    })
    return response.json()


@mcp.tool()
async def tavily_crawl(
    url: str,
    instructions: str | None = None,
    max_depth: int = 1,
    max_breadth: int = 20,
    limit: int = 50,
    select_paths: list[str] | None = None,
    select_domains: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    allow_external: bool = True,
    extract_depth: Literal["basic", "advanced"] = "basic",
    format: Literal["markdown", "text"] = "markdown",
) -> dict[str, Any]:
    """
    Crawl a website from a root URL, following links and extracting the content of each page.

    Args:
        url: The root URL to start from.
        instructions: Natural-language guidance on which pages to find (costs more credits).
        max_depth: How many link levels away from the root to explore, from 1 to 5.
        max_breadth: Maximum links followed per page, from 1 to 500.
        limit: Total number of pages to process before stopping.
        select_paths: Regex patterns; only URLs whose path matches are crawled.
        select_domains: Regex patterns; only matching domains or subdomains are crawled.
        exclude_paths: Regex patterns; URLs whose path matches are skipped.
        exclude_domains: Regex patterns; matching domains or subdomains are skipped.
        allow_external: Whether links to external domains appear in the results.
        extract_depth: "advanced" retrieves more data per page but is slower.
        format: Output format of the page content.

    Returns:
        Tavily's response with `base_url` and `results` (url, raw_content) for every crawled page.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing or Tavily returns an error status.
        httpx.HTTPError: If the request fails at the network level or times out.
    """
    response = await _post("/crawl", {
        "url": url,
        "instructions": instructions,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
        "limit": limit,
        "select_paths": select_paths,
        "select_domains": select_domains,
        "exclude_paths": exclude_paths,
        "exclude_domains": exclude_domains,
        "allow_external": allow_external,
        "extract_depth": extract_depth,
        "format": format,
    }, timeout=200)
    return response.json()


@mcp.tool()
async def tavily_map(
    url: str,
    instructions: str | None = None,
    max_depth: int = 1,
    max_breadth: int = 20,
    limit: int = 50,
    select_paths: list[str] | None = None,
    select_domains: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    allow_external: bool = True,
) -> dict[str, Any]:
    """
    Build a map of a website's structure by discovering its URLs, without extracting page content.

    Args:
        url: The root URL to start from.
        instructions: Natural-language guidance on which pages to find (costs more credits).
        max_depth: How many link levels away from the root to explore, from 1 to 5.
        max_breadth: Maximum links followed per page, from 1 to 500.
        limit: Total number of links to process before stopping.
        select_paths: Regex patterns; only URLs whose path matches are mapped.
        select_domains: Regex patterns; only matching domains or subdomains are mapped.
        exclude_paths: Regex patterns; URLs whose path matches are skipped.
        exclude_domains: Regex patterns; matching domains or subdomains are skipped.
        allow_external: Whether links to external domains appear in the results.

    Returns:
        Tavily's response with `base_url` and `results`, the list of discovered URLs.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing or Tavily returns an error status.
        httpx.HTTPError: If the request fails at the network level or times out.
    """
    response = await _post("/map", {
        "url": url,
        "instructions": instructions,
        "max_depth": max_depth,
        "max_breadth": max_breadth,
        "limit": limit,
        "select_paths": select_paths,
        "select_domains": select_domains,
        "exclude_paths": exclude_paths,
        "exclude_domains": exclude_domains,
        "allow_external": allow_external,
    }, timeout=200)
    return response.json()


@mcp.tool()
async def tavily_research(
    input: str,
    model: Literal["mini", "pro", "auto"] = "auto",
    citation_format: Literal["numbered", "mla", "apa", "chicago"] = "numbered",
    output_length: Literal["short", "standard", "long"] = "standard",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run an in-depth research task and return a cited report. Searches, reads and synthesises many sources, so it is slow.

    Args:
        input: The research question or task.
        model: "mini" for narrow questions, "pro" for broad multi-angle topics, "auto" to let Tavily choose.
        citation_format: Citation style used in the report.
        output_length: Target size of the report.
        include_domains: Domains the agent should prefer (soft preference, at most 20).
        exclude_domains: Domains the agent must never use (at most 20).

    Returns:
        The finished task with `content` (the report) and `sources`. If it is still running after the wait limit,
        the task's current `status` and `request_id` are returned instead.
    Raises:
        RuntimeError: If TAVILY_API_KEY is missing, Tavily returns an error status, or the research task fails.
        httpx.HTTPError: If a request fails at the network level or times out.
    """
    created = (await _post("/research", {
        "input": input,
        "model": model,
        "citation_format": citation_format,
        "output_length": output_length,
        "include_domains": include_domains,
        "exclude_domains": exclude_domains,
    })).json()
    request_id = created["request_id"]

    waited = 0
    async with httpx.AsyncClient(timeout=60, verify=SSL_VERIFY) as client:
        while waited < RESEARCH_MAX_WAIT_SECONDS:
            await asyncio.sleep(RESEARCH_POLL_SECONDS)
            waited += RESEARCH_POLL_SECONDS
            response = await client.get(f"{TAVILY_BASE_URL}/research/{request_id}", headers=_headers())
            _raise_for_error(response)
            result = response.json()
            # 202 means still pending / in_progress; 200 carries the final completed or failed state.
            if response.status_code == 200:
                if result.get("status") == "failed":
                    raise RuntimeError(f"Tavily research task {request_id} failed")
                return result
    return {"request_id": request_id, "status": result.get("status", "pending")}


if __name__ == "__main__":
    mcp.run(transport="stdio")
