"""Neo4j Graph Database Client for memos-graph."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase, ManagedTransaction

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async Neo4j client for entity graph operations."""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "memos123",
    ):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j connected to {uri}")
    
    async def close(self):
        """Close the Neo4j driver."""
        await self.driver.close()
    
    async def create_entity(
        self,
        agent_id: str,
        name: str,
        entity_type: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        """Create or merge an entity node."""
        async with self.driver.session() as session:
            result = await session.run("""
                MERGE (e:Entity {name: $name, agent_id: $agent_id})
                SET e.type = $type,
                    e.metadata = $metadata,
                    e.updated_at = datetime()
                RETURN e.id
            """, 
            name=name, 
            agent_id=agent_id, 
            type=entity_type,
            metadata=metadata or {}
            )
            record = await result.single()
            return record[0] if record else None
    
    async def create_relation(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        agent_id: str,
        properties: Optional[Dict] = None,
    ) -> bool:
        """Create a relationship between two entities."""
        async with self.driver.session() as session:
            await session.run("""
                MATCH (a:Entity {name: $source_name, agent_id: $agent_id})
                MATCH (b:Entity {name: $target_name, agent_id: $agent_id})
                MERGE (a)-[r:RELATION {type: $rel_type}]->(b)
                SET r += $properties,
                    r.updated_at = datetime()
                RETURN r
            """,
            source_name=source_name,
            target_name=target_name,
            rel_type=relation_type,
            agent_id=agent_id,
            properties=properties or {}
            )
            return True
    
    async def get_graph(
        self,
        agent_id: str,
        limit: int = 200,
    ) -> Dict[str, List[Dict]]:
        """
        Get the entity graph for an agent.
        
        Returns:
            {
                "nodes": [{"id": 1, "name": "张三", "type": "person", ...}],
                "links": [{"source": 1, "target": 2, "type": "works_at", ...}]
            }
        """
        async with self.driver.session() as session:
            # Query both Entity and Memory nodes
            result = await session.run("""
                MATCH (n)
                WHERE (n:Entity AND n.agent_id = $agent_id) OR (n:Memory AND n.agent_id = $agent_id)
                RETURN n
                ORDER BY n.created_at DESC
                LIMIT $limit
            """, agent_id=agent_id, limit=limit)
            
            nodes = []
            async for record in result:
                n = record["n"]
                labels = list(n.labels)
                node_data = {
                    "id": n.get("name") or str(n.get("id", "")),
                    "labels": labels,
                    "agent_id": n.get("agent_id"),
                }
                
                # Add type-specific properties
                if "Entity" in labels:
                    node_data["name"] = n.get("name")
                    node_data["type"] = n.get("type")
                    node_data["metadata"] = n.get("metadata", {})
                elif "Memory" in labels:
                    node_data["content"] = n.get("content", "")[:200]
                    node_data["scope"] = n.get("scope")
                    node_data["created_at"] = str(n.get("created_at"))
                
                nodes.append(node_data)
            
            # Query relationships (Entity-Entity only for now)
            rel_result = await session.run("""
                MATCH (a:Entity {agent_id: $agent_id})-[r]-(b:Entity {agent_id: $agent_id})
                RETURN a, r, b
                LIMIT $limit
            """, agent_id=agent_id, limit=limit)
            
            links = []
            async for record in rel_result:
                a = record["a"]
                b = record["b"]
                r = record["r"]
                
                links.append({
                    "source": a.get("name") or str(a.get("id", "")),
                    "target": b.get("name") or str(b.get("id", "")),
                    "type": r.get("type"),
                    "properties": {k: v for k, v in r.items() if k not in ["type"]},
                })
            
            return {
                "nodes": nodes,
                "links": links,
            }
    
    async def get_entities(self, agent_id: str, limit: int = 100) -> List[Dict]:
        """Get all entities for an agent."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (e:Entity {agent_id: $agent_id})
                RETURN e
                ORDER BY e.updated_at DESC
                LIMIT $limit
            """, agent_id=agent_id, limit=limit)
            
            entities = []
            async for record in result:
                e = record["e"]
                entities.append({
                    "id": e.id,
                    "name": e.get("name"),
                    "type": e.get("type"),
                    "agent_id": e.get("agent_id"),
                    "metadata": e.get("metadata", {}),
                })
            
            return entities
    
    async def get_relations(self, agent_id: str, limit: int = 100) -> List[Dict]:
        """Get all relations for an agent."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (a:Entity {agent_id: $agent_id})-[r]->(b:Entity)
                RETURN a, r, b
                LIMIT $limit
            """, agent_id=agent_id, limit=limit)
            
            relations = []
            async for record in result:
                relations.append({
                    "source_entity_id": record["a"].id,
                    "target_entity_id": record["b"].id,
                    "relation_type": record["r"].get("type"),
                    "properties": {k: v for k, v in record["r"].items() if k != "type"},
                })
            
            return relations
    
    async def delete_entity(self, entity_id: int) -> bool:
        """Delete an entity and all its relationships."""
        async with self.driver.session() as session:
            await session.run("""
                MATCH (e:Entity {id: $id})
                DETACH DELETE e
            """, id=entity_id)
            return True
    
    async def search_entities(
        self,
        agent_id: str,
        query: str,
        limit: int = 20,
    ) -> List[Dict]:
        """Search entities by name (full-text)."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (e:Entity {agent_id: $agent_id})
                WHERE e.name CONTAINS $query
                RETURN e
                LIMIT $limit
            """, agent_id=agent_id, query=query, limit=limit)
            
            entities = []
            async for record in result:
                e = record["e"]
                entities.append({
                    "id": e.id,
                    "name": e.get("name"),
                    "type": e.get("type"),
                    "score": 1.0,  # Simple scoring
                })
            
            return entities


# Global instance
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create the global Neo4j client instance."""
    global _neo4j_client
    if _neo4j_client is None:
        from memos_graph.config import load_config
        cfg = load_config()
        
        neo4j_uri = cfg.neo4j.uri if hasattr(cfg, 'neo4j') else "bolt://localhost:7687"
        neo4j_user = cfg.neo4j.username if hasattr(cfg, 'neo4j') else "neo4j"
        neo4j_password = cfg.neo4j.password if hasattr(cfg, 'neo4j') else ""
        
        _neo4j_client = Neo4jClient(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )
    return _neo4j_client
