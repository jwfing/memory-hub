#!/usr/bin/env python3
"""Test script to verify proxy server can connect to HTTP backend."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_connection():
    """Test connection to HTTP backend."""
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client

    HTTP_SERVER_URL = os.getenv("MEMHUB_HTTP_URL", "http://localhost:8000")
    AUTH_TOKEN = os.getenv("MEMHUB_AUTH_TOKEN", None)

    print(f"Testing connection to: {HTTP_SERVER_URL}")
    print(f"Auth token configured: {'Yes' if AUTH_TOKEN else 'No'}")
    print(f"\n{'='*60}")

    if not AUTH_TOKEN:
        print("ERROR: No auth token configured!")
        print("Set MEMHUB_AUTH_TOKEN in your .env file")
        return False

    # Prepare headers with authentication
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # Connect to HTTP backend via SSE
    sse_url = f"{HTTP_SERVER_URL}/sse"

    try:
        print(f"Connecting to SSE endpoint: {sse_url}")

        # Create SSE client connection
        async with sse_client(
            url=sse_url,
            headers=headers
        ) as streams:
            print("✓ SSE connection established")

            # Create client session
            async with ClientSession(streams[0], streams[1]) as session:
                print("✓ Client session created")

                # Initialize the session
                await session.initialize()
                print("✓ Session initialized")

                # Test: List tools
                print("\nTesting: list_tools()")
                result = await session.list_tools()
                print(f"✓ Found {len(result.tools)} tools:")
                for tool in result.tools[:3]:  # Show first 3 tools
                    print(f"  - {tool.name}: {tool.description}")
                if len(result.tools) > 3:
                    print(f"  ... and {len(result.tools) - 3} more")

                # Test: List resources
                print("\nTesting: list_resources()")
                result = await session.list_resources()
                print(f"✓ Found {len(result.resources)} resources:")
                for resource in result.resources:
                    print(f"  - {resource.name} ({resource.uri})")

                print(f"\n{'='*60}")
                print("✓ All tests passed!")
                print("Proxy server configuration is correct!")
                print(f"{'='*60}")
                return True

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ Connection failed: {e}")
        print(f"\nDetailed error:")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}")
        print("\nTroubleshooting:")
        print("1. Make sure server_http.py is running")
        print("2. Check that MEMHUB_HTTP_URL is correct")
        print("3. Verify MEMHUB_AUTH_TOKEN is valid (not expired)")
        print(f"{'='*60}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)