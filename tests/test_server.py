#!/usr/bin/env python
"""Simple test script to verify MCP server setup."""

from memhub.database import SessionLocal, Conversation
from memhub.embeddings import get_embedding_service
from memhub.rag_service import get_rag_service
from memhub.graph_service import get_graph_service


def test_embedding_service():
    """Test embedding service."""
    print("\n=== Testing Embedding Service ===")
    service = get_embedding_service()

    text = "Hello, this is a test message"
    embedding = service.get_embedding(text)

    print(f"Text: {text}")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")

    assert len(embedding) > 0, "Embedding generation failed"
    print("✓ Embedding service working!")


def test_database_connection():
    """Test database connection."""
    print("\n=== Testing Database Connection ===")
    db = SessionLocal()

    try:
        # Count conversations
        count = db.query(Conversation).count()
        print(f"Current conversations in database: {count}")
        print("✓ Database connection working!")

    finally:
        db.close()


def test_save_and_search():
    """Test saving and searching conversations."""
    print("\n=== Testing Save and Search ===")

    db = SessionLocal()
    service = get_embedding_service()
    rag = get_rag_service()

    try:
        # Save a test conversation
        test_content = "I love learning about Python programming and machine learning"
        embedding = service.get_embedding(test_content)

        conversation = Conversation(
            user_id="test_user",
            session_id="test_session",
            role="user",
            content=test_content,
            platform="test",
            embedding=embedding
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        print(f"✓ Saved conversation with ID: {conversation.id}")

        # Search for it
        results = rag.search_conversations(
            db=db,
            query="Python machine learning",
            user_id="test_user",
            limit=5
        )

        print(f"✓ Found {len(results)} results")

        if results:
            print(f"  Top result similarity: {results[0]['similarity']:.3f}")
            print(f"  Content: {results[0]['content'][:50]}...")

    finally:
        db.close()


def test_graph_service():
    """Test graph service."""
    print("\n=== Testing Graph Service ===")

    db = SessionLocal()
    graph = get_graph_service()

    try:
        # Get entity importance (will be empty for new database)
        importance = graph.get_entity_importance(
            db=db,
            user_id="test_user",
            limit=10
        )

        print(f"✓ Found {len(importance)} important entities")

    finally:
        db.close()


def main():
    """Run all tests."""
    print("Starting Memory Hub MCP Server Tests...")

    try:
        test_database_connection()
        test_embedding_service()
        test_save_and_search()
        test_graph_service()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
