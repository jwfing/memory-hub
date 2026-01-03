"""RAG (Retrieval Augmented Generation) service for memory retrieval."""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_
from memhub.database import Conversation, Summary, Entity
from memhub.embeddings import get_embedding_service
from datetime import datetime, timedelta


class RAGService:
    """Service for retrieving relevant memories using RAG."""

    def __init__(self):
        """Initialize RAG service."""
        self.embedding_service = get_embedding_service()

    def search_conversations(
        self,
        db: Session,
        query: str,
        user_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.3,
        session_id: Optional[str] = None,
        platform: Optional[str] = None,
        days_back: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search conversations using vector similarity.

        Args:
            db: Database session
            query: Search query
            user_id: User ID to filter by
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0-1)
            session_id: Optional session ID filter
            platform: Optional platform filter
            days_back: Optional time filter (search last N days)

        Returns:
            List of relevant conversations with similarity scores
        """
        # Generate query embedding
        query_embedding = self.embedding_service.get_embedding(query)

        # Build filters
        filters = [Conversation.user_id == user_id]
        if session_id:
            filters.append(Conversation.session_id == session_id)
        if platform:
            filters.append(Conversation.platform == platform)
        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            filters.append(Conversation.created_at >= cutoff_date)

        # Perform vector similarity search
        results = db.query(
            Conversation,
            (1 - Conversation.embedding.cosine_distance(query_embedding)).label("similarity")
        ).filter(
            and_(*filters)
        ).order_by(
            text("similarity DESC")
        ).limit(limit * 2).all()  # Get more results to filter

        # Filter by similarity threshold and format results
        conversations = []
        for conv, similarity in results:
            if similarity >= similarity_threshold:
                conversations.append({
                    "id": conv.id,
                    "session_id": conv.session_id,
                    "role": conv.role,
                    "content": conv.content,
                    "platform": conv.platform,
                    "created_at": conv.created_at.isoformat(),
                    "similarity": float(similarity),
                    "metadata": conv.extra_metadata
                })

                if len(conversations) >= limit:
                    break

        return conversations

    def search_by_topic(
        self,
        db: Session,
        topic: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search conversations by topic using entity extraction.

        Args:
            db: Database session
            topic: Topic to search for
            user_id: User ID to filter by
            limit: Maximum number of results

        Returns:
            List of relevant conversations
        """
        # Search entities first
        topic_embedding = self.embedding_service.get_embedding(topic)

        entities = db.query(
            Entity,
            (1 - Entity.embedding.cosine_distance(topic_embedding)).label("similarity")
        ).filter(
            and_(
                Entity.entity_type.in_(["topic", "concept"]),
                Entity.conversation.has(user_id=user_id)
            )
        ).order_by(
            text("similarity DESC")
        ).limit(limit).all()

        # Get conversations from entities
        conversation_ids = list(set([e.conversation_id for e, _ in entities]))
        conversations = db.query(Conversation).filter(
            Conversation.id.in_(conversation_ids)
        ).order_by(
            Conversation.created_at.desc()
        ).all()

        return [
            {
                "id": conv.id,
                "session_id": conv.session_id,
                "role": conv.role,
                "content": conv.content,
                "platform": conv.platform,
                "created_at": conv.created_at.isoformat(),
                "metadata": conv.extra_metadata
            }
            for conv in conversations
        ]

    def get_recent_context(
        self,
        db: Session,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversation context.

        Args:
            db: Database session
            user_id: User ID
            session_id: Optional session ID
            limit: Maximum number of messages

        Returns:
            List of recent conversations
        """
        query = db.query(Conversation).filter(
            Conversation.user_id == user_id
        )

        if session_id:
            query = query.filter(Conversation.session_id == session_id)

        conversations = query.order_by(
            Conversation.created_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": conv.id,
                "session_id": conv.session_id,
                "role": conv.role,
                "content": conv.content,
                "platform": conv.platform,
                "created_at": conv.created_at.isoformat(),
                "metadata": conv.extra_metadata
            }
            for conv in reversed(conversations)  # Return in chronological order
        ]

    def search_summaries(
        self,
        db: Session,
        query: str,
        user_id: str,
        limit: int = 5,
        summary_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search conversation summaries.

        Args:
            db: Database session
            query: Search query
            user_id: User ID
            limit: Maximum number of results
            summary_type: Optional summary type filter

        Returns:
            List of relevant summaries
        """
        query_embedding = self.embedding_service.get_embedding(query)

        filters = [Summary.user_id == user_id]
        if summary_type:
            filters.append(Summary.summary_type == summary_type)

        results = db.query(
            Summary,
            (1 - Summary.embedding.cosine_distance(query_embedding)).label("similarity")
        ).filter(
            and_(*filters)
        ).order_by(
            text("similarity DESC")
        ).limit(limit).all()

        return [
            {
                "id": summary.id,
                "session_id": summary.session_id,
                "summary_text": summary.summary_text,
                "summary_type": summary.summary_type,
                "start_time": summary.start_time.isoformat() if summary.start_time else None,
                "end_time": summary.end_time.isoformat() if summary.end_time else None,
                "created_at": summary.created_at.isoformat(),
                "similarity": float(similarity)
            }
            for summary, similarity in results
        ]


# Singleton instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get RAG service singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
