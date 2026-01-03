"""Knowledge graph service for analyzing conversation relationships."""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from memhub.database import Entity, Relationship, Conversation
import networkx as nx
from collections import defaultdict


class GraphService:
    """Service for knowledge graph operations."""

    def __init__(self):
        """Initialize graph service."""
        pass

    def build_user_graph(self, db: Session, user_id: str) -> nx.DiGraph:
        """
        Build knowledge graph for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            NetworkX directed graph
        """
        # Get all entities for user
        entities = db.query(Entity).join(
            Conversation
        ).filter(
            Conversation.user_id == user_id
        ).all()

        entity_ids = [e.id for e in entities]

        # Get relationships between entities
        relationships = db.query(Relationship).filter(
            and_(
                Relationship.source_entity_id.in_(entity_ids),
                Relationship.target_entity_id.in_(entity_ids)
            )
        ).all()

        # Build graph
        G = nx.DiGraph()

        # Add nodes
        for entity in entities:
            G.add_node(
                entity.id,
                name=entity.entity_name,
                type=entity.entity_type,
                description=entity.description
            )

        # Add edges
        for rel in relationships:
            G.add_edge(
                rel.source_entity_id,
                rel.target_entity_id,
                type=rel.relationship_type,
                weight=rel.weight
            )

        return G

    def get_related_entities(
        self,
        db: Session,
        entity_name: str,
        user_id: str,
        max_depth: int = 2,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get entities related to a given entity.

        Args:
            db: Database session
            entity_name: Name of the entity
            user_id: User ID
            max_depth: Maximum relationship depth
            limit: Maximum number of results

        Returns:
            List of related entities with relationship info
        """
        # Find the entity
        entity = db.query(Entity).join(
            Conversation
        ).filter(
            and_(
                Entity.entity_name.ilike(f"%{entity_name}%"),
                Conversation.user_id == user_id
            )
        ).first()

        if not entity:
            return []

        # Build graph
        G = self.build_user_graph(db, user_id)

        if entity.id not in G:
            return []

        # Find connected entities within max_depth
        related = []
        visited = set()

        def dfs(node_id: int, depth: int, path: List[int]):
            if depth > max_depth or node_id in visited:
                return

            visited.add(node_id)

            # Get neighbors
            for neighbor in G.successors(node_id):
                if neighbor not in visited:
                    edge_data = G.get_edge_data(node_id, neighbor)
                    node_data = G.nodes[neighbor]

                    related.append({
                        "entity_id": neighbor,
                        "entity_name": node_data.get("name"),
                        "entity_type": node_data.get("type"),
                        "relationship_type": edge_data.get("type"),
                        "weight": edge_data.get("weight", 1.0),
                        "depth": depth + 1,
                        "path": path + [neighbor]
                    })

                    if len(related) < limit:
                        dfs(neighbor, depth + 1, path + [neighbor])

        dfs(entity.id, 0, [entity.id])

        # Sort by weight and depth
        related.sort(key=lambda x: (-x["weight"], x["depth"]))

        return related[:limit]

    def get_entity_importance(
        self,
        db: Session,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get most important entities based on graph centrality.

        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of results

        Returns:
            List of entities with importance scores
        """
        G = self.build_user_graph(db, user_id)

        if len(G.nodes) == 0:
            return []

        # Calculate centrality measures
        try:
            pagerank = nx.pagerank(G, weight="weight")
        except:
            pagerank = {node: 1.0 / len(G.nodes) for node in G.nodes}

        # Get degree centrality
        degree_centrality = {
            node: G.degree(node, weight="weight")
            for node in G.nodes
        }

        # Combine scores
        importance_scores = []
        for node_id in G.nodes:
            node_data = G.nodes[node_id]
            importance_scores.append({
                "entity_id": node_id,
                "entity_name": node_data.get("name"),
                "entity_type": node_data.get("type"),
                "pagerank": pagerank.get(node_id, 0),
                "degree": degree_centrality.get(node_id, 0),
                "importance": pagerank.get(node_id, 0) * 0.6 +
                             (degree_centrality.get(node_id, 0) / max(degree_centrality.values() or [1])) * 0.4
            })

        # Sort by importance
        importance_scores.sort(key=lambda x: -x["importance"])

        return importance_scores[:limit]

    def get_topic_clusters(
        self,
        db: Session,
        user_id: str,
        min_cluster_size: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Identify topic clusters in the knowledge graph.

        Args:
            db: Database session
            user_id: User ID
            min_cluster_size: Minimum cluster size

        Returns:
            List of topic clusters
        """
        G = self.build_user_graph(db, user_id)

        if len(G.nodes) < min_cluster_size:
            return []

        # Convert to undirected for community detection
        G_undirected = G.to_undirected()

        # Find communities using Louvain algorithm
        try:
            import community as community_louvain
            communities = community_louvain.best_partition(G_undirected, weight="weight")
        except ImportError:
            # Fallback to connected components
            communities = {}
            for i, component in enumerate(nx.connected_components(G_undirected)):
                for node in component:
                    communities[node] = i

        # Group by community
        clusters_dict = defaultdict(list)
        for node_id, community_id in communities.items():
            node_data = G.nodes[node_id]
            clusters_dict[community_id].append({
                "entity_id": node_id,
                "entity_name": node_data.get("name"),
                "entity_type": node_data.get("type")
            })

        # Filter and format
        clusters = []
        for community_id, entities in clusters_dict.items():
            if len(entities) >= min_cluster_size:
                # Get most common entity type for cluster label
                types = [e["entity_type"] for e in entities]
                most_common_type = max(set(types), key=types.count) if types else "unknown"

                clusters.append({
                    "cluster_id": community_id,
                    "cluster_label": most_common_type,
                    "size": len(entities),
                    "entities": entities
                })

        # Sort by size
        clusters.sort(key=lambda x: -x["size"])

        return clusters

    def get_conversation_timeline(
        self,
        db: Session,
        user_id: str,
        entity_name: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of conversations, optionally filtered by entity.

        Args:
            db: Database session
            user_id: User ID
            entity_name: Optional entity name to filter by
            limit: Maximum number of results

        Returns:
            Timeline of conversations
        """
        query = db.query(Conversation).filter(
            Conversation.user_id == user_id
        )

        if entity_name:
            # Find conversations that mention the entity
            entity_ids = db.query(Entity.conversation_id).filter(
                Entity.entity_name.ilike(f"%{entity_name}%")
            ).subquery()

            query = query.filter(Conversation.id.in_(entity_ids))

        conversations = query.order_by(
            Conversation.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": conv.id,
                "session_id": conv.session_id,
                "role": conv.role,
                "content": conv.content[:200] + "..." if len(conv.content) > 200 else conv.content,
                "platform": conv.platform,
                "created_at": conv.created_at.isoformat()
            }
            for conv in conversations
        ]


# Singleton instance
_graph_service: Optional[GraphService] = None


def get_graph_service() -> GraphService:
    """Get graph service singleton."""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
