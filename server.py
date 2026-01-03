"""Memory Hub MCP Proxy Server - Forwards requests to HTTP backend."""

import asyncio
import os
import sys
from typing import Any
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

# Global client session
client_session: ClientSession = None


async def get_client_session() -> ClientSession:
    """Get or create MCP client session to HTTP backend."""
    global client_session

    if client_session is None:
        # Prepare headers with authentication if token is provided
        headers = {}
        if AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

        # Connect to HTTP backend via SSE
        sse_url = f"{HTTP_SERVER_URL}/sse"

        try:
            # Create SSE client connection
            streams = await sse_client(
                url=sse_url,
                headers=headers
            ).__aenter__()

            # Create client session
            client_session = ClientSession(streams[0], streams[1])
            await client_session.__aenter__()

            # Initialize the session
            await client_session.initialize()

            print(f"Connected to HTTP backend at {HTTP_SERVER_URL}", file=sys.stderr)

        except Exception as e:
            print(f"Failed to connect to HTTP backend: {e}", file=sys.stderr)
            print(f"Make sure server_http.py is running on {HTTP_SERVER_URL}", file=sys.stderr)
            raise

    return client_session


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools from HTTP backend."""
    try:
        session = await get_client_session()
        result = await session.list_tools()
        return result.tools
    except Exception as e:
        print(f"Error listing tools: {e}", file=sys.stderr)
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
        print(error_msg, file=sys.stderr)
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
        print(f"Error listing resources: {e}", file=sys.stderr)
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
        print(error_msg, file=sys.stderr)
        return json.dumps({"error": error_msg})


async def main():
    """Run the MCP proxy server."""
    print("Memory Hub MCP Proxy Server starting...", file=sys.stderr)
    print(f"Connecting to HTTP backend at {HTTP_SERVER_URL}", file=sys.stderr)

    if AUTH_TOKEN:
        print("Authentication token configured", file=sys.stderr)
    else:
        print("WARNING: No authentication token configured. Set MEMHUB_AUTH_TOKEN environment variable.", file=sys.stderr)

    # Run stdio server
    async with stdio_server() as (read_stream, write_stream):
        print("Stdio server ready, connecting to backend...", file=sys.stderr)

        # Pre-connect to backend
        try:
            await get_client_session()
            print("Successfully connected to backend!", file=sys.stderr)
        except Exception as e:
            print(f"Failed to connect to backend: {e}", file=sys.stderr)
            print("The proxy will attempt to reconnect when needed.", file=sys.stderr)

        # Run the server
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())