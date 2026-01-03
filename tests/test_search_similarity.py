#!/usr/bin/env python3
"""Test vector search similarity scores."""

from dotenv import load_dotenv
load_dotenv()

from memhub.embeddings import get_embedding_service
from memhub.database import SessionLocal, Conversation
from sqlalchemy import text

def test_search(query_text, user_id="2"):
    """Test vector search and show similarity scores."""
    # Generate query embedding
    embedding_service = get_embedding_service()
    query_embedding = embedding_service.get_embedding(query_text)

    # Query database
    db = SessionLocal()
    try:
        results = db.query(
            Conversation.id,
            Conversation.content,
            (1 - Conversation.embedding.cosine_distance(query_embedding)).label("similarity")
        ).filter(
            Conversation.user_id == user_id
        ).order_by(
            text("similarity DESC")
        ).limit(10).all()

        print(f"\n搜索结果 (查询: '{query_text}', user_id: '{user_id}'):")
        print("=" * 80)

        if not results:
            print("没有找到任何结果")
            return

        for conv_id, content, similarity in results:
            print(f"ID: {conv_id}")
            print(f"相似度: {similarity:.4f} {'✓' if similarity >= 0.7 else '✗ (< 0.7)'}")
            print(f"内容: {content[:80]}...")
            print("-" * 80)
    finally:
        db.close()

if __name__ == "__main__":
    # Test multiple queries
    queries = [
        "向量搜索",
        "Python vector search",
        "代理服务器架构",
        "proxy server"
    ]

    for query in queries:
        test_search(query)