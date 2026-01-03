"""API Key management service for long-term authentication."""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session


class APIKeyService:
    """Service for managing API keys."""

    def __init__(self):
        """Initialize API key service."""
        pass

    @staticmethod
    def _hash_key(api_key: str) -> str:
        """Hash an API key using SHA-256."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def _get_key_prefix(api_key: str) -> str:
        """Get the prefix of an API key for identification."""
        return api_key[:8]

    def generate_api_key(
        self,
        db: Session,
        user_id: int,
        name: str,
        expires_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a new API key for a user.

        Args:
            db: Database session
            user_id: User ID (integer)
            name: Name/description for the API key
            expires_days: Days until expiration (None = never expires)

        Returns:
            Dict with api_key (plaintext, shown only once) and metadata
        """
        from memhub.database import APIKey

        # Generate a secure random API key
        # Format: mhub_<32 random hex characters>
        random_part = secrets.token_hex(32)
        api_key = f"mhub_{random_part}"

        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        # Hash the key for storage
        key_hash = self._hash_key(api_key)
        key_prefix = self._get_key_prefix(api_key)

        # Create and save API key record
        api_key_record = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            expires_at=expires_at,
            is_active=True,
            created_at=datetime.utcnow()
        )

        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)

        result = {
            "success": True,
            "api_key": api_key,  # Only shown once!
            "key_prefix": key_prefix,
            "key_id": api_key_record.id,
            "name": name,
            "user_id": user_id,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": api_key_record.created_at.isoformat(),
            "message": "⚠️ Save this API key securely - it won't be shown again!"
        }

        return result

    def verify_api_key(
        self,
        db: Session,
        api_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Verify an API key and return user info if valid.

        Args:
            db: Database session
            api_key: API key to verify

        Returns:
            User info dict if valid, None otherwise
        """
        from memhub.database import APIKey, User

        if not api_key or not api_key.startswith("mhub_"):
            return None

        key_hash = self._hash_key(api_key)

        # Look up API key in database
        api_key_record = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()

        if not api_key_record:
            return None

        # Check if expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            return None

        # Get user info
        user = db.query(User).filter(User.id == api_key_record.user_id).first()
        if not user or not user.is_active:
            return None

        # Update last used timestamp
        api_key_record.last_used_at = datetime.utcnow()
        db.commit()

        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "key_name": api_key_record.name,
            "is_active": True
        }

    def revoke_api_key(
        self,
        db: Session,
        user_id: int,
        key_id: Optional[int] = None,
        key_prefix: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revoke (deactivate) an API key.

        Args:
            db: Database session
            user_id: User ID
            key_id: ID of the key to revoke (optional)
            key_prefix: Prefix of the key to revoke (optional)

        Returns:
            Result dict
        """
        from memhub.database import APIKey

        query = db.query(APIKey).filter(APIKey.user_id == user_id)

        if key_id:
            query = query.filter(APIKey.id == key_id)
        elif key_prefix:
            query = query.filter(APIKey.key_prefix == key_prefix)
        else:
            return {"success": False, "error": "Must provide key_id or key_prefix"}

        api_key = query.first()

        if not api_key:
            return {"success": False, "error": "API key not found"}

        api_key.is_active = False
        db.commit()

        return {
            "success": True,
            "message": f"API key '{api_key.name}' has been revoked"
        }

    def list_api_keys(
        self,
        db: Session,
        user_id: int
    ) -> list[Dict[str, Any]]:
        """
        List all API keys for a user (without showing the actual keys).

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of API key metadata
        """
        from memhub.database import APIKey

        api_keys = db.query(APIKey).filter(
            APIKey.user_id == user_id
        ).order_by(APIKey.created_at.desc()).all()

        return [
            {
                "id": key.id,
                "name": key.name,
                "key_prefix": key.key_prefix,
                "is_active": key.is_active,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "created_at": key.created_at.isoformat()
            }
            for key in api_keys
        ]


# Singleton instance
_api_key_service: Optional[APIKeyService] = None


def get_api_key_service() -> APIKeyService:
    """Get API key service singleton."""
    global _api_key_service
    if _api_key_service is None:
        _api_key_service = APIKeyService()
    return _api_key_service