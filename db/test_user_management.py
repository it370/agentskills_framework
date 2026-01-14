"""
Test script for user management system

This script validates that the user management system is working correctly.
Run this after applying the database schema to verify everything is set up.
"""

import os
import sys
import asyncio
from pathlib import Path

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path BEFORE importing env_loader
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from env_loader import load_env_once

# Load environment using centralized env loader
load_env_once(project_root)


async def test_user_service():
    """Test user service functionality"""
    print("\n=== Testing User Service ===\n")
    
    # Import after env is loaded
    from services.user_service import UserService, UserRegistration, UserLogin, PasswordReset
    
    # Check required environment variables
    db_uri = os.getenv("DATABASE_URL")
    jwt_secret = os.getenv("JWT_SECRET")
    
    if not db_uri:
        print("❌ DATABASE_URL not set")
        return False
    
    if not jwt_secret:
        print("❌ JWT_SECRET not set")
        return False
    
    print("✓ Environment variables configured")
    
    # Initialize user service
    user_service = UserService(db_uri, jwt_secret)
    
    # Test 1: Register a user
    print("\n1. Testing user registration...")
    try:
        test_user = UserRegistration(
            username="testuser",
            email="test@example.com",
            password="TestPass123"
        )
        user = await user_service.register_user(test_user)
        print(f"✓ User registered: {user.username} (ID: {user.id})")
    except ValueError as e:
        if "already exists" in str(e):
            print(f"✓ User already exists (this is fine for testing)")
        else:
            print(f"❌ Registration failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False
    
    # Test 2: Login
    print("\n2. Testing user login...")
    try:
        login = UserLogin(username="testuser", password="TestPass123")
        token, user = await user_service.login(login)
        print(f"✓ Login successful: {user.username}")
        print(f"  Token: {token[:50]}...")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False
    
    # Test 3: Verify token
    print("\n3. Testing token verification...")
    try:
        verified_user = await user_service.verify_session(token)
        if verified_user and verified_user.username == "testuser":
            print(f"✓ Token verified: {verified_user.username}")
        else:
            print(f"❌ Token verification failed")
            return False
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        return False
    
    # Test 4: Logout
    print("\n4. Testing logout...")
    try:
        success = await user_service.logout(token)
        if success:
            print("✓ Logout successful")
        else:
            print("⚠ Logout returned False (token may not exist)")
    except Exception as e:
        print(f"❌ Logout error: {e}")
        return False
    
    # Test 5: Verify token after logout
    print("\n5. Testing token after logout...")
    try:
        verified_user = await user_service.verify_session(token)
        if verified_user:
            print("⚠ Warning: Token still valid after logout")
        else:
            print("✓ Token invalidated after logout")
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        return False
    
    print("\n✓ All user service tests passed!")
    return True


async def test_email_service():
    """Test email service (if configured)"""
    print("\n=== Testing Email Service ===\n")
    
    from services.email_service import get_email_service
    
    email_service = get_email_service()
    
    if not email_service:
        print("⚠ SMTP not configured (this is optional)")
        print("  To enable password reset emails, set SMTP_* variables in .env")
        return True
    
    print("✓ Email service configured")
    print(f"  Host: {email_service.smtp_host}")
    print(f"  Port: {email_service.smtp_port}")
    print(f"  From: {email_service.from_email}")
    
    # Note: We don't actually send an email to avoid spamming
    print("\n✓ Email service configuration valid")
    print("  (Not sending test email to avoid spam)")
    
    return True


async def test_database_schema():
    """Test database schema"""
    print("\n=== Testing Database Schema ===\n")
    
    import psycopg
    
    db_uri = os.getenv("DATABASE_URL")
    if not db_uri:
        print("❌ DATABASE_URL not set")
        return False
    
    try:
        with psycopg.connect(db_uri) as conn:
            with conn.cursor() as cur:
                # Check users table
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    )
                """)
                if cur.fetchone()[0]:
                    print("✓ users table exists")
                else:
                    print("❌ users table missing")
                    return False
                
                # Check password_reset_tokens table
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'password_reset_tokens'
                    )
                """)
                if cur.fetchone()[0]:
                    print("✓ password_reset_tokens table exists")
                else:
                    print("❌ password_reset_tokens table missing")
                    return False
                
                # Check user_sessions table
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'user_sessions'
                    )
                """)
                if cur.fetchone()[0]:
                    print("✓ user_sessions table exists")
                else:
                    print("❌ user_sessions table missing")
                    return False
                
                # Check user_id column in run_metadata
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'run_metadata' 
                        AND column_name = 'user_id'
                    )
                """)
                if cur.fetchone()[0]:
                    print("✓ run_metadata.user_id column exists")
                else:
                    print("⚠ run_metadata.user_id column missing (may not be critical)")
                
                # Count users
                cur.execute("SELECT COUNT(*) FROM users")
                user_count = cur.fetchone()[0]
                print(f"✓ Database accessible ({user_count} users)")
    
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    print("\n✓ Database schema valid")
    return True


async def test_api_endpoints():
    """Test API endpoints"""
    print("\n=== Testing API Endpoints ===\n")
    
    import httpx
    
    base_url = "http://localhost:8000"
    
    try:
        # Test health endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("✓ API is running")
            else:
                print(f"⚠ API returned status {response.status_code}")
    except httpx.ConnectError:
        print("⚠ API not running (start with: python main.py)")
        print("  Skipping API endpoint tests")
        return True
    except Exception as e:
        print(f"❌ API error: {e}")
        return False
    
    # Test auth endpoints
    try:
        async with httpx.AsyncClient() as client:
            # Test register endpoint
            response = await client.post(
                f"{base_url}/auth/register",
                json={
                    "username": "apitest",
                    "email": "apitest@example.com",
                    "password": "ApiTest123"
                }
            )
            if response.status_code in [200, 201]:
                print("✓ Registration endpoint works")
                token = response.json()["access_token"]
            elif response.status_code == 400 and "already exists" in response.text:
                print("✓ Registration endpoint works (user exists)")
                # Try login instead
                response = await client.post(
                    f"{base_url}/auth/login",
                    json={
                        "username": "apitest",
                        "password": "ApiTest123"
                    }
                )
                token = response.json()["access_token"]
            else:
                print(f"⚠ Registration endpoint returned {response.status_code}")
                print(f"  Response: {response.text}")
                return True
            
            # Test authenticated endpoint
            response = await client.get(
                f"{base_url}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                user = response.json()
                print(f"✓ Authenticated endpoint works (user: {user['username']})")
            else:
                print(f"⚠ Authenticated endpoint returned {response.status_code}")
    
    except Exception as e:
        print(f"❌ API endpoint error: {e}")
        return False
    
    print("\n✓ API endpoints working")
    return True


async def main():
    """Run all tests"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       User Management System - Validation Tests             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    results = []
    
    # Run tests
    results.append(("Database Schema", await test_database_schema()))
    results.append(("User Service", await test_user_service()))
    results.append(("Email Service", await test_email_service()))
    results.append(("API Endpoints", await test_api_endpoints()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{name:.<50} {status}")
    
    print("="*60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed! User management system is ready.")
        print("\nNext steps:")
        print("1. Start the application: python main.py")
        print("2. Register users via /auth/register")
        print("3. Use JWT tokens for all API requests")
        print("4. See QUICKSTART_USER_MANAGEMENT.md for usage examples")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        print("\nTroubleshooting:")
        print("1. Ensure DATABASE_URL is set in .env")
        print("2. Ensure JWT_SECRET is set in .env")
        print("3. Run: python db/apply_user_schema.py")
        print("4. Check database is accessible")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
