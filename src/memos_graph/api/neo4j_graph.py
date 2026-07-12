"""Neo4j Graph API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from memos_graph.graph.neodb import get_neo4j_client, Neo4jClient

router = APIRouter(prefix="/neo4j", tags=["neo4j"])


async def get_client() -> Neo4jClient:
    """Dependency to get Neo4j client."""
    return get_neo4j_client()


@router.get("/graph")
async def get_entity_graph(
    agent_id: str = Query(..., description="Agent ID"),
    limit: int = Query(200, ge=1, le=1000),
    client: Neo4jClient = Depends(get_client),
):
    """
    Get entity graph with nodes and links for visualization.
    
    Returns data in format compatible with ECharts/D3 force-directed graphs.
    """
    try:
        graph = await client.get_graph(agent_id=agent_id, limit=limit)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")


@router.get("/entities")
async def list_entities(
    agent_id: str = Query(..., description="Agent ID"),
    limit: int = Query(100, ge=1, le=500),
    client: Neo4jClient = Depends(get_client),
):
    """List all entities for an agent."""
    try:
        entities = await client.get_entities(agent_id=agent_id, limit=limit)
        return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")


@router.get("/relations")
async def list_relations(
    agent_id: str = Query(..., description="Agent ID"),
    limit: int = Query(100, ge=1, le=500),
    client: Neo4jClient = Depends(get_client),
):
    """List all relations for an agent."""
    try:
        relations = await client.get_relations(agent_id=agent_id, limit=limit)
        return relations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="Search query"),
    agent_id: str = Query(..., description="Agent ID"),
    limit: int = Query(20, ge=1, le=100),
    client: Neo4jClient = Depends(get_client),
):
    """Search entities by name."""
    try:
        entities = await client.search_entities(
            agent_id=agent_id,
            query=q,
            limit=limit,
        )
        return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j query failed: {str(e)}")


@router.post("/entities")
async def create_entity(
    agent_id: str,
    name: str,
    type: str,
    metadata: Optional[dict] = None,
    client: Neo4jClient = Depends(get_client),
):
    """Create a new entity."""
    try:
        entity_id = await client.create_entity(
            agent_id=agent_id,
            name=name,
            entity_type=type,
            metadata=metadata,
        )
        return {"id": entity_id, "name": name, "type": type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j operation failed: {str(e)}")


@router.post("/relations")
async def create_relation(
    source_name: str,
    target_name: str,
    type: str,
    agent_id: str,
    properties: Optional[dict] = None,
    client: Neo4jClient = Depends(get_client),
):
    """Create a relationship between two entities."""
    try:
        success = await client.create_relation(
            source_name=source_name,
            target_name=target_name,
            relation_type=type,
            agent_id=agent_id,
            properties=properties,
        )
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j operation failed: {str(e)}")
