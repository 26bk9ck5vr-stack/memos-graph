"""Graph endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from memos_graph.db.session import get_session
from memos_graph.db.models import Entity, EntityEdge

router = APIRouter()


class EntityResponse(BaseModel):
    id: int
    name: str
    type: str
    metadata: dict


class EntityEdgeResponse(BaseModel):
    from_entity_id: int
    to_entity_id: int
    relation_type: str
    confidence: float | None


@router.get("/entities", response_model=list[EntityResponse])
async def list_entities(
    agent_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List all entities for an agent (for graph visualization)."""
    try:
        query = select(Entity)
        if agent_id:
            query = query.where(Entity.agent_id == agent_id)
        query = query.limit(200)

        result = await session.execute(query)
        entities = result.scalars().all()

        return [
            EntityResponse(id=e.id, name=e.name, type=e.type, metadata=e.metadata_ or {})
            for e in entities
        ]
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/entity-edges", response_model=list[EntityEdgeResponse])
async def list_entity_edges(
    agent_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List all entity edges for an agent (for graph visualization)."""
    try:
        query = select(EntityEdge)
        if agent_id:
            query = query.where(EntityEdge.agent_id == agent_id)
        query = query.limit(500)

        result = await session.execute(query)
        edges = result.scalars().all()

        return [
            EntityEdgeResponse(
                from_entity_id=e.from_entity_id,
                to_entity_id=e.to_entity_id,
                relation_type=e.relation_type,
                confidence=e.confidence,
            )
            for e in edges
        ]
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


class GraphExpandRequest(BaseModel):
    entity_name: str
    agent_id: str
    depth: int = 1


class GraphExpandResponse(BaseModel):
    entity: EntityResponse
    connected_entities: list[EntityResponse]
    edges: list[dict]


@router.get("/graph/entity/{entity_name}", response_model=list[EntityResponse])
async def get_entity(
    entity_name: str,
    agent_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Entity).where(Entity.name == entity_name)
    if agent_id:
        query = query.where(Entity.agent_id == agent_id)

    result = await session.execute(query)
    entities = result.scalars().all()

    return [
        EntityResponse(id=e.id, name=e.name, type=e.type, metadata=e.metadata_ or {})
        for e in entities
    ]


@router.post("/graph/expand", response_model=GraphExpandResponse)
async def expand_graph(
    request: GraphExpandRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Entity).where(
            Entity.name == request.entity_name,
            Entity.agent_id == request.agent_id,
        )
    )
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    edges_result = await session.execute(
        select(EntityEdge).where(
            EntityEdge.from_entity_id == entity.id,
            EntityEdge.agent_id == request.agent_id,
        ).limit(50)
    )
    edges = edges_result.scalars().all()

    connected_entity_ids = [e.to_entity_id for e in edges]
    if connected_entity_ids:
        connected_result = await session.execute(
            select(Entity).where(Entity.id.in_(connected_entity_ids))
        )
        connected_entities = connected_result.scalars().all()
    else:
        connected_entities = []

    return GraphExpandResponse(
        entity=EntityResponse(id=entity.id, name=entity.name, type=entity.type, metadata=entity.metadata_ or {}),
        connected_entities=[
            EntityResponse(id=e.id, name=e.name, type=e.type, metadata=e.metadata_ or {})
            for e in connected_entities
        ],
        edges=[
            {
                "from_entity_id": e.from_entity_id,
                "to_entity_id": e.to_entity_id,
                "relation_type": e.relation_type,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    )
