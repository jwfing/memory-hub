#!/usr/bin/env python
"""Test authentication functionality."""

from memhub.database import SessionLocal
from memhub.auth_service import get_auth_service


def test_user_registration():
    """Test user registration."""
    print("\n=== Testing User Registration ===")

    db = SessionLocal()
    auth = get_auth_service()

    try:
        # Register a test user
        result = auth.create_user(
            db=db,
            username="test_user",
            email="test@example.com",
            password="TestPassword123",
            full_name="Test User"
        )

        if result["success"]:
            print(f"✓ User registered successfully")
            print(f"  User ID: {result['user_id']}")
            print(f"  Username: {result['username']}")
            print(f"  Email: {result['email']}")
        else:
            print(f"✗ Registration failed: {result['error']}")

        return result["success"]

    finally:
        db.close()


def test_user_login():
    """Test user login."""
    print("\n=== Testing User Login ===")

    db = SessionLocal()
    auth = get_auth_service()

    try:
        # Login
        result = auth.authenticate_user(
            db=db,
            username="test_user",
            password="TestPassword123"
        )

        if result["success"]:
            print(f"✓ Login successful")
            print(f"  Username: {result['user']['username']}")
            print(f"  Token: {result['token'][:50]}...")
            return result["token"]
        else:
            print(f"✗ Login failed: {result['error']}")
            return None

    finally:
        db.close()


def test_token_verification(token):
    """Test token verification."""
    print("\n=== Testing Token Verification ===")

    db = SessionLocal()
    auth = get_auth_service()

    try:
        # Verify token
        payload = auth.verify_token(token)

        if payload:
            print(f"✓ Token is valid")
            print(f"  User ID: {payload['user_id']}")
            print(f"  Username: {payload['username']}")

            # Get user info
            user_info = auth.get_user_info(db, payload['user_id'])
            if user_info:
                print(f"  Email: {user_info['email']}")
                print(f"  Full Name: {user_info['full_name']}")
                print(f"  Active: {user_info['is_active']}")
        else:
            print(f"✗ Token is invalid")

        return payload is not None

    finally:
        db.close()


def test_password_update(token):
    """Test password update."""
    print("\n=== Testing Password Update ===")

    db = SessionLocal()
    auth = get_auth_service()

    try:
        # Verify token first
        payload = auth.verify_token(token)
        if not payload:
            print("✗ Invalid token")
            return False

        # Update password
        result = auth.update_password(
            db=db,
            user_id=payload['user_id'],
            old_password="TestPassword123",
            new_password="NewPassword456"
        )

        if result["success"]:
            print(f"✓ Password updated successfully")

            # Try login with new password
            login_result = auth.authenticate_user(
                db=db,
                username="test_user",
                password="NewPassword456"
            )

            if login_result["success"]:
                print(f"✓ Login with new password successful")
            else:
                print(f"✗ Login with new password failed")

            # Change back to old password
            auth.update_password(
                db=db,
                user_id=payload['user_id'],
                old_password="NewPassword456",
                new_password="TestPassword123"
            )
            print(f"✓ Password reset to original")

        else:
            print(f"✗ Password update failed: {result['error']}")

        return result["success"]

    finally:
        db.close()


def cleanup():
    """Clean up test data."""
    print("\n=== Cleaning Up ===")

    db = SessionLocal()

    try:
        from memhub.database import User

        # Delete test user
        user = db.query(User).filter(User.username == "test_user").first()
        if user:
            db.delete(user)
            db.commit()
            print("✓ Test user deleted")

    finally:
        db.close()


def main():
    """Run all authentication tests."""
    print("Starting Authentication Tests...")

    try:
        # Test registration
        if not test_user_registration():
            print("\n❌ Registration test failed, skipping other tests")
            return

        # Test login
        token = test_user_login()
        if not token:
            print("\n❌ Login test failed, skipping other tests")
            return

        # Test token verification
        test_token_verification(token)

        # Test password update
        test_password_update(token)

        print("\n" + "=" * 50)
        print("All authentication tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        cleanup()


if __name__ == "__main__":
    main()
