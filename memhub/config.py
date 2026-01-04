"""Configuration management for Memory Hub MCP Server."""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""

    # Database - InsForge Cloud
    postgres_host: str = "5245iaat.us-west.database.insforge.app"
    postgres_port: int = 5432
    postgres_db: str = "insforge"
    postgres_user: str = "postgres"
    postgres_password: str = "itsnothing"
    postgres_sslmode: str = "require"  # SSL required for InsForge

    # Embedding model (sentence-transformers)
    # Popular models:
    # - "all-MiniLM-L6-v2": Fast, 384 dimensions, English
    # - "paraphrase-multilingual-MiniLM-L12-v2": Multilingual, 384 dimensions
    # - "all-mpnet-base-v2": High quality, 768 dimensions, English
    # - "paraphrase-multilingual-mpnet-base-v2": High quality, 768 dimensions, Multilingual
    embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"
    embedding_dimensions: int = 768

    # MCP Server
    mcp_server_name: str = "memory-hub"
    mcp_server_version: str = "1.0.0"

    # Authentication
    jwt_secret: str = "change-this-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24 * 7  # 7 days

    # Proxy Server Configuration (for stdio proxy mode)
    memhub_http_url: Optional[str] = None
    memhub_auth_token: Optional[str] = None

    class Config:
        # Use absolute path for .env file (relative to this config.py file)
        env_file = str(Path(__file__).parent.parent / ".env")
        case_sensitive = False

    @property
    def database_url(self) -> str:
        """Get database connection URL with SSL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}?sslmode={self.postgres_sslmode}"


settings = Settings()
