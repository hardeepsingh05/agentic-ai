"""
Knowledge-graph memory MCP server, modelled on Anthropic's open source `server-memory`.

The graph (entities, their observations, and the relations between them) is persisted as JSON
in `6_mcp/memory/memory.json`, so an agent keeps its memory across runs.
"""
import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x

mcp = FastMCP("memory_server")

# MEMORY_FILE_PATH can override the default location (6_mcp/memory/memory.json).
MEMORY_FILE = Path(
    os.getenv("MEMORY_FILE_PATH") or Path(__file__).resolve().parent.parent / "memory" / "memory.json"
)


class Entity(BaseModel):
    """A node in the knowledge graph."""
    name: str = Field(description="Unique name of the entity")
    entity_type: str = Field(description="Type of the entity, e.g. person, company, project")
    observations: list[str] = Field(default_factory=list, description="Facts known about the entity")


class Relation(BaseModel):
    """A directed edge between two entities, written in active voice."""
    source: str = Field(description="Name of the entity the relation starts from")
    target: str = Field(description="Name of the entity the relation points to")
    relation_type: str = Field(description="Relation in active voice, e.g. works_at, owns")


class ObservationInput(BaseModel):
    """Observations to add to, or remove from, one entity."""
    entity_name: str = Field(description="Name of the entity to change")
    contents: list[str] = Field(description="Observation texts")


class KnowledgeGraph(BaseModel):
    """The full graph or a slice of it."""
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


def _load() -> KnowledgeGraph:
    """
    Read the knowledge graph from disk.

    Args:
        None

    Returns:
        The stored graph, or an empty graph when the memory file does not exist yet.
    Raises:
        pydantic.ValidationError: If the memory file exists but does not match the graph schema.
        json.JSONDecodeError: If the memory file exists but is not valid JSON.
    """
    if not MEMORY_FILE.exists():
        return KnowledgeGraph()
    return KnowledgeGraph.model_validate(json.loads(MEMORY_FILE.read_text(encoding="utf-8")))


def _save(graph: KnowledgeGraph) -> None:
    """
    Write the knowledge graph to disk, creating the memory folder if needed.

    Args:
        graph: The graph to persist.

    Returns:
        None
    Raises:
        OSError: If the memory folder or file cannot be written.
    """
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file first so a crash mid-write cannot corrupt the existing memory.
    tmp = MEMORY_FILE.with_suffix(".tmp")
    tmp.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(MEMORY_FILE)


@mcp.tool()
async def create_entities(entities: list[Entity]) -> list[Entity]:
    """
    Create new entities in the knowledge graph. Entities whose name already exists are ignored.

    Args:
        entities: The entities to create, each with a name, a type and optional observations.

    Returns:
        The entities that were actually created.
    Raises:
        None
    """
    graph = _load()
    existing = {e.name for e in graph.entities}
    created = []
    for entity in entities:
        if entity.name not in existing:
            existing.add(entity.name)
            created.append(entity)
    graph.entities.extend(created)
    _save(graph)
    return created


@mcp.tool()
async def create_relations(relations: list[Relation]) -> list[Relation]:
    """
    Create directed relations between existing entities. Duplicate relations are ignored.

    Args:
        relations: The relations to create, each with a source, a target and a relation type.

    Returns:
        The relations that were actually created.
    Raises:
        None
    """
    graph = _load()
    existing = {(r.source, r.target, r.relation_type) for r in graph.relations}
    created = []
    for relation in relations:
        key = (relation.source, relation.target, relation.relation_type)
        if key not in existing:
            existing.add(key)
            created.append(relation)
    graph.relations.extend(created)
    _save(graph)
    return created


@mcp.tool()
async def add_observations(observations: list[ObservationInput]) -> list[ObservationInput]:
    """
    Add new observations to existing entities. Observations an entity already has are skipped.

    Args:
        observations: For each entity, the observation texts to add.

    Returns:
        For each entity, the observations that were actually added.
    Raises:
        ValueError: If an entity name does not exist in the graph.
    """
    graph = _load()
    by_name = {e.name: e for e in graph.entities}
    added = []
    for item in observations:
        entity = by_name.get(item.entity_name)
        if entity is None:
            raise ValueError(f"Entity with name {item.entity_name} not found")
        new = [c for c in dict.fromkeys(item.contents) if c not in entity.observations]
        entity.observations.extend(new)
        added.append(ObservationInput(entity_name=item.entity_name, contents=new))
    _save(graph)
    return added


@mcp.tool()
async def delete_entities(entity_names: list[str]) -> str:
    """
    Delete entities, together with every relation that touches them.

    Args:
        entity_names: Names of the entities to delete. Unknown names are ignored.

    Returns:
        A confirmation message.
    Raises:
        None
    """
    graph = _load()
    doomed = set(entity_names)
    graph.entities = [e for e in graph.entities if e.name not in doomed]
    graph.relations = [r for r in graph.relations if r.source not in doomed and r.target not in doomed]
    _save(graph)
    return "Entities deleted successfully"


@mcp.tool()
async def delete_observations(deletions: list[ObservationInput]) -> str:
    """
    Delete specific observations from entities.

    Args:
        deletions: For each entity, the exact observation texts to remove. Unknown entities are ignored.

    Returns:
        A confirmation message.
    Raises:
        None
    """
    graph = _load()
    by_name = {e.name: e for e in graph.entities}
    for item in deletions:
        entity = by_name.get(item.entity_name)
        if entity is not None:
            entity.observations = [o for o in entity.observations if o not in item.contents]
    _save(graph)
    return "Observations deleted successfully"


@mcp.tool()
async def delete_relations(relations: list[Relation]) -> str:
    """
    Delete specific relations from the graph.

    Args:
        relations: The relations to remove, matched on source, target and relation type.

    Returns:
        A confirmation message.
    Raises:
        None
    """
    graph = _load()
    doomed = {(r.source, r.target, r.relation_type) for r in relations}
    graph.relations = [r for r in graph.relations if (r.source, r.target, r.relation_type) not in doomed]
    _save(graph)
    return "Relations deleted successfully"


@mcp.tool()
async def read_graph() -> KnowledgeGraph:
    """
    Read the entire knowledge graph.

    Args:
        None

    Returns:
        All entities and relations currently stored.
    Raises:
        None
    """
    return _load()


@mcp.tool()
async def search_nodes(query: str) -> KnowledgeGraph:
    """
    Search entities by a case-insensitive match on name, type or observation text.

    Args:
        query: The text to look for.

    Returns:
        The matching entities and the relations between them.
    Raises:
        None
    """
    graph = _load()
    needle = query.lower()
    matches = [
        e for e in graph.entities
        if needle in e.name.lower()
        or needle in e.entity_type.lower()
        or any(needle in o.lower() for o in e.observations)
    ]
    names = {e.name for e in matches}
    relations = [r for r in graph.relations if r.source in names and r.target in names]
    return KnowledgeGraph(entities=matches, relations=relations)


@mcp.tool()
async def open_nodes(names: list[str]) -> KnowledgeGraph:
    """
    Retrieve specific entities by name.

    Args:
        names: Names of the entities to retrieve. Unknown names are ignored.

    Returns:
        The requested entities and the relations between them.
    Raises:
        None
    """
    graph = _load()
    wanted = set(names)
    entities = [e for e in graph.entities if e.name in wanted]
    found = {e.name for e in entities}
    relations = [r for r in graph.relations if r.source in found and r.target in found]
    return KnowledgeGraph(entities=entities, relations=relations)


if __name__ == "__main__":
    mcp.run(transport="stdio")
