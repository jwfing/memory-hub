"""Memory Hub MCP Proxy Server - Forwards requests to HTTP backend."""

import asyncio
import os
import sys
from typing import Any, Optional
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Resource, Tool, TextContent

# Load environment variables
load_dotenv()

# Configuration
HTTP_SERVER_URL = os.getenv("MEMHUB_HTTP_URL", "http://localhost:8000")
AUTH_TOKEN = os.getenv("MEMHUB_AUTH_TOKEN", None)

# Create MCP server (proxy)
app = Server("memory-hub")


class BackendConnection:
    """Manages connection to the HTTP backend."""

    def __init__(self):
        self._sse_client = None
        self._session: Optional[ClientSession] = None
        self._headers = {}

    async def connect(self) -> ClientSession:
        """Establish connection to HTTP backend."""
        if self._session is not None:
            return self._session

        # Prepare headers with authentication if token is provided
        if AUTH_TOKEN:
            self._headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

        # Connect to HTTP backend via SSE
        sse_url = f"{HTTP_SERVER_URL}/sse"

        try:
            # Use proper async context manager pattern
            self._sse_client = sse_client(url=sse_url, headers=self._headers)
            read_stream, write_stream = await self._sse_client.__aenter__()

            # Create and initialize client session
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()
            await self._session.initialize()

            print(f"Connected to HTTP backend at {HTTP_SERVER_URL}", file=sys.stderr, flush=True)
            return self._session

        except Exception as e:
            print(f"Failed to connect to HTTP backend: {e}", file=sys.stderr, flush=True)
            print(f"Make sure server_http.py is running on {HTTP_SERVER_URL}", file=sys.stderr, flush=True)
            await self.close()
            raise

    async def close(self):
        """Close the connection."""
        try:
            if self._session is not None:
                await self._session.__aexit__(None, None, None)
                self._session = None
            if self._sse_client is not None:
                await self._sse_client.__aexit__(None, None, None)
                self._sse_client = None
        except Exception:
            # Ignore cleanup errors
            pass


# Global backend connection
backend = BackendConnection()


async def get_client_session() -> ClientSession:
    """Get or create MCP client session to HTTP backend."""
    return await backend.connect()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools from HTTP backend."""
    try:
        session = await get_client_session()
        result = await session.list_tools()
        return result.tools
    except Exception as e:
        print(f"Error listing tools: {e}", file=sys.stderr, flush=True)
        return []


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Forward tool call to HTTP backend."""
    try:
        session = await get_client_session()
        result = await session.call_tool(name, arguments)
        return result.content
    except Exception as e:
        import json
        error_msg = f"Error calling tool {name}: {e}"
        print(error_msg, file=sys.stderr, flush=True)
        return [TextContent(
            type="text",
            text=json.dumps({"error": error_msg})
        )]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources from HTTP backend."""
    try:
        session = await get_client_session()
        result = await session.list_resources()
        return result.resources
    except Exception as e:
        print(f"Error listing resources: {e}", file=sys.stderr, flush=True)
        return []


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Forward resource read to HTTP backend."""
    try:
        session = await get_client_session()
        result = await session.read_resource(uri)

        # Extract text content from the result
        if hasattr(result, 'contents') and len(result.contents) > 0:
            content = result.contents[0]
            if hasattr(content, 'text'):
                return content.text

        import json
        return json.dumps({"error": "Invalid response from backend"})
    except Exception as e:
        import json
        error_msg = f"Error reading resource {uri}: {e}"
        print(error_msg, file=sys.stderr, flush=True)
        return json.dumps({"error": error_msg})


async def main():
    """Run the MCP proxy server."""
    print("Memory Hub MCP Proxy Server starting...", file=sys.stderr, flush=True)
    print(f"Connecting to HTTP backend at {HTTP_SERVER_URL}", file=sys.stderr, flush=True)

    if AUTH_TOKEN:
        print("Authentication token configured", file=sys.stderr, flush=True)
    else:
        print("WARNING: No authentication token configured. Set MEMHUB_AUTH_TOKEN environment variable.", file=sys.stderr, flush=True)

    # Run stdio server
    async with stdio_server() as (read_stream, write_stream):
        print("Stdio server ready, connecting to backend...", file=sys.stderr, flush=True)

        # Pre-connect to backend
        try:
            await get_client_session()
            print("Successfully connected to backend!", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Failed to connect to backend: {e}", file=sys.stderr, flush=True)
            print("The proxy will attempt to reconnect when needed.", file=sys.stderr, flush=True)

        try:
            # Run the server
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        finally:
            # Clean up backend connection
            await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
