"""
Qdrant MCP server, modelled on the official `mcp-server-qdrant`: an agent stores text in a Qdrant
collection and finds it again by meaning. Embeddings come from an Azure OpenAI embedding deployment.

By default Qdrant runs in local on-disk mode under `6_mcp/qdrant/`, so no Docker or server is needed.

Environment:
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION: Azure OpenAI connection.
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: Name of the embedding deployment, e.g. text-embedding-3-small.
    QDRANT_URL / QDRANT_API_KEY: Optional; use a Qdrant server or cloud cluster instead of the local folder.
    QDRANT_LOCAL_PATH: Optional; override the local storage folder.
    QDRANT_COLLECTION_NAME: Optional; default collection (falls back to "memories").
"""
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from qdrant_client import AsyncQdrantClient, models

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x

load_dotenv(override=True)

mcp = FastMCP("qdrant_server")

DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME") or "memories"
LOCAL_PATH = os.getenv("QDRANT_LOCAL_PATH") or str(Path(__file__).resolve().parent.parent / "qdrant")

_qdrant: AsyncQdrantClient | None = None
_openai: AsyncAzureOpenAI | None = None


def _get_qdrant() -> AsyncQdrantClient:
    """
    Return the shared Qdrant client, creating it on first use.

    Args:
        None

    Returns:
        A client for the Qdrant server in QDRANT_URL, or for the local on-disk store.
    Raises:
        None
    """
    global _qdrant
    if _qdrant is None:
        url = os.getenv("QDRANT_URL")
        _qdrant = (
            AsyncQdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
            if url
            else AsyncQdrantClient(path=LOCAL_PATH)
        )
    return _qdrant


async def _embed(text: str) -> list[float]:
    """
    Turn text into an embedding vector with the Azure OpenAI embedding deployment.

    Args:
        text: The text to embed.

    Returns:
        The embedding vector.
    Raises:
        RuntimeError: If AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not set.
        openai.OpenAIError: If the embedding request fails, e.g. wrong deployment name or credentials.
    """
    global _openai
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    if not deployment:
        raise RuntimeError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not set")
    if _openai is None:
        _openai = AsyncAzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )
    response = await _openai.embeddings.create(model=deployment, input=text)
    return response.data[0].embedding


@mcp.tool()
async def qdrant_store(
    information: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Store information in the Qdrant vector database so it can be found later by meaning.

    Args:
        information: The text to remember.
        metadata: Optional extra JSON data to keep alongside the text, e.g. source or tags.

    Returns:
        A confirmation of what was remembered.
    Raises:
        RuntimeError: If AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not set.
        openai.OpenAIError: If the embedding request fails.
    """
    # One fixed collection: letting the model pick names made later searches miss earlier stores.
    collection = DEFAULT_COLLECTION
    client = _get_qdrant()
    vector = await _embed(information)
    # The vector size is only known once we have an embedding, so the collection is created lazily.
    if not await client.collection_exists(collection):
        await client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=len(vector), distance=models.Distance.COSINE),
        )
    await client.upsert(
        collection_name=collection,
        points=[models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"document": information, "metadata": metadata},
        )],
    )
    return f"Remembered: {information}"


@mcp.tool()
async def qdrant_find(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Find stored information that is semantically closest to a query.

    Args:
        query: Describes what to look for.
        limit: Maximum number of matches to return.

    Returns:
        Matches from best to worst, each with `document`, `metadata` and `score`. Empty if nothing has been stored yet.
    Raises:
        RuntimeError: If AZURE_OPENAI_EMBEDDING_DEPLOYMENT is not set.
        openai.OpenAIError: If the embedding request fails.
    """
    collection = DEFAULT_COLLECTION
    client = _get_qdrant()
    if not await client.collection_exists(collection):
        return []
    result = await client.query_points(
        collection_name=collection,
        query=await _embed(query),
        limit=limit,
        with_payload=True,
    )
    return [
        {
            "document": point.payload.get("document"),
            "metadata": point.payload.get("metadata"),
            "score": point.score,
        }
        for point in result.points
    ]


@mcp.tool()
async def qdrant_list_collections() -> list[str]:
    """
    List the names of all collections in the Qdrant database.

    Args:
        None

    Returns:
        The collection names.
    Raises:
        None
    """
    response = await _get_qdrant().get_collections()
    return [c.name for c in response.collections]


if __name__ == "__main__":
    mcp.run(transport="stdio")
