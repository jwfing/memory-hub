"""Authentication and authorization service."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import bcrypt
import jwt
from memhub.database import User
from memhub.config import settings


class AuthService:
    """Service for user authentication and authorization."""

    def __init__(self):
        """Initialize auth service."""
        self.jwt_secret = settings.jwt_secret
        self.jwt_algorithm = settings.jwt_algorithm
        self.jwt_expiration_hours = settings.jwt_expiration_hours

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )

    def create_user(
        self,
        db: Session,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user.

        Args:
            db: Database session
            username: Username (must be unique)
            email: Email address (must be unique)
            password: Plain text password
            full_name: Optional full name

        Returns:
            User info dict or error dict
        """
        # Check if username exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"success": False, "error": "Username already exists"}

        # Check if email exists
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            return {"success": False, "error": "Email already exists"}

        # Validate password strength
        if len(password) < 8:
            return {"success": False, "error": "Password must be at least 8 characters"}

        # Create user
        password_hash = self.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            created_at=datetime.utcnow()
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "created_at": user.created_at.isoformat()
        }

    def authenticate_user(
        self,
        db: Session,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate a user and generate JWT token.

        Args:
            db: Database session
            username: Username or email
            password: Plain text password

        Returns:
            Authentication result with token or error
        """
        # Find user by username or email
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            return {"success": False, "error": "Invalid username or password"}

        if not user.is_active:
            return {"success": False, "error": "Account is disabled"}

        # Verify password
        if not self.verify_password(password, user.password_hash):
            return {"success": False, "error": "Invalid username or password"}

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()

        # Generate JWT token
        token = self.generate_token(user.id, user.username)

        return {
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_admin": user.is_admin
            }
        }

    def generate_token(self, user_id: int, username: str) -> str:
        """
        Generate JWT token.

        Args:
            user_id: User ID
            username: Username

        Returns:
            JWT token string
        """
        expiration = datetime.utcnow() + timedelta(hours=self.jwt_expiration_hours)

        payload = {
            "user_id": user_id,
            "username": username,
            "exp": expiration,
            "iat": datetime.utcnow()
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            User object or None
        """
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username

        Returns:
            User object or None
        """
        return db.query(User).filter(User.username == username).first()

    def update_password(
        self,
        db: Session,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> Dict[str, Any]:
        """
        Update user password.

        Args:
            db: Database session
            user_id: User ID
            old_password: Current password
            new_password: New password

        Returns:
            Result dict
        """
        user = self.get_user_by_id(db, user_id)
        if not user:
            return {"success": False, "error": "User not found"}

        # Verify old password
        if not self.verify_password(old_password, user.password_hash):
            return {"success": False, "error": "Current password is incorrect"}

        # Validate new password
        if len(new_password) < 8:
            return {"success": False, "error": "New password must be at least 8 characters"}

        # Update password
        user.password_hash = self.hash_password(new_password)
        db.commit()

        return {"success": True, "message": "Password updated successfully"}

    def deactivate_user(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Deactivate a user account.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Result dict
        """
        user = self.get_user_by_id(db, user_id)
        if not user:
            return {"success": False, "error": "User not found"}

        user.is_active = False
        db.commit()

        return {"success": True, "message": "User deactivated successfully"}

    def get_user_info(self, db: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            User info dict or None
        """
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None
        }


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get auth service singleton."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
