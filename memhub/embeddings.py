"""Embedding generation utilities."""

from typing import List, Optional
from sentence_transformers import SentenceTransformer
from memhub.config import settings
import numpy as np


class EmbeddingService:
    """Service for generating embeddings using sentence-transformers."""

    def __init__(self):
        """Initialize embedding service."""
        print(f"Loading embedding model: {settings.embedding_model}")
        self.model = SentenceTransformer(settings.embedding_model)
        print(f"Model loaded. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            return [0.0] * settings.embedding_dimensions

        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * settings.embedding_dimensions

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts
        processed_texts = []
        indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                processed_texts.append(text)
                indices.append(i)

        if not processed_texts:
            return [[0.0] * settings.embedding_dimensions] * len(texts)

        try:
            # Generate embeddings in batch (more efficient)
            embeddings_array = self.model.encode(
                processed_texts,
                convert_to_numpy=True,
                show_progress_bar=len(processed_texts) > 100
            )

            # Map results back to original indices
            embeddings = [[0.0] * settings.embedding_dimensions] * len(texts)
            for i, idx in enumerate(indices):
                embeddings[idx] = embeddings_array[i].tolist()

            return embeddings
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return [[0.0] * settings.embedding_dimensions] * len(texts)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score
        """
        import numpy as np

        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
